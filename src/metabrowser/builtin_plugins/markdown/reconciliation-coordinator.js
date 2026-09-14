import { createTrustedStandardLinkResolutionContext } from "./links.js";
import { createPublishedRouteResolutionContext } from "./project-adapters.js";
import {
  createTrustedWikiSourcePathContext,
  createWikiResolutionContext,
} from "./wiki-resolver.js";

const MAX_ELEMENTS_PER_CALLBACK = 32;
// One rendered root admits at most 4,096 catalog/long-source reconciliation jobs.
// `createMarkdownEnhancementBudget` separately applies the same aggregate ceiling
// to eager standard, resource, and wiki enhancement across nested transclusions.
const MAX_RECONCILIATION_JOBS = 4096;
// exp-032 measured a single 500k unresolved-basename scan at 150–200ms.
// Every root mount, including nested transclusions, therefore shares this one
// path-visit allowance instead of allocating the allowance per enhancer.
const MAX_PATH_VISITS_PER_CALLBACK = 16_384;

/**
 * Bound every functional link/resource/wiki target in one rendered root before
 * any selector-specific work is retained or queued. Nested transclusions receive
 * this same non-refundable budget from their parent enhancer.
 *
 * @param {number=} maxElements
 */
export function createMarkdownEnhancementBudget(maxElements = MAX_RECONCILIATION_JOBS) {
  if (
    !Number.isSafeInteger(maxElements) ||
    maxElements < 1 ||
    maxElements > MAX_RECONCILIATION_JOBS
  ) {
    throw new TypeError("Markdown enhancement limit must be a supported positive integer");
  }
  let admitted = 0;
  const budget = Object.freeze({
    claim() {
      if (admitted >= maxElements) {
        return false;
      }
      admitted += 1;
      return true;
    },
    exhausted() {
      return admitted >= maxElements;
    },
  });
  return budget;
}

/**
 * @typedef {ReturnType<typeof createWikiResolutionContext>} WikiContext
 * @typedef {ReturnType<typeof createPublishedRouteResolutionContext>} PublishedContext
 * @typedef {ReturnType<typeof createTrustedStandardLinkResolutionContext>} StandardContext
 * @typedef {ReturnType<WikiContext["begin"]>} WikiApplication
 * @typedef {ReturnType<StandardContext["begin"]>} StandardApplication
 */

/**
 * @typedef {object} BaseJob
 * @property {boolean} active
 * @property {number} generation
 * @property {number} processedGeneration
 * @property {ScopeState} scope
 */

/**
 * @typedef {BaseJob & {kind: "wiki", intent: unknown,
 *   application: WikiApplication | null,
 *   commit: (result: NonNullable<ReturnType<WikiApplication["step"]>["result"]>) => void}} WikiJob
 */

/**
 * @typedef {BaseJob & {kind: "published", intent: unknown,
 *   commit: (result: ReturnType<PublishedContext["resolve"]>) => void}} PublishedJob
 */

/**
 * @typedef {BaseJob & {kind: "standard", intent: unknown,
 *   application: StandardApplication | null,
 *   commit: (result: NonNullable<ReturnType<StandardApplication["step"]>["result"]>) => void}} StandardJob
 */

/** @typedef {WikiJob | PublishedJob | StandardJob} ReconciliationJob */

/**
 * @typedef {object} ScopeState
 * @property {boolean} active
 * @property {Set<ReconciliationJob>} jobs
 * @property {AbortSignal | undefined} signal
 * @property {(() => void) | null} abortListener
 * @property {ReturnType<typeof createTrustedWikiSourcePathContext> | null} sourceContext
 * @property {StandardContext | null} standardContext
 */

/**
 * Coordinate every catalog-derived Markdown mutation for one rendered root.
 *
 * A root owns exactly one instance and injects it into transclusions. Catalog
 * notifications only invalidate the coordinator; snapshot selection, resolver
 * construction, catalog reads, and DOM callbacks all run inside the shared slice.
 * The first complete immutable snapshot is pinned for the mount so existing and
 * asynchronously-added nested content cannot observe different catalog revisions.
 * The first snapshot truncated at the inventory file cap is kept the same way, and
 * later truncated or partial revisions re-run nothing. A truncated revision cannot
 * rule out files past the cap, so a later complete revision still replaces it and
 * re-runs just the jobs that reported `catalog-truncated`.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {{schedule?: (callback: FrameRequestCallback) => number,
 *   cancel?: (handle: number) => void,
 *   reportError?: (error: unknown) => void}=} options
 */
