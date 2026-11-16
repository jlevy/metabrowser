// A pull request's comparison, read on every tab but Changes before Changes asks for it.
//
// The page knows the comparison the moment the record arrives. Its header's Diff summary is
// drawn from what is read here, on Conversation and Checks (mb-pb35), and the reader's next
// click is often Changes, which is then handed the same answer. Principle 6 of the design
// system says to fetch it now unless the cost is real and known, so this is what the cost is:
//
// - One request per comparison a page shows, sent when the browser is idle, so it does not
//   queue ahead of an interaction. The server keeps the answer, so it is computed once. A
//   read that failed is asked again at the page's next paint, which is no sooner than its
//   next record or tab, so a refusal cannot loop.
// - Measured 2026-11-02 in Node 24 at load 14, the same V8 Chrome has, on real first pages:
//   parsing took 3 ms for 1.0 MB and 49 ms for the largest real page, 13.6 MB of fifty files
//   of a +442,186-line pull request, which holds 26 MB of heap until the click. The route's
//   8 MiB bound on a page's patch is the ceiling on both.
// - The diff plugin's modules and stylesheet, a prefetched tier on this page, as they would
//   otherwise load with the first diff.
//
// A record that refreshes repaints the page, so `want` is asked again every poll: it is a
// no-op for the same comparison unless its read failed, and a record that moved its head
// cancels the old request.

/**
 * @typedef {{left: string, right: string, route?: string, rendered_route?: string}} ComparisonEnds
 *
 * @typedef {{
 *   load(comparison: ComparisonEnds, signal: AbortSignal): Promise<unknown>,
 *   warm(): void,
 *   loaded?(comparison: ComparisonEnds, payload: unknown): void,
 *   failed?(comparison: ComparisonEnds): void,
 *   schedule(callback: () => void): unknown,
 *   cancel(handle: unknown): void,
 *   isVisible(): boolean,
 * }} PrefetchDependencies
 *
 * @typedef {"waiting" | "fetching" | "held" | "taken" | "failed"} PrefetchPhase
 *
 * @typedef {{
 *   key: string,
 *   phase: PrefetchPhase,
 *   handle: unknown,
 *   controller: AbortController | null,
 *   payload: Promise<unknown> | null,
 * }} PrefetchEntry
 */

/** @param {ComparisonEnds} comparison */
const keyOf = (comparison) => comparison.route ?? `${comparison.left}...${comparison.right}`;

/**
 * The prefetch of one page. Its only way into the diff is `take`.
 *
 * @param {PrefetchDependencies} deps
 */
export function createComparisonPrefetch(deps) {
  /**
   * What this page has for the comparison it last wanted. A payload stays only until it is
   * taken: from then on the browser's own cache answers a Back, and the page holds nothing.
   *
   * @type {PrefetchEntry | null}
   */
  let current = null;
  let disposed = false;

  /** Let go of what the current entry holds, unless a mount is waiting on its request. */
  function release() {
    if (current === null) {
      return;
    }
    if (current.phase === "waiting") {
      deps.cancel(current.handle);
    }
    if (current.phase === "fetching") {
      current.controller?.abort();
    }
    current = null;
  }

  /** @param {PrefetchEntry} entry @param {ComparisonEnds} comparison */
  function start(entry, comparison) {
    if (disposed || current !== entry) {
      return;
    }
    deps.warm();
    const controller = new AbortController();
    entry.controller = controller;
    entry.phase = "fetching";
    entry.payload = deps.load(comparison, controller.signal).then(
      (payload) => {
        if (entry.phase === "fetching") {
          entry.phase = "held";
        }
        // What was read, for the page's Diff summary, taken or not (mb-pb35).
        if (current === entry && !disposed) {
          deps.loaded?.(comparison, payload);
        }
        return payload;
      },
      () => {
        if (entry.phase === "fetching") {
          entry.phase = "failed";
          // The page's Diff summary is not left showing an earlier comparison's (A1 of
          // review A on #470). A taken read is the diff's, which says so itself.
          if (current === entry && !disposed) {
            deps.failed?.(comparison);
          }
        }
        return undefined;
      },
    );
  }

  return Object.freeze({
    /**
     * The page shows this comparison, and the reader is not looking at it. A comparison whose
     * read failed is asked for again.
     *
     * @param {ComparisonEnds} comparison
     */
    want(comparison) {
      const key = keyOf(comparison);
      if (disposed || (current?.key === key && current.phase !== "failed") || !deps.isVisible()) {
        return;
      }
      release();
      /** @type {PrefetchEntry} */
      const entry = { key, phase: "waiting", handle: null, controller: null, payload: null };
      current = entry;
      entry.handle = deps.schedule(() => start(entry, comparison));
    },
    /**
     * The reader asked: the payload if there is one, waiting for a request on its way, or
     * undefined, and the diff asks for itself, and says so itself if that fails.
     *
     * @param {ComparisonEnds} comparison
     * @returns {Promise<unknown>}
     */
    take(comparison) {
      const key = keyOf(comparison);
      if (disposed) {
        return Promise.resolve(undefined);
      }
      if (current?.key !== key) {
        release();
        current = { key, phase: "taken", handle: null, controller: null, payload: null };
        return Promise.resolve(undefined);
      }
      if (current.phase === "waiting") {
        deps.cancel(current.handle);
      }
      const payload = current.payload ?? Promise.resolve(undefined);
      current.phase = "taken";
      current.payload = null;
      return payload;
    },
    dispose() {
      disposed = true;
      if (current !== null && current.phase === "taken") {
        // A mount waiting on it is being disposed too.
        current.controller?.abort();
      }
      release();
    },
    snapshot: () => ({
      phase: current?.phase ?? "none",
      comparison: current?.key ?? null,
      holding: current?.payload !== null && current?.payload !== undefined,
    }),
  });
}
