// Quick File catalog feed: makes the known-file catalog complete.
//
// Bulk state comes from one gzipped `GET /api/catalog` fetch; live
// deltas arrive as `catalog.change` events on the existing inventory
// stream. Deltas observed before a bulk commit fold into that same staged
// transaction; larger steady-state changes use the same bounded scheduler.
// This module owns no EventSource and no DOM: app.js
// forwards stream events in, so the module is testable in Node with
// a stubbed fetch.

(() => {
  const RETRY_BASE_MS = 2_000;
  const RETRY_MAX_MS = 60_000;
  // The 300k exact-release profile for mb-gp3m measures and gates this ceiling.
  // Keep the item bound beside its production scheduler; the durable artifact
  // records elapsed timing rather than pretending item count is time.
  const BULK_APPLY_SLICE_ITEMS = 4_096;
  const perf = window.metabrowser?.perf || {
    measure: (_label, fn) => fn(),
    measureAsync: (_label, fn) => fn(),
  };

  /**
   * @typedef {object} BulkSnapshotApplication
   * @property {() => void} cancel
   * @property {(payload: CatalogChangePayload) => void} enqueueCatalogChange
   * @property {(ops: EventChangeOperation[]) => void} enqueueEventChange
   * @property {(maxWorkItems: number) => {cancelled: boolean, done: boolean,
   *   candidateVisits: number, workItems: number}} step
   */

  /**
   * @typedef {object} CatalogChangePayload
   * @property {Array<{p: string, e: string}>} [upserts]
   * @property {string[]} [removes]
   * @property {string[]} [remove_files]
   * @property {string[]} [non_file_paths]
   */

  /**
   * @typedef {object} EventChangeOperation
   * @property {{path: string, type: string, logical_ext?: string, gitignored?: boolean}} [entry]
   * @property {string} op
   * @property {string} [path]
   */

  /** @typedef {{kind: "catalog", payload: CatalogChangePayload} |
   *   {kind: "event", ops: EventChangeOperation[]}} PendingChange */

  /**
   * @typedef {object} CatalogFeedTarget
   * @property {(files: Array<{p: string, e: string}>, complete: boolean,
   *   authoritative?: boolean) => BulkSnapshotApplication} beginBulkSnapshot
   * @property {(payload: CatalogChangePayload, maxWorkItems: number) =>
   *   BulkSnapshotApplication | null} beginCatalogChange
   * @property {(ops: EventChangeOperation[], maxWorkItems: number) =>
   *   BulkSnapshotApplication | null} beginEventChange
   * @property {(payload: CatalogChangePayload) => {candidateVisits: number,
   *   changed: boolean, workItems: number}} applyCatalogChange
   * @property {(ops: EventChangeOperation[]) => {candidateVisits: number,
   *   changed: boolean, workItems: number}} applyEventChange
   * @property {() => void} markComplete
   * @property {() => void} markIncomplete
   */

  /**
   * @param {object} options
   * @param {CatalogFeedTarget} options.catalog
   * @param {string} [options.endpoint]
   * @param {typeof fetch} [options.fetchImpl]
   * @param {(callback: () => void, delayMs: number) => number} [options.scheduleRetry]
   * @param {(handle: number) => void} [options.cancelRetry]
   * @param {() => Promise<void>} [options.yieldControl]
   */
  function create(options) {
    const catalog = options.catalog;
    const endpoint = options.endpoint || "/api/catalog";
    const fetchImpl = options.fetchImpl || ((input) => fetch(input));
    const scheduleRetry =
      options.scheduleRetry || ((callback, delayMs) => window.setTimeout(callback, delayMs));
    const cancelRetry = options.cancelRetry || ((handle) => window.clearTimeout(handle));
    const taskYielder = options.yieldControl ? null : createTaskYielder();
    const yieldControl =
      options.yieldControl || taskYielder?.yieldControl || (() => Promise.resolve());

    /** @type {PendingChange[]} */
    let pendingChanges = [];
    let fetchSerial = 0;
    let fetchedOnce = false;
    let fetching = false;
    let retryAttempts = 0;
    /** @type {number | null} */
    let retryHandle = null;
    let disposed = false;
    let started = false;
    let refetchWanted = false;
    let suppressNextSentinelRefetch = false;
    let authoritativeRefetchPending = false;
    let terminalRefetchRequested = false;
    let lastBulkWasAuthoritative = false;
    let lastBulkHadCompleteCoverage = false;
    /** @type {BulkSnapshotApplication | null} */
    let activeBulkApplication = null;

    function clearRetry() {
      if (retryHandle !== null) {
        cancelRetry(retryHandle);
        retryHandle = null;
      }
    }

    /**
     * Drive one staged application through posted-task slices. `pendingChanges`
     * remains its cancellation journal until the atomic commit succeeds.
     * @param {BulkSnapshotApplication} application
     * @param {string} label
     * @param {number} files
     * @param {number | null} serial
     * @param {boolean} [firstPendingAlreadyQueued=false]
     */
    async function driveApplication(
      application,
      label,
      files,
      serial,
      firstPendingAlreadyQueued = false,
    ) {
      activeBulkApplication = application;
      for (const change of pendingChanges.slice(firstPendingAlreadyQueued ? 1 : 0)) {
        if (change.kind === "catalog") {
          application.enqueueCatalogChange(change.payload);
        } else {
          application.enqueueEventChange(change.ops);
        }
      }
      while (true) {
        if (
          disposed ||
          activeBulkApplication !== application ||
          (serial !== null && serial !== fetchSerial)
        ) {
          application.cancel();
          if (activeBulkApplication === application) {
            activeBulkApplication = null;
          }
          return false;
        }
        const metadata = { candidate_visits: 0, files, work_items: 0 };
        const result = perf.measure(
          label,
          () => {
            const step = application.step(BULK_APPLY_SLICE_ITEMS);
            metadata.candidate_visits = step.candidateVisits;
            metadata.work_items = step.workItems;
            return step;
          },
          metadata,
        );
        if (result.cancelled) {
          if (activeBulkApplication === application) {
            activeBulkApplication = null;
          }
          return false;
        }
        if (result.done) {
          if (activeBulkApplication === application) {
            activeBulkApplication = null;
          }
          // A fetch application has replayed the whole journal over its
          // payload. A steady change that finishes while a fetch is in flight
          // has not: that payload may predate changes journaled since, so keep
          // them for its replay. Replaying already-applied changes converges.
          if (serial !== null || !fetching) {
            pendingChanges = [];
          }
          return true;
        }
        await yieldControl();
      }
    }

    async function applyPendingChanges() {
      if (disposed || fetching || activeBulkApplication || pendingChanges.length === 0) {
        return;
      }
      while (!disposed && !fetching && !activeBulkApplication && pendingChanges.length > 0) {
        const change = pendingChanges[0];
        const application =
          change.kind === "catalog"
            ? catalog.beginCatalogChange(change.payload, BULK_APPLY_SLICE_ITEMS)
            : catalog.beginEventChange(change.ops, BULK_APPLY_SLICE_ITEMS);
        if (application) {
          await driveApplication(
            application,
            change.kind === "catalog"
              ? "knownFileCatalog:applyCatalogChange"
              : "knownFileCatalog:applyEventChange",
            0,
            null,
            true,
          );
          return;
        }
        pendingChanges.shift();
        const metadata = { candidate_visits: 0, work_items: 0 };
        perf.measure(
          change.kind === "catalog"
            ? "knownFileCatalog:applyCatalogChange"
            : "knownFileCatalog:applyEventChange",
          () => {
            const result =
              change.kind === "catalog"
                ? catalog.applyCatalogChange(change.payload)
                : catalog.applyEventChange(change.ops);
            metadata.candidate_visits = result.candidateVisits;
            metadata.work_items = result.workItems;
          },
          metadata,
        );
      }
    }

    async function runFetch() {
      if (disposed || fetching) {
        return;
      }
      fetching = true;
      clearRetry();
      fetchSerial += 1;
      const serial = fetchSerial;
      try {
        const response = await fetchImpl(endpoint);
        if (disposed || serial !== fetchSerial) {
          return;
        }
        // 304 means the catalog is unchanged since the last applied
        // payload; buffered deltas still replay below so nothing on
        // the live path is lost.
        if (response.status !== 304) {
          if (!response.ok) {
            throw new Error(`catalog fetch failed: ${response.status}`);
          }
          const responseMetadata = {
            content_length: Number(response.headers?.get?.("content-length")) || null,
            content_encoding: response.headers?.get?.("content-encoding") || null,
          };
          const body = await perf.measureAsync(
            "apiCatalog:body",
            () => response.text(),
            responseMetadata,
          );
          const payload = perf.measure("apiCatalog:parse", () => JSON.parse(body), {
            characters: body.length,
          });
          if (disposed || serial !== fetchSerial) {
            return;
          }
          // The payload's two flags answer different questions, and a
          // finished-but-capped walk answers them oppositely.
          //
          // Coverage: `complete` means the walk finished, `truncated` means it
          // finished by hitting the max-files cap. Files past the cap were
          // never indexed and can never be searched, so a truncated catalog is
          // complete for the index and permanently incomplete for the root.
          // Forwarding `complete` alone told the user "N files" while hiding
          // everything beyond the cap.
          //
          // Authority: either way the walk stopped, so the payload lists every
          // file the index holds. That makes it authoritative membership, and
          // the catalog may retire feed-sourced paths it no longer names —
          // which is how a refetch expresses a deletion that happened while
          // the stream was down. A payload built mid-walk is only a prefix and
          // must merge instead.
          const authoritative = payload.complete === true;
          const completeCoverage = authoritative && payload.truncated !== true;
          const files = Array.isArray(payload.files) ? payload.files : [];
          const application = catalog.beginBulkSnapshot(files, completeCoverage, authoritative);
          if (
            !(await driveApplication(
              application,
              "knownFileCatalog:applyBulkSnapshot",
              files.length,
              serial,
            ))
          ) {
            return;
          }
          lastBulkWasAuthoritative = authoritative;
          lastBulkHadCompleteCoverage = completeCoverage;
          if (authoritative) {
            authoritativeRefetchPending = false;
            terminalRefetchRequested = false;
          }
        } else if (lastBulkWasAuthoritative) {
          const application = catalog.beginBulkSnapshot([], lastBulkHadCompleteCoverage, false);
          if (
            !(await driveApplication(application, "knownFileCatalog:applyBulkSnapshot", 0, serial))
          ) {
            return;
          }
          authoritativeRefetchPending = false;
        }
        fetchedOnce = true;
        retryAttempts = 0;
      } catch (_error) {
        activeBulkApplication?.cancel();
        activeBulkApplication = null;
        if (disposed || serial !== fetchSerial) {
          return;
        }
        // The stream keeps buffering deltas while we retry, so a
        // transient failure delays completeness without losing data.
        retryAttempts += 1;
        const delayMs = Math.min(RETRY_MAX_MS, RETRY_BASE_MS * 2 ** (retryAttempts - 1));
        retryHandle = scheduleRetry(() => {
          retryHandle = null;
          void runFetch();
        }, delayMs);
      } finally {
        fetching = false;
        // A refetch requested while this fetch was in flight ran
        // into the `fetching` guard; honor it now so no request is
        // ever silently swallowed.
        if (refetchWanted && !disposed) {
          refetchWanted = false;
          void runFetch();
        } else if (!disposed && fetchedOnce && pendingChanges.length > 0) {
          void applyPendingChanges();
        }
      }
    }

    /**
     * Invalidate any in-flight fetch and ensure a fresh one runs.
     * Bumping the serial makes an in-flight response stale at every
     * checkpoint, so a payload built before the trigger (a stream
     * reconnect or a root swap) can never apply afterward; the
     * follow-up fetch is queued from the in-flight call's cleanup
     * rather than dropped by its `fetching` guard.
     */
    function requestRefetch() {
      fetchSerial += 1;
      if (fetching) {
        refetchWanted = true;
      } else {
        void runFetch();
      }
    }

    /** Require the next accepted bulk payload to establish membership. */
    function requestContinuityRefetch() {
      // A continuity boundary makes every delta buffered before it ambiguous:
      // the disconnected stream may have omitted a later inverse operation.
      // Rotate the buffer before invalidating the fetch so only events from
      // the new continuity generation replay over its authoritative payload.
      // Ordinary fetch retries and terminal completion refetches do not take
      // this path and therefore keep their ordered buffers.
      pendingChanges = [];
      activeBulkApplication?.cancel();
      activeBulkApplication = null;
      authoritativeRefetchPending = true;
      terminalRefetchRequested = false;
      catalog.markIncomplete();
      requestRefetch();
    }

    /**
     * Call on every event-stream open. The first open begins the
     * bulk fetch after subscription; later opens establish continuity
     * with a fresh fetch before their sentinel arrives. Remembering
     * that the next sentinel belongs to this open avoids a duplicate
     * fetch while still letting an unexpected sentinel trigger repair.
     */
    function start() {
      if (disposed) {
        return;
      }
      suppressNextSentinelRefetch = true;
      if (started) {
        requestContinuityRefetch();
        return;
      }
      started = true;
      void runFetch();
    }

    /**
     * A `catalog.change` event arrived on the stream. Applied
     * directly once the bulk payload has landed; buffered before
     * that so replay order preserves convergence.
     * @param {CatalogChangePayload} payload
     */
    function onCatalogChange(payload) {
      if (disposed || !payload) {
        return;
      }
      const change = { kind: /** @type {const} */ ("catalog"), payload };
      pendingChanges.push(change);
      if (activeBulkApplication) {
        activeBulkApplication.enqueueCatalogChange(payload);
      } else if (fetchedOnce && !fetching) {
        void applyPendingChanges();
      }
    }

    /** Route the general fs.change seam through the same bounded scheduler.
     * @param {EventChangeOperation[]} ops
     */
    function onEventChange(ops) {
      if (disposed || !Array.isArray(ops) || ops.length === 0) {
        return;
      }
      const change = { kind: /** @type {const} */ ("event"), ops };
      pendingChanges.push(change);
      if (activeBulkApplication) {
        activeBulkApplication.enqueueEventChange(ops);
      } else if (fetchedOnce && !fetching) {
        void applyPendingChanges();
      }
    }

    /**
     * The stream delivered a fresh id=0 snapshot. A snapshot paired
     * with `start()` belongs to the open already handled there. An
     * unpaired snapshot means continuity changed without a reported
     * open, so refetch defensively.
     */
    function onSentinelSnapshot() {
      if (disposed || !started) {
        return;
      }
      if (suppressNextSentinelRefetch) {
        suppressNextSentinelRefetch = false;
        return;
      }
      requestContinuityRefetch();
    }

    /** Root swap: the catalog was cleared by the caller; rebuild it. */
    function onResync() {
      if (disposed) {
        return;
      }
      pendingChanges = [];
      fetchedOnce = false;
      lastBulkWasAuthoritative = false;
      lastBulkHadCompleteCoverage = false;
      requestContinuityRefetch();
    }

    /**
     * The walker reached a terminal state after an incomplete bulk
     * fetch. After a reconnect, deletions from the gap require one
     * terminal, authoritative payload even when the walk stopped at
     * its file cap. Only an uncapped walk establishes full coverage.
     * @param {boolean} [truncated=false]
     */
    function onIndexComplete(truncated = false) {
      if (disposed) {
        return;
      }
      if (authoritativeRefetchPending) {
        // Completion can arrive from both the SSE capability event and the
        // independent progress poll. One authoritative refetch repairs the
        // current continuity gap; duplicate terminal signals must not download
        // the full catalog again.
        if (!terminalRefetchRequested) {
          terminalRefetchRequested = true;
          requestRefetch();
        }
        return;
      }
      if (!truncated) {
        catalog.markComplete();
      }
    }

    function dispose() {
      disposed = true;
      clearRetry();
      pendingChanges = [];
      activeBulkApplication?.cancel();
      activeBulkApplication = null;
      taskYielder?.dispose();
    }

    return Object.freeze({
      dispose,
      onCatalogChange,
      onEventChange,
      onIndexComplete,
      onResync,
      onSentinelSnapshot,
      start,
    });
  }

  /**
   * Yield with a posted task instead of a nested timer. Browsers clamp a long
   * chain of zero-delay timers, which would turn safe slices into avoidable
   * end-to-end catalog latency.
   */
  function createTaskYielder() {
    if (typeof MessageChannel !== "function") {
      return Object.freeze({
        dispose() {},
        yieldControl: () => new Promise((resolve) => window.setTimeout(resolve, 0)),
      });
    }
    const channel = new MessageChannel();
    /** @type {Array<() => void>} */
    const pending = [];
    let disposed = false;
    channel.port1.onmessage = () => {
      pending.shift()?.();
    };
    return Object.freeze({
      dispose() {
        disposed = true;
        channel.port1.close();
        channel.port2.close();
        for (const resolve of pending.splice(0)) {
          resolve();
        }
      },
      yieldControl() {
        if (disposed) {
          return Promise.resolve();
        }
        return new Promise((resolve) => {
          pending.push(() => resolve(undefined));
          channel.port2.postMessage(null);
        });
      },
    });
  }

  window.MetabrowserCatalogFeed = Object.freeze({ BULK_APPLY_SLICE_ITEMS, create });
})();