export function createMarkdownReconciliationCoordinator(mb, options = {}) {
  const ownedScheduler = options.schedule ? null : createPostedTaskScheduler();
  const schedule =
    options.schedule ?? /** @type {NonNullable<typeof ownedScheduler>} */ (ownedScheduler).schedule;
  const cancel =
    options.cancel ??
    (ownedScheduler
      ? ownedScheduler.cancel
      : /** @param {number} handle */ (handle) => cancelAnimationFrame(handle));
  const reportError = options.reportError ?? defaultReportError;
  /** @type {Set<ReconciliationJob>} */
  const jobs = new Set();
  /** @type {Set<ReconciliationJob>} */
  const ready = new Set();
  /** @type {Set<() => void>} */
  const scopeDisposers = new Set();
  /** @type {Iterator<ReconciliationJob> | null} */
  let rescan = null;
  /** @type {ReturnType<MetabrowserPublicSdk["fileCatalog"]["snapshot"]> | null} */
  let snapshot = null;
  /** @type {WikiContext | null} */
  let wikiContext = null;
  /** @type {PublishedContext | null} */
  let publishedContext = null;
  /** @type {(() => void) | null} */
  let unsubscribe = null;
  /** @type {number | null} */
  let scheduledHandle = null;
  let disposed = false;
  let started = false;
  let dirty = true;
  let blocked = false;
  let pinned = false;
  let truncatedRevision = false;
  let generation = 0;

  function start() {
    if (started || disposed) {
      return;
    }
    started = true;
    // Subscribe before selecting the first snapshot. A mutation in between can
    // only set `dirty` again; it cannot be missed.
    unsubscribe = mb.fileCatalog.subscribe(catalogChanged);
    dirty = true;
  }

  function catalogChanged() {
    if (disposed || pinned) {
      return;
    }
    blocked = false;
    dirty = true;
    ensureScheduled();
  }

  function ensureScheduled() {
    if (disposed || blocked || scheduledHandle !== null) {
      return;
    }
    scheduledHandle = schedule(runSlice);
  }

  function refreshSnapshot() {
    if (!dirty || pinned) {
      return;
    }
    try {
      const next = mb.fileCatalog.snapshot();
      // Keep a selected truncated revision through later truncated and partial
      // revisions, such as the restarted walk after a reconnect; only a complete
      // walk can settle what it could not.
      if (next === snapshot || (truncatedRevision && !next.complete)) {
        dirty = false;
        return;
      }
      // Snapshot selection and resolver construction are staged before any
      // published generation is mutated or the previous context is disposed.
      const nextWikiContext = createWikiResolutionContext(next);
      const previousWikiContext = wikiContext;
      snapshot = next;
      wikiContext = nextWikiContext;
      publishedContext = null;
      dirty = false;
      blocked = false;
      generation += 1;
      rescan = jobs.values();
      previousWikiContext?.dispose();
      truncatedRevision = next.truncated === true;
      if (next.complete) {
        pinned = true;
        unsubscribe?.();
        unsubscribe = null;
      }
    } catch (error) {
      // An invalid provider revision is infrastructure failure, not a reason to
      // spin a frame forever. A later catalog notification may retry with a new
      // revision while the last successfully published generation stays intact.
      dirty = false;
      blocked = true;
      throw error;
    }
  }

  function takeReadyJob() {
    while (true) {
      const candidate = ready.values().next();
      if (!candidate.done) {
        const job = candidate.value;
        ready.delete(job);
        if (job.active && job.processedGeneration !== generation) {
          return job;
        }
        continue;
      }
      if (!rescan) {
        return null;
      }
      const scanned = rescan.next();
      if (scanned.done) {
        rescan = null;
        return null;
      }
      const job = scanned.value;
      if (job.active && job.processedGeneration !== generation) {
        return job;
      }
    }
  }

  function runSlice() {
    scheduledHandle = null;
    if (disposed) {
      return;
    }
    try {
      refreshSnapshot();
      if (!snapshot || !wikiContext) {
        return;
      }

      let elementVisits = 0;
      let remainingPathVisits = MAX_PATH_VISITS_PER_CALLBACK;
      while (elementVisits < MAX_ELEMENTS_PER_CALLBACK) {
        const job = takeReadyJob();
        if (!job) {
          break;
        }
        if (job.kind !== "published" && remainingPathVisits < 1) {
          ready.add(job);
          break;
        }
        elementVisits += 1;
        try {
          if (job.generation !== generation) {
            job.generation = generation;
            if (job.kind === "wiki") {
              job.application = null;
            }
          }
          if (job.kind === "wiki") {
            job.application ||= wikiContext.beginTrusted(
              job.intent,
              job.scope.sourceContext || undefined,
            );
            const step = job.application.step(remainingPathVisits);
            remainingPathVisits -= step.pathVisits;
            if (!step.done || !step.result) {
              ready.add(job);
              continue;
            }
            const shouldCommit = job.active && job.scope.active && !disposed;
            job.processedGeneration = generation;
            // An incomplete projection can both gain and lose exact paths. Keep
            // every catalog-derived wiki job until the first final revision so
            // early-present and early-absent states converge on the same pinned
            // snapshot rather than becoming permanent by arrival order.
            if (settlesJob(snapshot, step.result)) {
              removeJob(job);
            }
            if (shouldCommit) {
              job.commit(step.result);
            }
          } else if (job.kind === "standard") {
            const context = job.scope.standardContext;
            if (!context) {
              throw new Error("standard reconciliation requires a source-scoped context");
            }
            job.application ||= context.begin(job.intent);
            const step = job.application.step(remainingPathVisits);
            remainingPathVisits -= step.pathVisits;
            if (!step.done || !step.result) {
              ready.add(job);
              continue;
            }
            const shouldCommit = job.active && job.scope.active && !disposed;
            job.processedGeneration = generation;
            removeJob(job);
            if (shouldCommit) {
              job.commit(step.result);
            }
          } else {
            publishedContext ||= createPublishedRouteResolutionContext(snapshot);
            const result = publishedContext.resolve(job.intent);
            const shouldCommit = job.active && job.scope.active && !disposed;
            job.processedGeneration = generation;
            if (settlesJob(snapshot, result)) {
              removeJob(job);
            }
            if (shouldCommit) {
              job.commit(result);
            }
          }
        } catch (error) {
          // One malformed intent or consumer callback cannot starve the rest of a
          // root. Quarantine it permanently, report it, and continue within the
          // same aggregate budget.
          removeJob(job);
          safelyReport(error);
        }
      }
    } catch (error) {
      safelyReport(error);
    } finally {
      // In particular, a thrown job or reporter must not strand unrelated work
      // after this callback has already cleared `scheduledHandle`.
      if (!disposed && !blocked && (ready.size > 0 || rescan !== null)) {
        ensureScheduled();
      }
    }
  }

  /** @param {unknown} error */
  function safelyReport(error) {
    try {
      reportError(error);
    } catch (_reportingError) {
      // Diagnostics must not become a second poison job.
    }
  }

  /** @param {ReconciliationJob} job */
  function addJob(job) {
    if (disposed || !job.scope.active) {
      return () => {};
    }
    if (jobs.size >= MAX_RECONCILIATION_JOBS) {
      job.active = false;
      try {
        job.commit(
          Object.freeze({
            reason: "reconciliation-limit",
            status: /** @type {const} */ ("unsupported"),
          }),
        );
      } catch (error) {
        safelyReport(error);
      }
      return () => {};
    }
    start();
    jobs.add(job);
    job.scope.jobs.add(job);
    ready.add(job);
    ensureScheduled();
    return () => removeJob(job);
  }

  /** @param {ReconciliationJob} job */
  function removeJob(job) {
    if (!job.active) {
      return;
    }
    job.active = false;
    jobs.delete(job);
    ready.delete(job);
    job.scope.jobs.delete(job);
    if (job.kind === "wiki" || job.kind === "standard") {
      job.application = null;
    }
  }

  /** @param {AbortSignal=} signal @param {string=} sourcePath */
  function createScope(signal, sourcePath) {
    const active = !disposed && signal?.aborted !== true;
    const sourceContext =
      !active || sourcePath === undefined ? null : createTrustedWikiSourcePathContext(sourcePath);
    /** @type {ScopeState} */
    const state = {
      abortListener: null,
      active,
      jobs: new Set(),
      signal,
      sourceContext,
      standardContext:
        !active || sourcePath === undefined
          ? null
          : createTrustedStandardLinkResolutionContext(sourcePath, sourceContext || undefined),
    };

    function disposeScope() {
      if (!state.active) {
        return;
      }
      state.active = false;
      scopeDisposers.delete(disposeScope);
      for (const job of [...state.jobs]) {
        removeJob(job);
      }
      state.sourceContext?.dispose();
      state.sourceContext = null;
      state.standardContext = null;
      state.signal?.removeEventListener("abort", state.abortListener || (() => {}));
      state.abortListener = null;
    }

    if (state.active && signal) {
      state.abortListener = disposeScope;
      signal.addEventListener("abort", disposeScope, { once: true });
    }
    if (state.active) {
      scopeDisposers.add(disposeScope);
    }

    return Object.freeze({
      dispose: disposeScope,
      /** @param {unknown} intent @param {WikiJob["commit"]} commit */
      wiki(intent, commit) {
        if (typeof commit !== "function") {
          throw new TypeError("wiki reconciliation requires a commit callback");
        }
        /** @type {WikiJob} */
        const job = {
          active: true,
          application: null,
          commit,
          generation: 0,
          intent,
          kind: "wiki",
          processedGeneration: -1,
          scope: state,
        };
        return addJob(job);
      },
      /** @param {unknown} intent @param {PublishedJob["commit"]} commit */
      published(intent, commit) {
        if (typeof commit !== "function") {
          throw new TypeError("published-route reconciliation requires a commit callback");
        }
        /** @type {PublishedJob} */
        const job = {
          active: true,
          commit,
          generation: 0,
          intent,
          kind: "published",
          processedGeneration: -1,
          scope: state,
        };
        return addJob(job);
      },
      /** @param {unknown} intent @param {StandardJob["commit"]} commit */
      standard(intent, commit) {
        if (typeof commit !== "function") {
          throw new TypeError("standard-link reconciliation requires a commit callback");
        }
        /** @type {StandardJob} */
        const job = {
          active: true,
          application: null,
          commit,
          generation: 0,
          intent,
          kind: "standard",
          processedGeneration: -1,
          scope: state,
        };
        return addJob(job);
      },
    });
  }

  return Object.freeze({
    createScope,
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      if (scheduledHandle !== null) {
        cancel(scheduledHandle);
        scheduledHandle = null;
      }
      ownedScheduler?.dispose();
      for (const disposeScope of [...scopeDisposers]) {
        disposeScope();
      }
      scopeDisposers.clear();
      unsubscribe?.();
      unsubscribe = null;
      wikiContext?.dispose();
      wikiContext = null;
      publishedContext = null;
      snapshot = null;
      rescan = null;
      for (const job of jobs) {
        job.active = false;
        job.scope.jobs.delete(job);
        if (job.kind === "wiki" || job.kind === "standard") {
          job.application = null;
        }
      }
      jobs.clear();
      ready.clear();
    },
  });
}

