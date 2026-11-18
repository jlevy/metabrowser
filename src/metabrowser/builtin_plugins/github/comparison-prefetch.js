// A pull request's comparison, read on every tab but Changes before Changes asks for it, and
// kept for the document.
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
//
// What was read is kept for the document, not for one page (`createComparisonKeep`), because
// a page is mounted again for every visit (mb-neg9). Before, each visit to a pull request
// read its comparison anew: the browser's cache answered without the server, but only once
// the browser was idle, which the page's own first paint is not, and then parsed it again.
// Measured 2026-11-16 in headless Chrome 152 on the GitHub stand-in at a load average of 9
// to 12, moving between three pull requests of 26 to 121 files from the Pulls tab: a
// revisit's Diff summary arrived 22 to 50 ms after the click, and 175 to 238 ms at four
// times slower CPU, 156 to 164 ms of it the wait for idle. The app's WebKit has no
// `requestIdleCallback`, so there the wait is the 250 ms quiet after a press
// (docs/project/architecture/arch-browser-shell.md, "Idle Work"): with a real press and
// none, 253 to 256 ms. A kept comparison is drawn in the paint that shows its record, with
// no request, no wait, and no parse: 13 to 20 ms after the click, 57 to 73 ms at four
// times slower CPU, and 16 to 19 ms with no `requestIdleCallback`, the record's own read
// and paint. Measured again after review, at a load average of 19 to 47: 16 to 27 ms, 46
// to 63 ms, and 16 to 23 ms, where the old page at that load took 32 to 36 ms with a real
// press and 255 to 259 ms with no `requestIdleCallback`.
//
// A page opened on Changes reads through the keep too (`take`), so the next visit to that
// pull request is drawn from it like any other. The Pulls tab warms the keep for the pull
// requests a reader opens next (`createComparisonWarmer`): the rows the pointer or focus
// rested on, the open pull request's neighbours in its stacks, and its neighbours in the
// list.
//
// What the keep reads is the comparison alone. A request in it is shared and outlives any
// one asker, so the first screen's rendered Markdown, which a page leaving must stop, is the
// page's own to ask for, with its own signal (`prefetchMarkdown` on the diff view).

/**
 * @typedef {{left: string, right: string, route?: string, rendered_route?: string}} ComparisonEnds
 *
 * @typedef {{
 *   load(comparison: ComparisonEnds, signal: AbortSignal): Promise<unknown>,
 *   warm(): void,
 *   reading?(comparison: ComparisonEnds): void,
 *   loaded?(comparison: ComparisonEnds, payload: unknown): void,
 *   failed?(comparison: ComparisonEnds): void,
 *   schedule(callback: () => void): unknown,
 *   cancel(handle: unknown): void,
 *   isVisible(): boolean,
 *   keep?: ComparisonKeep,
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
 *
 * @typedef {ReturnType<typeof createComparisonKeep>} ComparisonKeep
 */

/**
 * The comparison's identity: its route names the pull request, both commits, the build and
 * the store, so an answer kept under it is the answer for as long as the record names it. A
 * record whose head or base moved names another route, and so another key.
 *
 * @param {ComparisonEnds} comparison
 */
export const comparisonKey = (comparison) =>
  comparison.route ?? `${comparison.left}...${comparison.right}`;

// Characters of comparison JSON the keep holds, least recently used out first. Measured
// 2026-11-16 over this repository's 192 merged pull requests, #1 to #475, with the route's
// own first answer, eight files' patches and every path: 59 KB at the median, 172 KB at the
// 90th percentile, 959 KB at the 99th, 1.34 MB at the largest, and 17.4 MB for all 192. The
// parsed answer holds 0.97 to 1.66 times its JSON length in V8's heap (`settings.py`,
// GIT_COMPARISON_CACHE_BYTES, which bounds the Commits panel's keep the same way), so this
// is at most about 27 MiB of heap. It keeps about ninety 90th-percentile pull requests, more
// than a reader opens in a sitting, and the browser's own cache answers past it.
export const KEPT_COMPARISON_CHARS = 16 * 1024 * 1024;
// An answer larger than this is handed on and not kept: one must not push out every other.
// The largest measured, 1.34 MB, is a third of it.
export const KEPT_COMPARISON_ENTRY_CHARS = KEPT_COMPARISON_CHARS / 4;

