// Minimal client-side catalog for quick file navigation.

(() => {
  /**
   * @typedef {object} CatalogWireEntry
   * @property {CatalogWireEntry[] | null} [children]
   * @property {boolean} [gitignored] present on tree and inventory payloads;
   *   absent on the bulk feed, which already excludes ignored files
   * @property {string} [logical_ext]
   * @property {string} [name]
   * @property {string} path
   * @property {string} type
   */

  /**
   * @typedef {object} KnownFile
   * @property {string} basename
   * @property {string | null} logicalExtension
   * @property {string} path
   * @property {string} source
   */

  /**
   * @typedef {object} CatalogSnapshot
   * @property {boolean} complete true once a complete bulk feed has
   *   been applied (or the walk finished after an incomplete one)
   * @property {readonly KnownFile[]} files
   * @property {number} observedCount
   * @property {number} revision
   * @property {Readonly<Record<string, number>>} sourceSummary
   */

  /** Provenance that may seat a gitignored path: the user opened it on purpose. */
  const NAVIGATION_SOURCE = "navigation";

  /** Provenance of paths the bulk feed owns and may therefore retire. */
  const FEED_SOURCE = "catalog-feed";

  /**
   * Compare strings by UTF-16 code unit without locale-dependent collation.
   * @param {string} left
   * @param {string} right
   */
  function codeUnitCompare(left, right) {
    if (left < right) {
      return -1;
    }
    if (left > right) {
      return 1;
    }
    return 0;
  }

  /** @param {string} path */
  function basenameForPath(path) {
    const separator = path.lastIndexOf("/");
    return separator >= 0 ? path.slice(separator + 1) : path;
  }

  /** Create an isolated catalog whose snapshots cannot mutate internal state. */
  function create() {
    /** @type {Map<string, Readonly<KnownFile>>} */
    const filesByPath = new Map();
    let revision = 0;
    let catalogComplete = false;
    /** @type {Array<() => void>} */
    const subscribers = [];
    let notifyDepth = 0;
    /** @type {CatalogSnapshot | null} */
    let memoizedSnapshot = null;

    /**
     * Advance the revision and tell derived views the catalog moved.
     *
     * Every mutation routes through here, so a consumer subscribes once
     * instead of hooking each ingestion seam. The palette needs this because a
     * query typed while the bulk feed is still arriving would otherwise keep
     * its original results forever — the search controller only republishes on
     * a keystroke.
     *
     * The notification is invalidation only: no snapshot, not even the
     * revision. Building one here would sort the whole catalog on every
     * mutation, and the palette installs its listener for the application
     * lifetime, so that cost would land on every delta, navigation, tree
     * update, and resync — including while the palette is closed, which is the
     * common case, and ahead of the coalescing window meant to absorb exactly
     * this. A listener that needs state calls snapshot() when it is ready to
     * use it, which is also what makes the value it reads current rather than
     * whatever was true when the notification was queued.
     *
     * A listener that mutates the catalog would recurse, so re-entrant
     * notification is suppressed: the outermost bump is the only one that
     * reports, and by the time listeners run the nested write has landed.
     */
    function bumpRevision() {
      revision += 1;
      if (notifyDepth > 0 || subscribers.length === 0) {
        return;
      }
      notifyDepth += 1;
      try {
        // Iterate a copy: a listener may unsubscribe itself while running.
        for (const listener of subscribers.slice()) {
          try {
            listener();
          } catch (_error) {
            // One bad subscriber must not stop the rest, nor the ingestion
            // path that triggered this.
          }
        }
      } finally {
        notifyDepth -= 1;
      }
    }

    /**
     * Observe catalog changes. Returns an unsubscribe function.
     *
     * The listener takes no argument: it is told the catalog moved, not what
     * it moved to. Call `snapshot()` when the new state is actually needed.
     * @param {() => void} listener
     */
    function subscribe(listener) {
      if (typeof listener !== "function") {
        throw new TypeError("Catalog subscriber must be a function");
      }
      subscribers.push(listener);
      return () => {
        const index = subscribers.indexOf(listener);
        if (index >= 0) {
          subscribers.splice(index, 1);
        }
      };
    }

    /**
     * @param {string} path
     * @param {string | null} logicalExtension
     * @param {string} source
     */
    function put(path, logicalExtension, source) {
      if (!path || !source) {
        return false;
      }
      const basename = basenameForPath(path);
      if (!basename) {
        return false;
      }
      const previous = filesByPath.get(path);
      const nextLogicalExtension = logicalExtension || previous?.logicalExtension || null;
      if (
        previous &&
        previous.basename === basename &&
        previous.logicalExtension === nextLogicalExtension &&
        previous.source === source
      ) {
        return false;
      }
      filesByPath.set(
        path,
        Object.freeze({
          basename,
          logicalExtension: nextLogicalExtension,
          path,
          source,
        }),
      );
      return true;
    }

    /** @param {CatalogWireEntry} entry @param {string} source */
    function putEntry(entry, source) {
      if (entry?.type !== "file" || typeof entry.path !== "string") {
        return false;
      }
      // The catalog advertises itself as complete AND non-gitignored, and the
      // bulk feed honors that by excluding ignored files. Passive seams — the
      // initial tree, lazy subtrees, inventory snapshots and deltas — carry
      // ignored rows too, because the tree paints them dimmed rather than
      // hiding them. Letting those in made Quick File offer files the feed had
      // deliberately dropped (__pycache__/*.pyc against a complete catalog).
      //
      // Only explicit navigation may seat an ignored path: the user went there
      // on purpose, so it stays findable. That is a provenance decision, not a
      // property of the entry, so it is keyed on the source rather than the
      // wire payload. An ignored path already seated passively is evicted.
      if (entry.gitignored === true && source !== NAVIGATION_SOURCE) {
        // A path navigation already seated keeps its place: the later passive
        // sighting is the same ignored file the user chose to open, so it
        // carries no new information and must not evict it.
        if (filesByPath.get(entry.path)?.source === NAVIGATION_SOURCE) {
          return false;
        }
        return removeWithoutRevision(entry.path);
      }
      const logicalExtension =
        typeof entry.logical_ext === "string" && entry.logical_ext ? entry.logical_ext : null;
      return put(entry.path, logicalExtension, source);
    }

    /**
     * Remove several paths, and everything beneath them, in one pass.
     *
     * A removed path may name a directory, so each one has to be matched
     * against every entry as a prefix. Doing that per path was cheap when the
     * catalog held a depth-2 slice and is not now that it holds the whole
     * non-gitignored tree: a branch switch or bulk delete arrives as one batch
     * of many removes and cost O(entries x removes) on the UI thread, with an
     * open search waiting on it. Sweeping a whole batch together makes it one
     * pass per batch instead of one per path.
     *
     * Callers group only *consecutive* removes, so relative order with
     * interleaved upserts is preserved — `remove("dir")` then
     * `upsert("dir/child")` still keeps the child.
     * @param {readonly string[]} paths
     */
    function removeManyWithoutRevision(paths) {
      /** @type {Set<string>} */
      const removed = new Set();
      for (const path of paths) {
        if (!path) {
          continue;
        }
        removed.add(path.endsWith("/") ? path.slice(0, -1) : path);
      }
      if (removed.size === 0) {
        return false;
      }
      let changed = false;
      for (const candidatePath of filesByPath.keys()) {
        if (isRemoved(candidatePath, removed)) {
          filesByPath.delete(candidatePath);
          changed = true;
        }
      }
      return changed;
    }

    /**
     * Is this path removed, either named directly or as a descendant?
     *
     * Asks the question from the candidate's side — walk its ancestor
     * directories and look each up — rather than testing the candidate
     * against every removed prefix. That is what makes a batch sweep
     * independent of how many paths were removed: cost per entry is its path
     * depth and a few Set lookups, not the size of the removal list.
     * @param {string} candidatePath
     * @param {Set<string>} removed
     */
    function isRemoved(candidatePath, removed) {
      if (removed.has(candidatePath)) {
        return true;
      }
      let boundary = candidatePath.lastIndexOf("/");
      while (boundary > 0) {
        if (removed.has(candidatePath.slice(0, boundary))) {
          return true;
        }
        boundary = candidatePath.lastIndexOf("/", boundary - 1);
      }
      return false;
    }

    /** @param {string} path */
    function removeWithoutRevision(path) {
      return removeManyWithoutRevision([path]);
    }

    /** @param {CatalogWireEntry[]} entries @param {string} source */
    function observeEntries(entries, source) {
      let changed = false;
      for (const entry of entries) {
        changed = putEntry(entry, source) || changed;
      }
      if (changed) {
        bumpRevision();
      }
    }

    /**
     * Record every file leaf present in a complete or partial tree payload.
     * @param {CatalogWireEntry[]} entries
     * @param {string} source
     */
    function observeTree(entries, source) {
      /** @type {CatalogWireEntry[]} */
      const stack = entries.slice();
      let changed = false;
      while (stack.length > 0) {
        const entry = stack.pop();
        if (!entry) {
          continue;
        }
        if (entry.type === "file") {
          changed = putEntry(entry, source) || changed;
        } else if (entry.type === "dir" && Array.isArray(entry.children)) {
          stack.push(...entry.children);
        }
      }
      if (changed) {
        bumpRevision();
      }
    }

    /** @param {CatalogWireEntry[]} entries */
    function observeInitialTree(entries) {
      observeTree(entries, "initial-tree");
    }

    /** @param {CatalogWireEntry[]} entries */
    function observeLazyTree(entries) {
      observeTree(entries, "lazy-tree");
    }

    /** @param {CatalogWireEntry[]} entries */
    function observeRecent(entries) {
      observeEntries(entries, "recent");
    }

    /** @param {CatalogWireEntry[]} entries */
    function observeEventSnapshot(entries) {
      observeEntries(entries, "event-snapshot");
    }

    /** @param {Array<{entry?: CatalogWireEntry, op: string, path?: string}>} ops */
    function applyEventChange(ops) {
      let changed = false;
      /** @type {string[]} */
      let pendingRemoves = [];
      // Flush before any upsert so ordering inside the batch is unchanged:
      // only a consecutive run of removes is ever collapsed into one sweep.
      function flushRemoves() {
        if (pendingRemoves.length === 0) {
          return;
        }
        changed = removeManyWithoutRevision(pendingRemoves) || changed;
        pendingRemoves = [];
      }
      for (const op of ops) {
        if (op.op === "upsert" && op.entry) {
          flushRemoves();
          changed = putEntry(op.entry, "event-change") || changed;
        } else if (op.op === "remove" && typeof op.path === "string") {
          pendingRemoves.push(op.path);
        }
      }
      flushRemoves();
      if (changed) {
        bumpRevision();
      }
    }

    /** @param {string} path @param {string | null} logicalExtension */
    function observeNavigation(path, logicalExtension) {
      if (put(path, logicalExtension, NAVIGATION_SOURCE)) {
        bumpRevision();
      }
    }

    /**
     * Apply the one-shot `/api/catalog` bulk payload. Merges rather
     * than replaces: gitignored files a user navigated to stay
     * findable, and stale observed paths are pruned by remove ops or
     * the palette's not-found flow rather than a destructive swap.
     * @param {Array<{p: string, e: string}>} files
     * @param {boolean} bulkComplete whether the index had finished
     *   walking when the payload was built
     */
    function applyBulkSnapshot(files, bulkComplete, authoritative = false) {
      let changed = false;
      /** @type {Set<string> | null} */
      const membership = authoritative ? new Set() : null;
      for (const file of files) {
        if (typeof file?.p !== "string") {
          continue;
        }
        membership?.add(file.p);
        changed = put(file.p, file.e || null, FEED_SOURCE) || changed;
      }
      // A refetch happens precisely because deltas may have been dropped, so
      // a merge alone cannot express what the payload says is GONE: a file
      // deleted while the stream was down is absent from the refetch and, if
      // we only merge, stays searchable forever.
      //
      // A finished walk lists every file the index holds, so its payload is
      // authoritative membership and anything else the feed put here is
      // stale. Paths seated by explicit navigation survive: they are the
      // documented exception to feed membership (a gitignored file the user
      // opened is not in the feed by design). Passive observations do not
      // survive — a tree row the authoritative feed omits is a deleted file.
      //
      // Safe against the create-during-fetch race because the feed buffers
      // deltas while a fetch is in flight and replays them after this
      // returns, so a file created in the window is re-added immediately.
      if (membership) {
        for (const [path, file] of filesByPath) {
          if (file.source === NAVIGATION_SOURCE || membership.has(path)) {
            continue;
          }
          filesByPath.delete(path);
          changed = true;
        }
      }
      // Completeness only ever rises here; `clear()` is the reset.
      // A bulk response built mid-walk (`complete: false`) can
      // resolve after the walk-completion event already marked the
      // catalog complete, and that event fires once — accepting the
      // stale flag would downgrade permanently. The cost is a
      // transiently optimistic flag when a restarted server is
      // still walking, where the data converges through live ops.
      if (bulkComplete && !catalogComplete) {
        catalogComplete = true;
        changed = true;
      }
      if (changed) {
        bumpRevision();
      }
    }

    /**
     * Apply one `catalog.change` event from the live stream.
     * @param {{upserts?: Array<{p: string, e: string}>, removes?: string[]}} payload
     */
    function applyCatalogChange(payload) {
      let changed = false;
      for (const upsert of payload?.upserts || []) {
        if (typeof upsert?.p === "string") {
          changed = put(upsert.p, upsert.e || null, "catalog-event") || changed;
        }
      }
      // Upserts and removes arrive as separate arrays here, so the whole
      // remove list is one consecutive run and sweeps in a single pass.
      const removes = (payload?.removes || []).filter(
        /** @returns {value is string} */ (value) => typeof value === "string",
      );
      changed = removeManyWithoutRevision(removes) || changed;
      if (changed) {
        bumpRevision();
      }
    }

    /**
     * Flip completeness without new data: the walk finished after an
     * incomplete bulk fetch, and live ops already converged the
     * contents.
     */
    function markComplete() {
      if (!catalogComplete) {
        catalogComplete = true;
        bumpRevision();
      }
    }

    /**
     * Remove a file or every known descendant of a directory path.
     * @param {string} path
     */
    function removePath(path) {
      if (removeWithoutRevision(path)) {
        bumpRevision();
      }
    }

    /** Clear observations after a root swap or resynchronization boundary. */
    function clear() {
      filesByPath.clear();
      catalogComplete = false;
      bumpRevision();
    }

    /**
     * Return a stable, immutable view of the current catalog.
     * Memoized by revision: the palette re-reads the snapshot on
     * every status render and the provider once per search, so the
     * copy-and-sort must not repeat while nothing changed.
     */
    function snapshot() {
      if (memoizedSnapshot && memoizedSnapshot.revision === revision) {
        return memoizedSnapshot;
      }
      const files = Array.from(filesByPath.values()).sort((left, right) =>
        codeUnitCompare(left.path, right.path),
      );
      /** @type {Record<string, number>} */
      const sourceSummary = {};
      for (const file of files) {
        sourceSummary[file.source] = (sourceSummary[file.source] || 0) + 1;
      }
      memoizedSnapshot = Object.freeze({
        complete: catalogComplete,
        files: Object.freeze(files),
        observedCount: files.length,
        revision,
        sourceSummary: Object.freeze(sourceSummary),
      });
      return memoizedSnapshot;
    }

    return Object.freeze({
      applyBulkSnapshot,
      applyCatalogChange,
      applyEventChange,
      clear,
      markComplete,
      observeEventSnapshot,
      observeInitialTree,
      observeLazyTree,
      observeNavigation,
      observeRecent,
      observeTree,
      removePath,
      snapshot,
      subscribe,
    });
  }

  window.MetabrowserKnownFileCatalog = Object.freeze({ create });
})();