/**
 * Pure catalog work advances through posted tasks rather than one animation frame
 * per slice. The measured 500k promotion needs 306 bounded slices: MessageChannel
 * preserves its ~206ms CPU completion instead of turning that into ~5.1s of frame
 * latency. DOM commits still occur only at slice boundaries.
 */
function createPostedTaskScheduler() {
  const Channel = globalThis.MessageChannel;
  let sequence = 0;
  /** @type {Map<number, FrameRequestCallback>} */
  const callbacks = new Map();
  if (typeof Channel !== "function") {
    return Object.freeze({
      /** @param {number} handle */
      cancel(handle) {
        const timer = /** @type {ReturnType<typeof setTimeout>} */ (handle);
        globalThis.clearTimeout(timer);
        callbacks.delete(handle);
      },
      dispose() {
        for (const handle of callbacks.keys()) {
          const timer = /** @type {ReturnType<typeof setTimeout>} */ (handle);
          globalThis.clearTimeout(timer);
        }
        callbacks.clear();
      },
      /** @param {FrameRequestCallback} callback */
      schedule(callback) {
        const handle = globalThis.setTimeout(() => {
          callbacks.delete(Number(handle));
          callback(performance.now());
        }, 0);
        const numericHandle = Number(handle);
        callbacks.set(numericHandle, callback);
        return numericHandle;
      },
    });
  }
  const channel = new Channel();
  channel.port1.onmessage = (event) => {
    const handle = Number(event.data);
    const callback = callbacks.get(handle);
    callbacks.delete(handle);
    callback?.(performance.now());
  };
  channel.port1.start?.();
  return Object.freeze({
    /** @param {number} handle */
    cancel(handle) {
      callbacks.delete(handle);
    },
    dispose() {
      callbacks.clear();
      channel.port1.close();
      channel.port2.close();
    },
    /** @param {FrameRequestCallback} callback */
    schedule(callback) {
      sequence += 1;
      callbacks.set(sequence, callback);
      channel.port2.postMessage(sequence);
      return sequence;
    },
  });
}

/**
 * Whether a committed result is final. A complete walk settles every result. A
 * walk truncated at the inventory file cap settles every result except
 * `catalog-truncated`; those jobs stay registered, without re-running on live
 * changes, until a complete revision can settle them.
 *
 * @param {ReturnType<MetabrowserPublicSdk["fileCatalog"]["snapshot"]>} snapshot
 * @param {unknown} result
 */
function settlesJob(snapshot, result) {
  const capped =
    typeof result === "object" &&
    result !== null &&
    "reason" in result &&
    result.reason === "catalog-truncated";
  return snapshot.complete || (snapshot.truncated === true && !capped);
}

/** @param {unknown} error */
function defaultReportError(error) {
  console.error("Markdown reconciliation job failed", error);
}
