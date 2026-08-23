// Quick File catalog feed: makes the known-file catalog complete.
//
// Bulk state comes from one gzipped `GET /api/catalog` fetch; live
// deltas arrive as `catalog.change` events on the existing inventory
// stream. The two converge without a shared transaction because ops
// are idempotent by path — provided deltas observed before the bulk
// payload applies are buffered and replayed after it, which is this
// module's whole job. It owns no EventSource and no DOM: app.js
// forwards stream events in, so the module is testable in Node with
// a stubbed fetch.

(() => {
  const RETRY_BASE_MS = 2_000;
  const RETRY_MAX_MS = 60_000;
  const perf = window.metabrowser?.perf || {
    measure: (_label, fn) => fn(),
    measureAsync: (_label, fn) => fn(),
  };

  /**
   * @typedef {object} CatalogFeedTarget
   * @property {(files: Array<{p: string, e: string}>, complete: boolean,
   *   authoritative?: boolean) => void} applyBulkSnapshot
   * @property {(payload: {upserts?: Array<{p: string, e: string}>, removes?: string[],
   *   remove_files?: string[]}) => void} applyCatalogChange
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
   */
  function create(options) {
    const catalog = options.catalog;
    const endpoint = options.endpoint || "/api/catalog";
    const fetchImpl = options.fetchImpl || ((input) => fetch(input));
    const scheduleRetry =
      options.scheduleRetry || ((callback, delayMs) => window.setTimeout(callback, delayMs));
    const cancelRetry = options.cancelRetry || ((handle) => window.clearTimeout(handle));

    /** @type {Array<{upserts?: Array<{p: string, e: string}>, removes?: string[],
     *   remove_files?: string[]}>} */
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
    let lastBulkWasAuthoritative = false;
    let lastBulkHadCompleteCoverage = false;

    function clearRetry() {
      if (retryHandle !== null) {
        cancelRetry(retryHandle);
        retryHandle = null;
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
          const payload = await perf.measureAsync("apiCatalog:json", () => response.json(), {
            content_length: Number(response.headers?.get?.("content-length")) || null,
            content_encoding: response.headers?.get?.("content-encoding") || null,
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
          perf.measure(
            "knownFileCatalog:applyBulkSnapshot",
            () =>
              catalog.applyBulkSnapshot(
                Array.isArray(payload.files) ? payload.files : [],
                completeCoverage,
                authoritative,
              ),
            { files: Array.isArray(payload.files) ? payload.files.length : 0 },
          );
          lastBulkWasAuthoritative = authoritative;
          lastBulkHadCompleteCoverage = completeCoverage;
          if (authoritative) {
            authoritativeRefetchPending = false;
          }
        } else if (lastBulkWasAuthoritative) {
          authoritativeRefetchPending = false;
          if (lastBulkHadCompleteCoverage) {
            catalog.markComplete();
          }
        }
        fetchedOnce = true;
        retryAttempts = 0;
        const replay = pendingChanges;
        pendingChanges = [];
        for (const change of replay) {
          catalog.applyCatalogChange(change);
        }
      } catch (_error) {
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
      authoritativeRefetchPending = true;
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
     * @param {{upserts?: Array<{p: string, e: string}>, removes?: string[],
     *   remove_files?: string[]}} payload
     */
    function onCatalogChange(payload) {
      if (disposed || !payload) {
        return;
      }
      if (fetchedOnce && !fetching) {
        catalog.applyCatalogChange(payload);
      } else {
        pendingChanges.push(payload);
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
        requestRefetch();
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
    }

    return Object.freeze({
      dispose,
      onCatalogChange,
      onIndexComplete,
      onResync,
      onSentinelSnapshot,
      start,
    });
  }

  window.MetabrowserCatalogFeed = Object.freeze({ create });
})();
