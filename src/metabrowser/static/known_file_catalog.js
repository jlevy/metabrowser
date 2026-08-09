// Minimal client-side catalog for quick file navigation.

(() => {
  /**
   * @typedef {object} CatalogWireEntry
   * @property {CatalogWireEntry[] | null} [children]
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
      if (put(path, logicalExtension, "navigation")) {
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
    function applyBulkSnapshot(files, bulkComplete) {
      let changed = false;
      for (const file of files) {
        if (typeof file?.p !== "string") {
          continue;
        }
        changed = put(file.p, file.e || null, "catalog-feed") || changed;
      }
      if (bulkComplete !== catalogComplete) {
        catalogComplete = bulkComplete;
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