/**
 * What the document has read of comparisons: answers, by key, within a bound on their JSON
 * length, and the requests on their way, which a second asker joins instead of sending its
 * own. A request is abandoned only when every asker has gone.
 *
 * An answer is measured in a task after the one that hands it on, as the Commits panel's
 * keep does (`static/git-panel.js`): 0.45 ms for 197 KB, about 8 ms for 3.3 MB. Until then
 * its request stands for it. Only an answer is kept: a refusal is asked again.
 *
 * @param {{maxChars?: number, entryChars?: number, measure?: (payload: unknown) => number, later?: (callback: () => void) => void}} [options]
 */
export function createComparisonKeep(options = {}) {
  const maxChars = options.maxChars ?? KEPT_COMPARISON_CHARS;
  const entryChars = options.entryChars ?? KEPT_COMPARISON_ENTRY_CHARS;
  const measure = options.measure ?? ((payload) => JSON.stringify(payload)?.length ?? 0);
  const later = options.later ?? ((callback) => void setTimeout(callback, 0));
  /** @type {Map<string, {payload: unknown, chars: number}>} */
  const kept = new Map();
  /** @type {Map<string, {promise: Promise<unknown>, controller: AbortController, askers: number}>} */
  const pending = new Map();
  let chars = 0;
  let generation = 0;

  /** @param {string} key @param {unknown} payload */
  function keep(key, payload) {
    let size;
    try {
      size = measure(payload);
    } catch {
      return;
    }
    const previous = kept.get(key);
    if (previous) {
      kept.delete(key);
      chars -= previous.chars;
    }
    if (size > entryChars) {
      return;
    }
    kept.set(key, { payload, chars: size });
    chars += size;
    for (const [oldest, entry] of kept) {
      if (chars <= maxChars) {
        break;
      }
      kept.delete(oldest);
      chars -= entry.chars;
    }
  }

  /**
   * This asker's wait on a request, which ends early when *signal* aborts.
   *
   * @param {string} key
   * @param {{promise: Promise<unknown>, controller: AbortController, askers: number}} entry
   * @param {AbortSignal | undefined} signal
   * @returns {Promise<unknown>}
   */
  function wait(key, entry, signal) {
    entry.askers += 1;
    if (signal === undefined) {
      return entry.promise;
    }
    return new Promise((resolve, reject) => {
      const leave = () => {
        entry.askers -= 1;
        if (entry.askers === 0 && pending.get(key) === entry) {
          pending.delete(key);
          entry.controller.abort();
        }
        reject(new DOMException("The comparison is no longer wanted.", "AbortError"));
      };
      if (signal.aborted) {
        leave();
        return;
      }
      signal.addEventListener("abort", leave, { once: true });
      entry.promise.then(
        (payload) => {
          signal.removeEventListener("abort", leave);
          resolve(payload);
        },
        (error) => {
          signal.removeEventListener("abort", leave);
          reject(error);
        },
      );
    });
  }

  /** @param {string} key */
  function held(key) {
    const entry = kept.get(key);
    if (entry === undefined) {
      return undefined;
    }
    kept.delete(key);
    kept.set(key, entry);
    return entry.payload;
  }

  return Object.freeze({
    /** The kept answer for *key*, marked most recently used, or undefined. */
    held,
    /** Whether an answer for *key* is kept or on its way. @param {string} key */
    has: (key) => kept.has(key) || pending.has(key),
    /**
     * The kept answer, or a wait on the request on its way; undefined when there is neither,
     * and nothing is sent.
     *
     * @param {string} key
     * @param {AbortSignal} [signal]
     * @returns {Promise<unknown> | undefined}
     */
    join(key, signal) {
      if (kept.has(key)) {
        return Promise.resolve(held(key));
      }
      const entry = pending.get(key);
      return entry === undefined ? undefined : wait(key, entry, signal);
    },
    /**
     * The kept answer, the request on its way, or *load*'s, which is kept when it answers.
     *
     * @param {string} key
     * @param {(signal: AbortSignal) => Promise<unknown>} load
     * @param {AbortSignal} [signal]
     * @returns {Promise<unknown>}
     */
    read(key, load, signal) {
      if (kept.has(key)) {
        return Promise.resolve(held(key));
      }
      let entry = pending.get(key);
      if (entry === undefined) {
        const controller = new AbortController();
        const asked = generation;
        /** @type {{promise: Promise<unknown>, controller: AbortController, askers: number}} */
        const fresh = {
          controller,
          askers: 0,
          promise: load(controller.signal).then(
            (payload) => {
              later(() => {
                if (pending.get(key) === fresh) {
                  pending.delete(key);
                }
                if (asked === generation && !controller.signal.aborted) {
                  keep(key, payload);
                }
              });
              return payload;
            },
            (error) => {
              if (pending.get(key) === fresh) {
                pending.delete(key);
              }
              throw error;
            },
          ),
        };
        // Every asker handles its own rejection; this marks the shared one handled.
        fresh.promise.catch(() => {});
        entry = fresh;
        pending.set(key, entry);
      }
      return wait(key, entry, signal);
    },
    /**
     * Keep *payload* under *key*, as an answer that arrived is kept, for an answer whose key
     * is known only from the answer itself: a stack's change names its two commits
     * (stack-lines.js). Measured now, since such an answer is small.
     *
     * @param {string} key
     * @param {unknown} payload
     */
    put(key, payload) {
      keep(key, payload);
    },
    /**
     * Settles once no request is on its way, so a warm waits behind a page's own read rather
     * than sharing the server with it.
     *
     * @returns {Promise<void>}
     */
    async quiet() {
      while (pending.size > 0) {
        await Promise.allSettled([...pending.values()].map((entry) => entry.promise));
        // Each answer leaves `pending` in a task after it arrives.
        await new Promise((resolve) => later(() => resolve(undefined)));
      }
    },
    /** Forget everything, and keep no answer on its way. */
    clear() {
      generation += 1;
      kept.clear();
      chars = 0;
      for (const entry of pending.values()) {
        entry.controller.abort();
      }
      pending.clear();
    },
    snapshot: () => ({ kept: [...kept.keys()], chars, pending: [...pending.keys()] }),
  });
}

