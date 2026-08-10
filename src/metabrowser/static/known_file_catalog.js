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
    /** @type {CatalogSnapshot | null} */
    let memoizedSnapshot = null;

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

    /** @param {string} path */
    function removeWithoutRevision(path) {
      if (!path) {
        return false;
      }
      const prefix = path.endsWith("/") ? path : `${path}/`;
      let changed = false;
      for (const candidatePath of filesByPath.keys()) {
        if (candidatePath === path || candidatePath.startsWith(prefix)) {
          filesByPath.delete(candidatePath);
          changed = true;
        }
      }
      return changed;
    }

    /** @param {CatalogWireEntry[]} entries @param {string} source */
    function observeEntries(entries, source) {
      let changed = false;
      for (const entry of entries) {
        changed = putEntry(entry, source) || changed;
      }
      if (changed) {
        revision += 1;
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
        revision += 1;
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
      for (const op of ops) {
        if (op.op === "upsert" && op.entry) {
          changed = putEntry(op.entry, "event-change") || changed;
        } else if (op.op === "remove" && typeof op.path === "string") {
          changed = removeWithoutRevision(op.path) || changed;
        }
      }
      if (changed) {
        revision += 1;
      }
    }

    /** @param {string} path @param {string | null} logicalExtension */
    function observeNavigation(path, logicalExtension) {
      if (put(path, logicalExtension, NAVIGATION_SOURCE)) {
        revision += 1;
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
        revision += 1;
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
      for (const removed of payload?.removes || []) {
        if (typeof removed === "string") {
          changed = removeWithoutRevision(removed) || changed;
        }
      }
      if (changed) {
        revision += 1;
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
        revision += 1;
      }
    }

    /**
     * Remove a file or every known descendant of a directory path.
     * @param {string} path
     */
    function removePath(path) {
      if (removeWithoutRevision(path)) {
        revision += 1;
      }
    }

    /** Clear observations after a root swap or resynchronization boundary. */
    function clear() {
      filesByPath.clear();
      catalogComplete = false;
      revision += 1;
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
    });
  }

  window.MetabrowserKnownFileCatalog = Object.freeze({ create });
})();
