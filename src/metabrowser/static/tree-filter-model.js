// The navigation filter's browser-owned model.
//
// Data membership belongs to the inventory provider. This module serializes one
// filter snapshot for /api/tree or /api/recent, then turns the complete Recent
// leaf answer plus live updates into the presentation tree app.js renders.
// Nothing here reads mounted DOM rows. Rendering may collapse, cache, or page a
// subtree without changing whether that subtree exists.

(() => {
  /**
   * @typedef {object} FilterSnapshot
   * @property {string} recency
   * @property {string[] | null} types
   * @property {string} size
   * @property {boolean} showIgnored
   */

  /**
   * @typedef {object} RecentEntry
   * @property {string} path
   * @property {"file"} type
   * @property {string} [name]
   * @property {string} [ext]
   * @property {string} [logical_ext]
   * @property {number} [size]
   * @property {number} [mtime]
   * @property {boolean} [gitignored]
   */

  /**
   * @typedef {object} FilterStateApi
   * @property {(row: {mtime?: number, size?: number, path?: string, ext?: string}, state: FilterSnapshot, nowSec: number) => boolean} rowMatches
   */

  /**
   * @typedef {object} RecentRequest
   * @property {boolean} dirty
   * @property {string} key
   */

  /**
   * @typedef {object} RecentRefetch
   * @property {boolean} [preserveRows]
   * @property {string} requestKey
   * @property {string} windowKey
   */

  /**
   * @typedef {object} RecentFilterCursor
   * @property {string} recentRequestKey
   * @property {"recent" | "tree"} source
   * @property {string} treeRequestKey
   * @property {string} windowKey
   */

  /**
   * @typedef {object} RecentLoad
   * @property {RecentFilterCursor} cursor
   * @property {RecentRequest} request
   * @property {RecentRefetch} repair
   * @property {string} url
   */

  /**
   * @typedef {object} RecentFilterTransition
   * @property {"apply" | "load-recent" | "load-tree" | "refetch-recent"} action
   * @property {RecentFilterCursor} current
   */

  /**
   * @typedef {object} CatalogChange
   * @property {string[]} [non_file_paths]
   * @property {Array<{p: string, e?: string}>} [upserts]
   * @property {string[]} [removes]
   * @property {string[]} [remove_files]
   */

  /**
   * @typedef {object} RecentCatalogEffect
   * @property {boolean} changed
   * @property {boolean} needsAuthoritativeRepair
   * @property {number} removedEntries
   * @property {number | null} retainedLowerBound
   */

  /**
   * @typedef {object} RemovalPrefixTrie
   * @property {Map<string, RemovalPrefixTrie>} children
   * @property {boolean} terminal
   */

  /**
   * @typedef {object} RecentFsEntry
   * @property {string} path
   * @property {string} type
   * @property {string} [name]
   * @property {number} [size]
   * @property {number} [mtime_ns]
   * @property {string} [ext]
   * @property {boolean} [gitignored]
   */

  /**
   * @typedef {{op: "upsert", entry: RecentFsEntry} | {op: "remove", path: string}} RecentFsChange
   */

  /**
   * @typedef {object} RecentContinuityOptions
   * @property {number} delayMs
   * @property {number} retryBaseMs
   * @property {number} maxRetryDelayMs
   * @property {number} maxRetries
   * @property {(request: RecentRefetch) => void} onRepair
   * @property {(status: "fresh" | "retrying" | "stale") => void} [onStatus]
   * @property {{clearTimeout: (handle: any) => void, setTimeout: (callback: () => void, delayMs: number) => any}} clock
   */

  /**
   * Compare canonical inventory paths by their UTF-8 byte order.
   *
   * Canonical paths contain Unicode scalars plus ASCII escapes for invalid
   * platform names. UTF-8 preserves scalar order, so a code-point walk gives
   * the contract's byte order without allocating encoded buffers per compare.
   * Locale collation is deliberately wrong here: for example, it commonly
   * sorts `a` before `Z`, while their canonical bytes require `Z` first.
   *
   * @param {string} left
   * @param {string} right
   */
  function canonicalPathCompare(left, right) {
    if (left === right) {
      return 0;
    }
    let leftIndex = 0;
    let rightIndex = 0;
    while (leftIndex < left.length && rightIndex < right.length) {
      const leftPoint = /** @type {number} */ (left.codePointAt(leftIndex));
      const rightPoint = /** @type {number} */ (right.codePointAt(rightIndex));
      if (leftPoint !== rightPoint) {
        return leftPoint < rightPoint ? -1 : 1;
      }
      leftIndex += leftPoint > 0xffff ? 2 : 1;
      rightIndex += rightPoint > 0xffff ? 2 : 1;
    }
    return leftIndex < left.length ? 1 : -1;
  }

  /**
   * The non-recency dimensions shared by `/api/tree` and `/api/recent`.
   * Recency names the Recent route itself; the route receives it as `window`.
   *
   * @param {FilterSnapshot | null} state
   * @param {Record<string, number>} sizeFloors bucket name -> minimum bytes
   * @returns {string[]}
   */
  function requestParams(state, sizeFloors) {
    /** @type {string[]} */
    const params = [];
    if (!state) {
      return params;
    }
    if (state.types && state.types.length > 0) {
      const types = Array.from(new Set(state.types)).sort(canonicalPathCompare);
      params.push(`types=${encodeURIComponent(types.join(","))}`);
    }
    const floor = sizeFloors?.[state.size];
    if (floor) {
      params.push(`min_size=${floor}`);
    }
    if (state.showIgnored === false) {
      params.push("include_ignored=0");
    }
    return params;
  }

  /**
   * Identity of a tree filter selection, for caching a fetched subtree against
   * the selection it was fetched under.
   *
   * @param {FilterSnapshot | null} state
   * @param {Record<string, number>} sizeFloors
   */
  function requestKey(state, sizeFloors) {
    return requestParams(state, sizeFloors).join("&");
  }

  /**
   * @param {string} path
   * @param {FilterSnapshot | null} state
   * @param {Record<string, number>} sizeFloors
   * @param {string[]} [extraParams]
   */
  function treeUrl(path, state, sizeFloors, extraParams) {
    const params = requestParams(state, sizeFloors).concat(extraParams || []);
    if (path) {
      params.unshift(`path=${encodeURIComponent(path)}`);
    }
    return params.length > 0 ? `/api/tree?${params.join("&")}` : "/api/tree";
  }

  /**
   * The exact Recent request the browser makes. Filters precede the provider's
   * ranking and cap, so a narrow selection cannot spend its page on nonmatches.
   *
   * @param {string} windowKey
   * @param {number} limit
   * @param {FilterSnapshot | null} state
   * @param {Record<string, number>} sizeFloors
   */
  function recentUrl(windowKey, limit, state, sizeFloors) {
    const params = [
      `window=${encodeURIComponent(windowKey)}`,
      `limit=${encodeURIComponent(String(limit))}`,
      ...requestParams(state, sizeFloors),
    ];
    return `/api/recent?${params.join("&")}`;
  }

  /**
   * @param {string} windowKey
   * @param {number} limit
   * @param {FilterSnapshot | null} state
   * @param {Record<string, number>} sizeFloors
   */
  function recentRequestKey(windowKey, limit, state, sizeFloors) {
    return recentUrl(windowKey, limit, state, sizeFloors);
  }

  /**
   * Snapshot the complete navigation-filter identity consumed by the shell.
   * The control transition and request launch share this value, so a later
   * integration cannot accidentally refetch only the recency dimension.
   *
   * @param {FilterSnapshot | null} state
   * @param {number} limit
   * @param {Record<string, number>} sizeFloors
   * @returns {RecentFilterCursor}
   */
  function recentFilterCursor(state, limit, sizeFloors) {
    const windowKey = state?.recency || "all";
    return {
      recentRequestKey: recentRequestKey(windowKey, limit, state, sizeFloors),
      source: windowKey === "all" ? "tree" : "recent",
      treeRequestKey: requestKey(state, sizeFloors),
      windowKey,
    };
  }

  /**
   * Decide the one application action caused by a filter-control transition.
   * Window/source changes load immediately; same-window Recent changes may be
   * coalesced because they can otherwise launch repeated whole-index scans.
   *
   * @param {RecentFilterCursor | null} previous
   * @param {RecentFilterCursor} current
   * @returns {RecentFilterTransition}
   */
  function recentFilterTransition(previous, current) {
    if (current.source === "recent") {
      if (previous?.source !== "recent" || previous.windowKey !== current.windowKey) {
        return { action: "load-recent", current };
      }
      if (previous.recentRequestKey !== current.recentRequestKey) {
        return { action: "refetch-recent", current };
      }
    } else if (previous?.source !== "tree" || previous.treeRequestKey !== current.treeRequestKey) {
      return { action: "load-tree", current };
    }
    return { action: "apply", current };
  }

  /**
   * Begin the exact request selected by the filter-control transition.
   *
   * @param {ReturnType<typeof createRecentContinuity>} continuity
   * @param {RecentFilterCursor} cursor
   * @param {boolean} preserveRows
   * @returns {RecentLoad}
   */
  function beginRecentRequest(continuity, cursor, preserveRows) {
    if (cursor.source !== "recent") {
      throw new Error("Recent requests require a recent-source filter cursor");
    }
    continuity.abandonRequest();
    const request = continuity.startRequest(cursor.recentRequestKey);
    return {
      cursor,
      request,
      repair: {
        preserveRows,
        requestKey: cursor.recentRequestKey,
        windowKey: cursor.windowKey,
      },
      url: cursor.recentRequestKey,
    };
  }

  /** @param {string} key @returns {RecentRequest} */
  function createRecentRequest(key) {
    return { dirty: false, key };
  }

  /** @param {RecentRequest | null} request */
  function dirtyRecentRequest(request) {
    if (request) {
      request.dirty = true;
    }
  }

  /**
   * Decide whether an HTTP snapshot still describes the event stream state.
   * There is no cursor shared by these transports, so a dirty snapshot must be
   * replaced rather than patched with blindly replayed operations.
   *
   * @param {RecentRequest | null} active
   * @param {RecentRequest} request
   * @returns {"commit" | "refetch" | "superseded"}
   */
  function recentRequestDisposition(active, request) {
    if (active !== request) {
      return "superseded";
    }
    return request.dirty ? "refetch" : "commit";
  }

  /**
   * Decide how an authoritative Recent invalidation composes with work that
   * already exists. Both the event handler and the repair timer use this same
   * decision so a timer cannot race a newer request and start a duplicate
   * provider scan.
   *
   * @param {boolean} recentActive
   * @param {boolean} requestInFlight
   * @param {boolean} filterRefetchPending
   * @returns {"ignore" | "dirty" | "covered" | "repair"}
   */
  function recentRepairDisposition(recentActive, requestInFlight, filterRefetchPending) {
    if (!recentActive) {
      return "ignore";
    }
    if (requestInFlight) {
      return "dirty";
    }
    return filterRefetchPending ? "covered" : "repair";
  }

  /**
   * A trailing-edge scheduler for filter-driven Recent refetches. Initial,
   * source, and window loads bypass it in app.js; repeated type/size changes
   * coalesce here before they launch an O(N) provider scan.
   *
   * @param {number} delayMs
   * @param {(request: RecentRefetch) => void} callback
   * @param {{clearTimeout: (handle: any) => void, setTimeout: (callback: () => void, delayMs: number) => any}} clock
   */
  function createRecentRefetchScheduler(delayMs, callback, clock) {
    /** @type {any} */
    let handle = null;
    function cancel() {
      if (handle !== null) {
        clock.clearTimeout(handle);
        handle = null;
      }
    }
    return Object.freeze({
      cancel,
      pending() {
        return handle !== null;
      },
      /** @param {RecentRefetch} request */
      schedule(request) {
        cancel();
        handle = clock.setTimeout(() => {
          handle = null;
          callback(request);
        }, delayMs);
      },
    });
  }

  /**
   * Coalesce live-overlay repaints for one Recent request identity.
   *
   * Source, window, and filter transitions cancel the pending timer in the
   * application. The generation and current-identity checks are the second
   * line of defence for a callback already queued by the browser when that
   * cancellation happens.
   *
   * @param {number} delayMs
   * @param {(request: RecentRefetch) => void} callback
   * @param {(request: RecentRefetch) => boolean} isCurrent
   * @param {{clearTimeout: (handle: any) => void, setTimeout: (callback: () => void, delayMs: number) => any}} clock
   */
  function createRecentRecomputeScheduler(delayMs, callback, isCurrent, clock) {
    /** @type {any} */
    let handle = null;
    /** @type {RecentRefetch | null} */
    let pending = null;
    let generation = 0;

    function cancel() {
      generation += 1;
      if (handle !== null) {
        clock.clearTimeout(handle);
      }
      handle = null;
      pending = null;
    }

    /** @param {RecentRefetch} request */
    function schedule(request) {
      if (handle !== null && pending) {
        if (pending.windowKey === request.windowKey && pending.requestKey === request.requestKey) {
          return "coalesced";
        }
        cancel();
      }
      pending = request;
      generation += 1;
      const scheduledGeneration = generation;
      handle = clock.setTimeout(() => {
        if (scheduledGeneration !== generation) {
          return;
        }
        handle = null;
        pending = null;
        generation += 1;
        if (isCurrent(request)) {
          callback(request);
        }
      }, delayMs);
      return "scheduled";
    }

    return Object.freeze({
      cancel,
      pending() {
        return handle !== null;
      },
      schedule,
    });
  }

  /**
   * A fixed-window coalescer for authoritative repairs after live events.
   *
   * Unlike the trailing filter scheduler above, a continuous writer must not
   * postpone convergence forever. The first invalidation starts one timer;
   * later invalidations only replace its constant-size request descriptor.
   * The continuity controller dirties an active request, so repair
   * invalidations never deliberately overlap it and only one repair is
   * pending.
   *
   * @param {number} delayMs
   * @param {(request: RecentRefetch) => void} callback
   * @param {{clearTimeout: (handle: any) => void, setTimeout: (callback: () => void, delayMs: number) => any}} clock
   */
  function createRecentRepairScheduler(delayMs, callback, clock) {
    /** @type {any} */
    let handle = null;
    /** @type {RecentRefetch | null} */
    let latest = null;
    function cancel() {
      if (handle !== null) {
        clock.clearTimeout(handle);
      }
      handle = null;
      latest = null;
    }
    return Object.freeze({
      cancel,
      pending() {
        return handle !== null;
      },
      /**
       * @param {RecentRefetch} request
       * @param {number} [requestedDelayMs]
       */
      schedule(request, requestedDelayMs) {
        latest = request;
        if (handle !== null) {
          return;
        }
        const waitMs = Number.isFinite(requestedDelayMs) ? requestedDelayMs : delayMs;
        handle = clock.setTimeout(
          () => {
            handle = null;
            const pending = latest;
            latest = null;
            if (pending) {
              callback(pending);
            }
          },
          /** @type {number} */ (waitMs),
        );
      },
    });
  }

  /**
   * Coordinate Recent request identity, live invalidation, sentinel coverage,
   * and bounded repair retries. Keeping these transitions in the production
   * model lets the browserless session exercise the same lifecycle as app.js.
   *
   * @param {RecentContinuityOptions} options
   */
  function createRecentContinuity(options) {
    /** @type {RecentRequest | null} */
    let activeRequest = null;
    let sentinelSeen = false;
    /** @type {string | null} */
    let repairIdentity = null;
    let retryCount = 0;
    let exhausted = false;
    /** @type {"fresh" | "retrying" | "stale"} */
    let repairStatus = "fresh";

    const scheduler = createRecentRepairScheduler(options.delayMs, options.onRepair, options.clock);

    /** @param {RecentRefetch} request */
    function identityOf(request) {
      return `${request.windowKey}\u0000${request.requestKey}`;
    }

    /** @param {"fresh" | "retrying" | "stale"} status */
    function setStatus(status) {
      if (repairStatus === status) {
        return;
      }
      repairStatus = status;
      options.onStatus?.(status);
    }

    /** @param {RecentRefetch} request */
    function prepareRepair(request) {
      const identity = identityOf(request);
      if (repairIdentity === identity) {
        return;
      }
      scheduler.cancel();
      repairIdentity = identity;
      retryCount = 0;
      exhausted = false;
      setStatus("fresh");
    }

    /**
     * @param {RecentRefetch} request
     * @param {number} [delayMs]
     * @param {boolean} [restartExhausted]
     * @returns {"scheduled" | "coalesced" | "exhausted"}
     */
    function scheduleRepair(request, delayMs, restartExhausted) {
      prepareRepair(request);
      if (exhausted) {
        if (!restartExhausted) {
          return "exhausted";
        }
        // Exhaustion stops autonomous retries. A later authoritative event is
        // new evidence that recovery may now succeed, so it may open one new
        // bounded episode without allowing the old one to loop by itself.
        retryCount = 0;
        exhausted = false;
        setStatus("retrying");
      }
      const wasPending = scheduler.pending();
      scheduler.schedule(request, delayMs);
      return wasPending ? "coalesced" : "scheduled";
    }

    /** @param {string} key */
    function startRequest(key) {
      activeRequest = createRecentRequest(key);
      return activeRequest;
    }

    /** @param {RecentRequest | null} [request] */
    function abandonRequest(request) {
      if (!request || activeRequest === request) {
        activeRequest = null;
      }
    }

    function dirtyActiveRequest() {
      dirtyRecentRequest(activeRequest);
    }

    /**
     * Settle identity before the caller commits and renders. A synchronous
     * expiry discovered by that render must see no active request, otherwise
     * it would dirty the already-accepted response and lose its repair.
     *
     * @param {RecentRequest} request
     */
    function settleRequest(request) {
      const disposition = recentRequestDisposition(activeRequest, request);
      if (activeRequest === request) {
        activeRequest = null;
      }
      return disposition;
    }

    /**
     * @param {boolean} recentActive
     * @param {boolean} filterRefetchPending
     * @param {RecentRefetch} request
     */
    function invalidate(recentActive, filterRefetchPending, request) {
      const disposition = recentRepairDisposition(
        recentActive,
        activeRequest !== null,
        filterRefetchPending,
      );
      if (disposition === "dirty") {
        dirtyActiveRequest();
      } else if (disposition === "repair") {
        scheduleRepair(request, undefined, true);
      }
      return disposition;
    }

    /**
     * Recheck when a queued repair becomes runnable. A newer request may have
     * started since the timer was armed, so the timer dirties it rather than
     * launching overlapping work.
     *
     * @param {boolean} recentActive
     * @param {boolean} filterRefetchPending
     */
    function repairReady(recentActive, filterRefetchPending) {
      const disposition = recentRepairDisposition(
        recentActive,
        activeRequest !== null,
        filterRefetchPending,
      );
      if (disposition === "dirty") {
        dirtyActiveRequest();
      }
      return disposition;
    }

    /**
     * @param {boolean} recentActive
     * @param {boolean} filterRefetchPending
     * @param {RecentRefetch} request
     */
    function observeSentinel(recentActive, filterRefetchPending, request) {
      const phase = sentinelSeen ? "reconnect" : "baseline";
      sentinelSeen = true;
      return Object.freeze({
        phase,
        disposition: invalidate(recentActive, filterRefetchPending, request),
      });
    }

    /**
     * @param {RecentRefetch} request
     * @param {boolean} retryable
     * @returns {"ignored" | "retrying" | "stale"}
     */
    function repairFailed(request, retryable) {
      if (repairIdentity !== identityOf(request)) {
        return "ignored";
      }
      if (!retryable || retryCount >= options.maxRetries) {
        scheduler.cancel();
        exhausted = true;
        setStatus("stale");
        return "stale";
      }
      const delayMs = Math.min(options.retryBaseMs * 2 ** retryCount, options.maxRetryDelayMs);
      retryCount += 1;
      setStatus("retrying");
      scheduleRepair(request, delayMs);
      return "retrying";
    }

    /** @param {RecentRefetch} request */
    function repairSucceeded(request) {
      scheduler.cancel();
      repairIdentity = identityOf(request);
      retryCount = 0;
      exhausted = false;
      setStatus("fresh");
    }

    function cancelRepairs() {
      scheduler.cancel();
      repairIdentity = null;
      retryCount = 0;
      exhausted = false;
      setStatus("fresh");
    }

    return Object.freeze({
      abandonRequest,
      cancelRepairs,
      dirtyActiveRequest,
      hasActiveRequest() {
        return activeRequest !== null;
      },
      invalidate,
      observeSentinel,
      pending: scheduler.pending,
      repairFailed,
      repairReady,
      repairSucceeded,
      scheduleRepair,
      startRequest,
      status() {
        return repairStatus;
      },
      settleRequest,
    });
  }

  /** @param {string} path */
  function inventoryPathDepth(path) {
    return path ? path.split("/").length : 0;
  }

  /**
   * Format the filtered Recent tally without presenting a retained-page lower
   * bound as an exact result. An untruncated response can become non-exact
   * after an unscoped live change, so exactness—not truncation—owns the `+`.
   *
   * @param {number} count
   * @param {{totalMatching: number, totalMatchingExact: boolean, truncated: boolean}} options
   */
  function recentFilteredTallyText(count, options) {
    if (!options.totalMatchingExact && !options.truncated) {
      return `Filtered to ${count.toLocaleString()}+ files.`;
    }
    let text = `Filtered to ${count.toLocaleString()} ${count === 1 ? "file" : "files"}`;
    if (options.truncated) {
      const totalSuffix = options.totalMatchingExact ? "" : "+";
      text += ` of ${options.totalMatching.toLocaleString()}${totalSuffix} matching`;
    }
    return `${text}.`;
  }

  /**
   * Apply paths carried only by the unscoped catalog companion to Recent.
   * Exact paths are O(batch); subtree removal and the safe lower-bound count
   * each scan the retained page once. The caller coalesces the one resulting
   * authoritative repair rather than retaining these operations.
   *
   * @param {Map<string, RecentEntry>} entries
   * @param {CatalogChange | null | undefined} change
   * @param {{filterState: FilterStateApi, nowSec: number, state: FilterSnapshot, visibleDepth: number}} options
   * @returns {Readonly<RecentCatalogEffect>}
   */
  function applyRecentCatalogChange(entries, change, options) {
    if (!change) {
      return Object.freeze({
        changed: false,
        needsAuthoritativeRepair: false,
        removedEntries: 0,
        retainedLowerBound: null,
      });
    }
    // `removes` has subtree semantics but carries no file/directory tag. Even
    // a shallow path can therefore remove Recent leaves below the fs.change
    // scope, so it always needs an authoritative repair.
    const removalPrefixes = (change.removes || []).filter(
      /** @returns {value is string} */ (value) => typeof value === "string" && value.length > 0,
    );
    const exactPaths = [
      ...(change.upserts || []).map((entry) => entry.p),
      ...(change.remove_files || []),
      ...(change.non_file_paths || []),
    ].filter(
      /** @returns {path is string} */ (path) =>
        typeof path === "string" && inventoryPathDepth(path) > options.visibleDepth,
    );
    const needsAuthoritativeRepair = removalPrefixes.length > 0 || exactPaths.length > 0;
    if (!needsAuthoritativeRepair) {
      return Object.freeze({
        changed: false,
        needsAuthoritativeRepair: false,
        removedEntries: 0,
        retainedLowerBound: null,
      });
    }

    let removedEntries = 0;
    for (const path of exactPaths) {
      if (entries.delete(path)) {
        removedEntries += 1;
      }
    }
    removedEntries +=
      removalPrefixes.length > 0 ? removeRecentEntriesByPrefix(entries, removalPrefixes) : 0;
    const matchOptions = {
      filterState: options.filterState,
      nowSec: options.nowSec,
      state: options.state,
    };
    return Object.freeze({
      changed: removedEntries > 0,
      needsAuthoritativeRepair: true,
      removedEntries,
      retainedLowerBound: recentMatchingCount(Array.from(entries.values()), matchOptions),
    });
  }

  /**
   * @param {RecentEntry | null | undefined} entry
   * @param {{filterState: FilterStateApi, nowSec: number, state: FilterSnapshot}} options
   */
  function recentEntryMatches(entry, options) {
    if (entry?.type !== "file" || !entry.path) {
      return false;
    }
    if (!options.state.showIgnored && entry.gitignored) {
      return false;
    }
    // Generic tree rows may omit metadata while an asynchronous stat is
    // pending, so filterState.rowMatches deliberately preserves an unknown
    // mtime. Recent entries are complete provider records: under a bounded
    // window, missing, non-finite, and epoch mtimes must follow the provider's
    // cutoff predicate and cannot enter through the live overlay.
    if (
      options.state.recency !== "all" &&
      (typeof entry.mtime !== "number" || !Number.isFinite(entry.mtime) || entry.mtime <= 0)
    ) {
      return false;
    }
    return options.filterState.rowMatches(
      {
        mtime: entry.mtime,
        size: entry.size,
        path: entry.path,
        ext: entry.logical_ext || entry.ext || "",
      },
      options.state,
      options.nowSec,
    );
  }

  /** @param {RecentEntry} left @param {RecentEntry} right */
  function recentRankCompare(left, right) {
    const byIgnored = Number(!!left.gitignored) - Number(!!right.gitignored);
    const byMtime = (right.mtime || 0) - (left.mtime || 0);
    return byIgnored || byMtime || canonicalPathCompare(left.path, right.path);
  }

  /**
   * Whether an event for a row absent from the retained Recent page has an
   * unknown prior file state. Directory aggregate upserts are the exception:
   * they are frequent and cannot change membership unless the pre-event tree
   * row proves that the path changed from a file.
   *
   * @param {RecentFsChange} operation
   * @param {{type?: string} | null | undefined} previousFileStoreEntry
   */
  function recentUnseenBeforeMayMatch(operation, previousFileStoreEntry) {
    if (operation.op === "upsert") {
      return operation.entry.type === "file" || previousFileStoreEntry?.type === "file";
    }
    return true;
  }

  /**
   * A capped page needs an authoritative backfill when a known member
   * disappears or ranks later in the provider's order. An unseen path also
   * needs repair when its prior membership is unknown: absence from a capped
   * page does not prove that the path did not match below the retained top N.
   * Ordinary writes to known members raise mtime and stay on the fast local
   * overlay path.
   *
   * @param {RecentEntry | null | undefined} before
   * @param {RecentEntry | null | undefined} after
   * @param {{filterState: FilterStateApi, nowSec: number, state: FilterSnapshot}} options
   * @param {boolean} unseenBeforeMayMatch
   */
  function recentReplacementNeedsBackfill(before, after, options, unseenBeforeMayMatch) {
    if (!before) {
      return unseenBeforeMayMatch;
    }
    if (!recentEntryMatches(before, options)) {
      return false;
    }
    if (!recentEntryMatches(after, options)) {
      return true;
    }
    return (
      recentRankCompare(/** @type {RecentEntry} */ (after), /** @type {RecentEntry} */ (before)) > 0
    );
  }

  /**
   * Remove retained files at or below any invalidated path in one bounded pass.
   * The transient trie keeps a subtree-removal batch O(prefix bytes + retained
   * path bytes) instead of rescanning the capped page once per operation.
   *
   * @param {Map<string, RecentEntry>} entries
   * @param {string[]} prefixes
   */
  function removeRecentEntriesByPrefix(entries, prefixes) {
    /** @type {RemovalPrefixTrie} */
    const root = { children: new Map(), terminal: false };
    for (const prefix of prefixes) {
      if (!prefix) {
        continue;
      }
      let node = root;
      for (const segment of prefix.split("/")) {
        if (node.terminal) {
          break;
        }
        let child = node.children.get(segment);
        if (!child) {
          child = { children: new Map(), terminal: false };
          node.children.set(segment, child);
        }
        node = child;
      }
      node.terminal = true;
      node.children.clear();
    }

    let removed = 0;
    for (const path of entries.keys()) {
      let node = root;
      for (const segment of path.split("/")) {
        const child = node.children.get(segment);
        if (!child) {
          break;
        }
        node = child;
        if (node.terminal) {
          entries.delete(path);
          removed += 1;
          break;
        }
      }
    }
    return removed;
  }

  /**
   * Count matching files still retained locally after an ambiguous live batch.
   * This is a safe lower bound for the provider's whole-root selection.
   *
   * @param {RecentEntry[]} entries
   * @param {{filterState: FilterStateApi, nowSec: number, state: FilterSnapshot}} options
   */
  function recentMatchingCount(entries, options) {
    let count = 0;
    for (const entry of entries) {
      if (recentEntryMatches(entry, options)) {
        count += 1;
      }
    }
    return count;
  }

  /**
   * Apply one real `fs.change` batch to the capped Recent overlay.
   *
   * Every operation is handled in O(1). Subtree removal and temporary
   * lower-bound calculation each scan the retained page at most once after the
   * whole batch, and all transient prefix state is discarded on return.
   *
   * @param {Map<string, RecentEntry>} entries
   * @param {RecentFsChange[]} operations
   * @param {{filterState: FilterStateApi, limit: number, nowSec: number, previousEntries: Map<string, {type?: string}>, state: FilterSnapshot, truncated: boolean}} options
   */
  function applyRecentChangeBatch(entries, operations, options) {
    const matchOptions = {
      filterState: options.filterState,
      nowSec: options.nowSec,
      state: options.state,
    };
    let changed = false;
    let repairCandidate = false;
    /** @type {string[]} */
    const removalPrefixes = [];

    for (const operation of operations) {
      if (operation.op === "upsert") {
        const wireEntry = operation.entry;
        const upsertPath = wireEntry.path;
        if (!upsertPath) {
          continue;
        }
        const previous = entries.get(upsertPath);
        const unseenBeforeMayMatch = recentUnseenBeforeMayMatch(
          operation,
          options.previousEntries.get(upsertPath),
        );
        if (wireEntry.type !== "file") {
          repairCandidate =
            repairCandidate ||
            recentReplacementNeedsBackfill(
              previous,
              null,
              matchOptions,
              !previous && unseenBeforeMayMatch,
            );
          if (previous) {
            entries.delete(upsertPath);
            changed = true;
          }
          continue;
        }

        /** @type {RecentEntry} */
        const replacement = {
          ext: wireEntry.ext || "",
          mtime: (wireEntry.mtime_ns || 0) / 1e9,
          name: wireEntry.name,
          path: upsertPath,
          size: wireEntry.size || 0,
          type: "file",
        };
        if (wireEntry.gitignored) {
          replacement.gitignored = true;
        }
        const eligible = recentEntryMatches(replacement, matchOptions);
        repairCandidate =
          repairCandidate ||
          recentReplacementNeedsBackfill(
            previous,
            eligible ? replacement : null,
            matchOptions,
            !previous && unseenBeforeMayMatch,
          );
        if (eligible) {
          entries.set(replacement.path, replacement);
          changed = true;
        } else if (previous) {
          entries.delete(replacement.path);
          changed = true;
        }
        continue;
      }

      if (operation.op === "remove" && operation.path) {
        const previous = entries.get(operation.path);
        repairCandidate =
          repairCandidate ||
          recentReplacementNeedsBackfill(previous, null, matchOptions, !previous);
        if (previous) {
          entries.delete(operation.path);
          changed = true;
        }
        removalPrefixes.push(operation.path);
      }
    }

    const removedDescendants =
      removalPrefixes.length > 0 ? removeRecentEntriesByPrefix(entries, removalPrefixes) : 0;
    changed = changed || removedDescendants > 0;
    repairCandidate = repairCandidate || removedDescendants > 0;
    const overflowed = trimRecentEntriesToLimit(entries, options.limit);
    changed = changed || overflowed;
    repairCandidate = repairCandidate || overflowed;
    const truncated = options.truncated || overflowed;
    const needsAuthoritativeRepair = truncated && repairCandidate;
    return Object.freeze({
      changed,
      needsAuthoritativeRepair,
      overflowed,
      removedDescendants,
      retainedLowerBound: needsAuthoritativeRepair
        ? recentMatchingCount(Array.from(entries.values()), matchOptions)
        : null,
      truncated,
    });
  }

  /**
   * Restore the live overlay's provider cap once per fs.change batch.
   * Sorting the retained page plus that one wire batch avoids an O(limit)
   * worst-member scan for every upsert while leaving no batch-sized state
   * behind after the handler returns.
   *
   * @param {Map<string, RecentEntry>} entries
   * @param {number} limit
   */
  function trimRecentEntriesToLimit(entries, limit) {
    if (entries.size <= limit) {
      return false;
    }
    const retained = Array.from(entries.values()).sort(recentRankCompare).slice(0, limit);
    entries.clear();
    for (const entry of retained) {
      entries.set(entry.path, entry);
    }
    return true;
  }

  /**
   * Apply the current selection to the complete leaf model before clustering.
   * The server has already applied it to the fetched snapshot; repeating the
   * predicate is necessary for live filesystem entries merged after the fetch.
   *
   * @param {RecentEntry[]} entries
   * @param {{filterState: FilterStateApi, limit: number, nowSec: number, state: FilterSnapshot}} options
   */
  function recentEntries(entries, options) {
    const selected = entries.filter((entry) => {
      return recentEntryMatches(entry, options);
    });
    const matchingCount = selected.length;
    selected.sort(recentRankCompare);
    const capped = selected.slice(0, options.limit);
    capped.sort((left, right) => {
      const byMtime = (right.mtime || 0) - (left.mtime || 0);
      return byMtime || canonicalPathCompare(left.path, right.path);
    });
    return { entries: capped, matchingCount };
  }

  /** @param {number[]} ages @param {number} pct */
  function agesWithinPct(ages, pct) {
    if (ages.length <= 1) {
      return true;
    }
    let low = ages[0];
    let high = ages[0];
    for (let index = 1; index < ages.length; index += 1) {
      low = Math.min(low, ages[index]);
      high = Math.max(high, ages[index]);
    }
    return high <= 0 || (high - low) / high <= pct;
  }

  /**
   * Recent's presentation transform: directory construction, single-directory
   * compaction, aggregate chips, and coherent-cluster collapse.
   *
   * @param {RecentEntry[]} files
   * @param {number} nowSec
   * @param {number} pct
   * @param {Set<string>} ignoredDirectoryPaths
   * @returns {Array<any>}
   */
  function clusterRecentTree(files, nowSec, pct, ignoredDirectoryPaths) {
    /** @type {{name: string, subdirs: Map<string, any>, leaves: RecentEntry[]}} */
    const root = { name: "", subdirs: new Map(), leaves: [] };
    for (const file of files) {
      const parts = file.path.split("/");
      let node = root;
      for (let index = 0; index < parts.length - 1; index += 1) {
        const part = parts[index];
        if (!node.subdirs.has(part)) {
          node.subdirs.set(part, { name: part, subdirs: new Map(), leaves: [] });
        }
        node = node.subdirs.get(part);
      }
      node.leaves.push(file);
    }

    /** @param {any} node @param {string} path */
    function emitDirectory(node, path) {
      /** @type {Array<any>} */
      let children = [];
      for (const name of Array.from(node.subdirs.keys()).sort(canonicalPathCompare)) {
        const childPath = path ? `${path}/${name}` : name;
        children.push(emitDirectory(node.subdirs.get(name), childPath));
      }
      for (const leaf of node.leaves) {
        children.push({ ...leaf, type: "file" });
      }

      let compactName = node.name;
      let compactPath = path;
      while (children.length === 1 && children[0].type === "dir") {
        const only = children[0];
        compactName = compactName ? `${compactName}/${only.name}` : only.name;
        compactPath = only.path;
        children = only.children;
      }
      children.sort((left, right) => {
        const byMtime = (right.mtime || 0) - (left.mtime || 0);
        return byMtime || canonicalPathCompare(String(left.path), String(right.path));
      });

      let totalFiles = 0;
      let totalSize = 0;
      let newestMtime = 0;
      for (const child of children) {
        totalFiles += child.type === "dir" ? child.total_files || 0 : 1;
        totalSize += child.type === "dir" ? child.total_size || 0 : child.size || 0;
        newestMtime = Math.max(newestMtime, child.mtime || 0);
      }
      const ages = children
        .filter((child) => (child.mtime || 0) > 0)
        .map((child) => nowSec - child.mtime);
      const coherent = agesWithinPct(ages, pct);
      /** @type {any} */
      const result = {
        type: "dir",
        name: compactName,
        path: compactPath,
        children,
        total_files: totalFiles,
        total_size: totalSize,
        mtime: newestMtime,
        clustered: coherent,
      };
      if (coherent) {
        result.expanded = false;
      }
      if (ignoredDirectoryPaths.has(compactPath)) {
        result.gitignored = true;
      }
      return result;
    }

    /** @type {Array<any>} */
    const tree = [];
    for (const name of Array.from(root.subdirs.keys()).sort(canonicalPathCompare)) {
      tree.push(emitDirectory(root.subdirs.get(name), name));
    }
    for (const leaf of root.leaves) {
      tree.push({ ...leaf, type: "file" });
    }
    tree.sort((left, right) => {
      const byMtime = (right.mtime || 0) - (left.mtime || 0);
      return byMtime || canonicalPathCompare(String(left.path), String(right.path));
    });
    return tree;
  }

  /**
   * @param {RecentEntry[]} entries
   * @param {{filterState: FilterStateApi, ignoredDirectoryPaths: Set<string>, limit: number, nowSec: number, clusterPct: number, state: FilterSnapshot}} options
   */
  function recentView(entries, options) {
    const selection = recentEntries(entries, options);
    return {
      entries: selection.entries,
      matchingCount: selection.matchingCount,
      tree: clusterRecentTree(
        selection.entries,
        options.nowSec,
        options.clusterPct,
        options.ignoredDirectoryPaths,
      ),
    };
  }

  /**
   * Project the complete retained leaf model, then hand only that projection
   * to the application renderer. The callback has no mounted-row input, so
   * DOM pagination or disclosure cannot become a membership predicate.
   *
   * @param {RecentEntry[]} entries
   * @param {{filterState: FilterStateApi, ignoredDirectoryPaths: Set<string>, limit: number, nowSec: number, clusterPct: number, state: FilterSnapshot}} options
   * @param {(view: {entries: RecentEntry[], matchingCount: number, tree: any[]}) => void} render
   */
  function renderRecentView(entries, options, render) {
    const view = recentView(entries, options);
    render(view);
    return view;
  }

  /**
   * Run one scheduled authoritative repair against the still-current view.
   *
   * This model is already in the shell's eager path because every first tree
   * render needs its request projection. Keeping Recent's composition here
   * adds no asset or loading tier and lets the browserless session execute the
   * exact branches app.js uses.
   *
   * @param {ReturnType<typeof createRecentContinuity>} continuity
   * @param {RecentRefetch} request
   * @param {{current: boolean, filterRefetchPending: boolean, recentLoaded: boolean, viewCommitted: boolean, fetch: (windowKey: string, preserveRows: boolean) => void}} context
   */
  function runRecentRepair(continuity, request, context) {
    if (!context.current) {
      continuity.cancelRepairs();
      return "cancelled";
    }
    const disposition = continuity.repairReady(context.recentLoaded, context.filterRefetchPending);
    if (disposition === "repair") {
      context.fetch(request.windowKey, request.preserveRows === true && context.viewCommitted);
    }
    return disposition;
  }

  /**
   * Settle and apply an authoritative Recent response.
   *
   * Request identity settles before commit, failed-repair state resets before
   * render, and render runs last. An expiry discovered synchronously by render
   * therefore starts a new repair episode rather than dirtying the accepted
   * request or being suppressed by the old one.
   *
   * @param {ReturnType<typeof createRecentContinuity>} continuity
   * @param {RecentRequest} request
   * @param {RecentRefetch} repair
   * @param {{current: boolean, commit: () => void, render: () => void}} context
   */
  function settleRecentSuccess(continuity, request, repair, context) {
    const disposition = continuity.settleRequest(request);
    if (!context.current || disposition === "superseded") {
      return "ignored";
    }
    if (disposition === "refetch") {
      continuity.scheduleRepair(repair);
      return "repair-scheduled";
    }
    context.commit();
    continuity.repairSucceeded(repair);
    context.render();
    return "committed";
  }

  /**
   * Settle a failed Recent request without overlapping its replacement.
   *
   * @param {ReturnType<typeof createRecentContinuity>} continuity
   * @param {RecentRequest} request
   * @param {RecentRefetch} repair
   * @param {unknown} error
   * @param {{current: boolean, classify: (error: unknown) => {retryable: boolean}, showInitialError: () => void}} context
   */
  function settleRecentFailure(continuity, request, repair, error, context) {
    const disposition = continuity.settleRequest(request);
    if (!context.current || disposition === "superseded") {
      return "ignored";
    }
    if (disposition === "refetch") {
      if (repair.preserveRows === true) {
        const failure = context.classify(error);
        continuity.repairFailed(repair, failure.retryable);
        return "repair-failed";
      }
      continuity.scheduleRepair(repair);
      return "repair-scheduled";
    }
    if (repair.preserveRows === true) {
      const failure = context.classify(error);
      continuity.repairFailed(repair, failure.retryable);
      return "repair-failed";
    }
    context.showInitialError();
    return "initial-failed";
  }

  /**
   * Mark an active request dirty or schedule one bounded repair.
   *
   * @param {ReturnType<typeof createRecentContinuity>} continuity
   * @param {{recentActive: boolean, filterRefetchPending: boolean, repair: RecentRefetch}} context
   */
  function invalidateRecent(continuity, context) {
    return continuity.invalidate(
      context.recentActive,
      context.filterRefetchPending,
      context.repair,
    );
  }

  /**
   * Apply an event-stream snapshot boundary to Recent continuity.
   *
   * @param {ReturnType<typeof createRecentContinuity>} continuity
   * @param {{recentActive: boolean, filterRefetchPending: boolean, repair: RecentRefetch}} context
   */
  function observeRecentSentinel(continuity, context) {
    return continuity.observeSentinel(
      context.recentActive,
      context.filterRefetchPending,
      context.repair,
    );
  }

  window.MetabrowserTreeFilterModel = Object.freeze({
    applyRecentChangeBatch,
    applyRecentCatalogChange,
    beginRecentRequest,
    createRecentContinuity,
    createRecentRecomputeScheduler,
    createRecentRepairScheduler,
    createRecentRefetchScheduler,
    createRecentRequest,
    dirtyRecentRequest,
    invalidateRecent,
    observeRecentSentinel,
    recentEntryMatches,
    recentFilterCursor,
    recentFilterTransition,
    recentFilteredTallyText,
    recentRepairDisposition,
    recentRequestDisposition,
    recentRequestKey,
    recentUrl,
    recentView,
    renderRecentView,
    requestKey,
    requestParams,
    treeUrl,
    trimRecentEntriesToLimit,
    runRecentRepair,
    settleRecentFailure,
    settleRecentSuccess,
  });
})();