/** The document's keep, which every pull request page and the Pulls tab share. */
export const documentComparisons = createComparisonKeep();

/**
 * How the GitHub plugin reads a comparison: through the diff plugin's `prefetch`, which
 * spells the address, so the request `mountDiff` would make is this one, byte for byte, and
 * the browser's cache answers a Back from it. The comparison alone: what it reads goes in
 * the keep, whose request outlives its askers, so no Markdown projection rides on it.
 *
 * @param {{ensureKindAssets(kind: string): Promise<unknown>, getRegisteredView(kind: string, name: string): unknown}} mb
 * @returns {(comparison: ComparisonEnds, signal: AbortSignal) => Promise<unknown>}
 */
export function diffComparisonLoader(mb) {
  return async (comparison, signal) => {
    await mb.ensureKindAssets("diff");
    signal.throwIfAborted();
    const view =
      /** @type {{prefetch?: (comparison: object, signal: AbortSignal) => Promise<unknown>} | null} */ (
        mb.getRegisteredView("diff", "diff")
      );
    if (typeof view?.prefetch !== "function") {
      throw new Error("the diff view has no prefetch");
    }
    return view.prefetch(
      {
        left: comparison.left,
        right: comparison.right,
        base_policy: "merge_base",
        ...(comparison.route === undefined ? {} : { route: comparison.route }),
      },
      signal,
    );
  };
}

/**
 * The prefetch of one page. Its only way into the diff is `take`.
 *
 * @param {PrefetchDependencies} deps
 */
export function createComparisonPrefetch(deps) {
  const keep = deps.keep ?? documentComparisons;
  /**
   * What this page has for the comparison it last wanted. A payload stays here only until it
   * is taken; the keep holds it for the next mount and the next page.
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

  /**
   * Follow *entry*'s answer, from the request on its way or the keep.
   *
   * @param {PrefetchEntry} entry
   * @param {ComparisonEnds} comparison
   * @param {Promise<unknown>} answer
   */
  function follow(entry, comparison, answer) {
    entry.phase = "fetching";
    entry.payload = answer.then(
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
          // A read no mount waits on failed: the page's Diff summary has nothing to wait for
          // (mb-onr2), and is not left showing an earlier comparison's (A1 of review A on
          // #470). A mount that took it asks for itself and says why itself.
          if (current === entry && !disposed) {
            deps.failed?.(comparison);
          }
        }
        return undefined;
      },
    );
  }

  /**
   * *entry*'s read of *comparison* through the keep: the kept answer, the request on its way,
   * or a request of its own, which every other asker can join. It ends for this page when
   * *entry*'s controller aborts.
   *
   * @param {PrefetchEntry} entry
   * @param {ComparisonEnds} comparison
   */
  function readThrough(entry, comparison) {
    entry.controller ??= new AbortController();
    return keep.read(entry.key, (signal) => deps.load(comparison, signal), entry.controller.signal);
  }

  /** @param {PrefetchEntry} entry @param {ComparisonEnds} comparison */
  function start(entry, comparison) {
    if (disposed || current !== entry) {
      return;
    }
    deps.warm();
    follow(entry, comparison, readThrough(entry, comparison));
  }

  return Object.freeze({
    /**
     * The page shows this comparison, and the reader is not looking at it. One the document
     * keeps is drawn now, in the paint that asked; one on its way is joined; any other is
     * read when the browser is idle.
     * A comparison whose read failed is asked for again.
     *
     * @param {ComparisonEnds} comparison
     */
    want(comparison) {
      const key = comparisonKey(comparison);
      if (disposed || (current?.key === key && current.phase !== "failed")) {
        return;
      }
      const kept = keep.held(key);
      if (kept !== undefined) {
        release();
        current = {
          key,
          phase: "held",
          handle: null,
          controller: null,
          payload: Promise.resolve(kept),
        };
        deps.warm();
        deps.loaded?.(comparison, kept);
        return;
      }
      if (!deps.isVisible()) {
        return;
      }
      release();
      // The entry's controller is its from the start, so whatever it joins, here or once a
      // mount takes it while it waits for idle, it leaves when the page goes.
      /** @type {PrefetchEntry} */
      const entry = {
        key,
        phase: "waiting",
        handle: null,
        controller: new AbortController(),
        payload: null,
      };
      current = entry;
      const joined = keep.join(key, entry.controller?.signal);
      if (joined !== undefined) {
        // Another page, or the Pulls tab, is reading it: no request of this page's own.
        deps.warm();
        follow(entry, comparison, joined);
        // Its read is on its way, for the page's Diff summary to wait on (mb-onr2).
        deps.reading?.(comparison);
        return;
      }
      entry.handle = deps.schedule(() => start(entry, comparison));
      // A read of it is on its way, for the page's Diff summary to wait on (mb-onr2), the
      // same comparison's again after another's.
      deps.reading?.(comparison);
    },
    /**
     * The reader asked: the payload if there is one, here or kept, waiting for a request on
     * its way; otherwise the comparison is read now, through the keep, so the next visit is
     * drawn from it. Undefined when that read fails, and the diff asks for itself, and says
     * why itself.
     *
     * @param {ComparisonEnds} comparison
     * @returns {Promise<unknown>}
     */
    take(comparison) {
      const key = comparisonKey(comparison);
      if (disposed) {
        return Promise.resolve(undefined);
      }
      if (current?.key !== key) {
        release();
        current = {
          key,
          phase: "taken",
          handle: null,
          controller: new AbortController(),
          payload: null,
        };
      } else if (current.phase === "waiting") {
        deps.cancel(current.handle);
      }
      const payload = current.payload ?? readThrough(current, comparison).catch(() => undefined);
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

// Comparisons one ask of the Pulls tab warms, in its order: the open pull request, whose page
// joins a warm of it on its way, the two rows the pointer or focus last rested on, the open
// pull request's neighbours in its stacks, then its neighbours in the list. Past the first
// few the ask changes before the lane reaches them.
export const WARM_COMPARISONS = 5;
// Warms the lane starts in an hour, each counted before its record is read. A warm is a
// record read from the cache and, when the keep has neither its comparison nor a request for
// it on its way, that comparison from the repository store, local Git with no network and no
// GitHub call; it asks for no rendered Markdown (`diffComparisonLoader`). Measured 2026-11-16
// on the GitHub stand-in at a load average of 9 to 12, a record read was 3 to 6 KB and 2 to
// 35 ms of server time, and a first comparison of 26 to 121 files 10 to 25 KB gzipped, 169
// to 676 KB of JSON, 76 to 354 ms of server time, and five Git processes; a repeat ran none.
// Over this repository's 192 merged pull requests a first answer took 115 ms at the median
// and 345 ms at the most, 12 KB gzipped at the median and 112 KB at the most. So an hour's
// cap is about 14 s of comparison time at the median and 41 s at the most, and at most 4 s
// of record reads, and the answers stay in the keep and in the server's own
// (`MAX_CACHED_MANIFESTS`, `MAX_CACHED_BODY_BYTES`). The cap is the warms' alone: the stack
// headings' change lines count their reads against a cap of their own (stack-lines.js,
// `STACK_LINES_PER_HOUR`), so they cannot spend the warms' share (review of #484, A2).
export const WARM_PER_HOUR = 120;
// The pull requests whose last outcome the lane remembers, oldest out first.
const WARM_FOUND = 64;
// The recent outcomes a snapshot reports.
const WARM_RECENT = 8;
const HOUR_MS = 3_600_000;

/**
 * An hourly count of the local reads a Pulls tab's lane starts on its own: the comparison
 * warmer's (`WARM_PER_HOUR`), and apart from it the stack lines' (stack-lines.js,
 * `STACK_LINES_PER_HOUR`). A read is counted as it starts.
 *
 * @param {() => number} now
 * @param {number} [limit]
 */
export function createWarmBudget(now, limit = WARM_PER_HOUR) {
  /** When each counted read started. @type {number[]} */
  let sent = [];
  /** @param {number} at */
  const recent = (at) => {
    sent = sent.filter((started) => at - started < HOUR_MS);
    return sent.length;
  };
  return Object.freeze({
    /** Count a read that starts now, or refuse it when the hour's cap is spent. */
    take() {
      const at = now();
      if (recent(at) >= limit) {
        return false;
      }
      sent.push(at);
      return true;
    },
    /** Whether the hour's cap is spent, so a read asked for now would be refused. */
    spent: () => recent(now()) >= limit,
    /** The reads counted, as of the last one started or refused. */
    count: () => sent.length,
  });
}

/** @typedef {ReturnType<typeof createWarmBudget>} WarmBudget */

/**
 * A pull request's record as a warm reads it: the comparison it names, or null, and how long
 * it holds, the envelope's `fresh_for_s`, past which its head may have moved.
 *
 * @typedef {{comparison: ComparisonEnds | null, freshForMs: number}} WarmRecord
 */

/**
 * The Pulls tab's warming of the keep: one pull request at a time, each when the browser is
 * idle, the record read from the cache and its comparison asked for only when the keep has
 * neither it nor a request on its way, and only once no other request is on its way, so a
 * page's own read never shares the server with a warm. An ask replaces the queue. The one
 * being read goes on: the server computes a comparison it was asked for whether or not the
 * asker stays, so what stopping it would save is the answer, and that is what the row just
 * left, or just clicked, may want next.
 *
 * Every outcome holds for its record's freshness window, and a pull request is not read
 * again while it does: a comparison kept or warmed, while the keep still has it, a record
 * that names none, a refusal, an answer too large to keep, and a read that failed, which
 * holds for the window the last record gave.
 *
 * @param {{
 *   keep?: ComparisonKeep,
 *   read(number: number, signal: AbortSignal): Promise<WarmRecord>,
 *   load(comparison: ComparisonEnds, signal: AbortSignal): Promise<unknown>,
 *   schedule(callback: () => void): unknown,
 *   cancel(handle: unknown): void,
 *   isVisible(): boolean,
 *   now(): number,
 * }} deps
 */
export function createComparisonWarmer(deps) {
  const keep = deps.keep ?? documentComparisons;
  const budget = createWarmBudget(deps.now);
  /** @type {number[]} */
  let queue = [];
  /** @type {unknown} */
  let handle = null;
  /** @type {{number: number, controller: AbortController} | null} */
  let running = null;
  /**
   * Each pull request's last outcome: its comparison's key, if its record named one, when,
   * for how long it holds, and whether it left the answer in the keep.
   *
   * @type {Map<number, {key: string | null, at: number, holdsMs: number, inKeep: boolean}>}
   */
  const found = new Map();
  /** The freshness window the last record read gave, which a failed read holds for. */
  let windowMs = 0;
  /** @type {string[]} */
  const recent = [];
  let disposed = false;

  /** @param {number} number @param {string} outcome */
  function note(number, outcome) {
    recent.push(`${number}: ${outcome}`);
    if (recent.length > WARM_RECENT) {
      recent.shift();
    }
  }

  /**
   * *number*'s warm ended in *outcome*, which holds for the window.
   *
   * @param {number} number
   * @param {string | null} key
   * @param {string} outcome
   */
  function settle(number, key, outcome) {
    note(number, outcome);
    found.delete(number);
    found.set(number, {
      key,
      at: deps.now(),
      holdsMs: windowMs,
      inKeep: outcome === "kept" || outcome === "warmed",
    });
    if (found.size > WARM_FOUND) {
      found.delete(/** @type {number} */ (found.keys().next().value));
    }
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
      const number = queue.shift();
      if (number !== undefined) {
        void run(number);
      }
    });
  }

  /**
   * Whether *number*'s last outcome still holds: within its window and, for one that left
   * its answer in the keep, while the keep has it.
   *
   * @param {number} number
   */
  function settled(number) {
    const seen = found.get(number);
    return (
      seen !== undefined &&
      deps.now() - seen.at < seen.holdsMs &&
      (!seen.inKeep || (seen.key !== null && keep.has(seen.key)))
    );
  }

  /** @param {number} number */
  async function run(number) {
    if (disposed || !deps.isVisible()) {
      return;
    }
    if (settled(number)) {
      next();
      return;
    }
    // Counted before the record is read, so a lane the cap holds reads nothing more.
    if (!budget.take()) {
      note(number, "hourly cap");
      queue = [];
      return;
    }
    const controller = new AbortController();
    running = { number, controller };
    /** @type {string | null} */
    let key = null;
    try {
      const record = await deps.read(number, controller.signal);
      if (controller.signal.aborted) {
        return;
      }
      windowMs = record.freshForMs;
      const comparison = record.comparison;
      if (comparison === null) {
        settle(number, null, "no comparison");
        return;
      }
      key = comparisonKey(comparison);
      if (keep.has(key)) {
        settle(number, key, "kept");
        return;
      }
      // Behind the reader: a comparison a page is reading, the open pull request's, goes
      // first, since a warm sent beside it would share the server with it.
      await keep.quiet();
      if (controller.signal.aborted) {
        return;
      }
      if (keep.has(key)) {
        settle(number, key, "kept");
        return;
      }
      await keep.read(key, (signal) => deps.load(comparison, signal), controller.signal);
      // The keep measures an answer in a task after the one that hands it on, and declines
      // one too large to keep.
      await keep.quiet();
      settle(number, key, keep.has(key) ? "warmed" : "not kept");
    } catch {
      if (controller.signal.aborted) {
        note(number, "cancelled");
      } else {
        settle(number, key, "failed");
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
     * The pull requests to warm, most likely first. Only the first `WARM_COMPARISONS` count.
     * An empty ask empties the queue, as a panel that is hidden or offline asks.
     *
     * @param {number[]} numbers
     */
    want(numbers) {
      if (disposed) {
        return;
      }
      const wanted = [...new Set(numbers)].slice(0, WARM_COMPARISONS);
      queue = wanted.filter((number) => number !== running?.number && !settled(number));
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
      queue: [...queue],
      running: running?.number ?? null,
      sentThisHour: budget.count(),
      recent: [...recent],
    }),
  });
}
