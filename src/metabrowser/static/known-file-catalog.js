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
   * Root coverage of the catalog. `complete` means a finished, uncapped walk.
   * `truncated` means the walk finished at the inventory file cap: membership
   * is final for this index, but files past the cap were never indexed.
   * @typedef {"partial" | "truncated" | "complete"} CatalogCoverage
   */

  /**
   * @typedef {object} CatalogSnapshot
   * @property {boolean} complete true once a complete bulk feed has
   *   been applied (or an uncapped walk finished after an incomplete one)
   * @property {boolean} truncated true when the walk finished at its file cap;
   *   never true together with `complete`
   * @property {readonly KnownFile[]} files
   * @property {number} observedCount
   * @property {number} revision
   * @property {Readonly<Record<string, number>>} sourceSummary
   */

  const COVERAGE_RANK = new Map([
    ["partial", 0],
    ["truncated", 1],
    ["complete", 2],
  ]);

  /** @param {CatalogCoverage} coverage */
  function coverageRank(coverage) {
    return COVERAGE_RANK.get(coverage) ?? 0;
  }

  /**
   * A terminal truncated walk cannot downgrade complete coverage; resetting to
   * partial and establishing complete coverage are explicit.
   * @param {CatalogCoverage} current
   * @param {CatalogCoverage} requested
   * @returns {CatalogCoverage}
   */
  function nextCoverage(current, requested) {
    return requested === "truncated" && current === "complete" ? current : requested;
  }

  /** Provenance that may seat a gitignored path: the user opened it on purpose. */
  const NAVIGATION_SOURCE = "navigation";

  /** Provenance of paths the bulk feed owns and may therefore retire. */
  const FEED_SOURCE = "catalog-feed";

  // Keep the steady-state direct path at the inventory stream's bounded batch
  // size. Larger or descendant-amplified changes use the sliced transaction;
  // exp-032 records the exact headed 300k timing beside this limit.
  const DIRECT_CHANGE_MAX_ITEMS = 256;

  // Repeated insertion is faster for a handful of point changes. Above this,
  // merge one overlay into the maintained projection so cost is O(n + k)
  // rather than O(n * k) when every new path sorts near the front.
  const POINT_RUN_MERGE_MIN_ITEMS = 16;

  /**
   * @typedef {object} BulkSnapshotStep
   * @property {number} candidateVisits
   * @property {boolean} cancelled
   * @property {boolean} done
   * @property {number} workItems
   */

  /**
   * @typedef {object} BulkSnapshotApplication
   * @property {() => void} cancel
   * @property {(payload: CatalogChangePayload) => void} enqueueCatalogChange
   * @property {(ops: EventChangeOperation[]) => void} enqueueEventChange
   * @property {(maxWorkItems: number) => BulkSnapshotStep} step
   */

  /**
   * @typedef {{kind: "put", path: string, logicalExtension: string | null, source: string} |
   *   {kind: "entry", entry: CatalogWireEntry, source: string} |
   *   {kind: "delete", path: string, preserveNavigation: boolean} |
   *   {kind: "remove", paths: Set<string>} |
   *   {kind: "coverage", value: CatalogCoverage}} BulkConcurrentMutation
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
   * @property {CatalogWireEntry} [entry]
   * @property {string} op
   * @property {string} [path]
   */

  /**
   * @typedef {object} CatalogState
   * @property {Map<string, Readonly<KnownFile>>} filesByPath
   * @property {Readonly<KnownFile>[]} orderedFiles
   * @property {Record<string, number>} sourceSummary
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

  /** @param {string} path @param {unknown} name */
  function displayBasename(path, name) {
    if (typeof name === "string" && name && !name.includes("/") && name !== "." && name !== "..") {
      return name;
    }
    return basenameForPath(path);
  }

  /**
   * Match the provider's canonical inventory-path contract for one file.
   * Paths are nonempty POSIX-relative identities with normalized segments.
   * JSON represents valid astral code points as surrogate pairs; reject only
   * an unpaired surrogate, which cannot have come from the provider's escaped
   * UTF-8 identity.
   * @param {unknown} value
   * @returns {value is string}
   */
  function isCanonicalFilePath(value) {
    if (typeof value !== "string" || value.length === 0) {
      return false;
    }
    let segmentStart = 0;
    for (let index = 0; index < value.length; index += 1) {
      const codeUnit = value.charCodeAt(index);
      if (codeUnit === 0 || codeUnit === 92) {
        return false;
      }
      if (codeUnit === 47) {
        const segmentLength = index - segmentStart;
        if (
          segmentLength === 0 ||
          (segmentLength === 1 && value.charCodeAt(segmentStart) === 46) ||
          (segmentLength === 2 &&
            value.charCodeAt(segmentStart) === 46 &&
            value.charCodeAt(segmentStart + 1) === 46)
        ) {
          return false;
        }
        segmentStart = index + 1;
        continue;
      }
      if (codeUnit >= 0xd800 && codeUnit <= 0xdbff) {
        const following = value.charCodeAt(index + 1);
        if (!(following >= 0xdc00 && following <= 0xdfff)) {
          return false;
        }
        index += 1;
      } else if (codeUnit >= 0xdc00 && codeUnit <= 0xdfff) {
        return false;
      }
    }
    const finalLength = value.length - segmentStart;
    return !(
      finalLength === 0 ||
      (finalLength === 1 && value.charCodeAt(segmentStart) === 46) ||
      (finalLength === 2 &&
        value.charCodeAt(segmentStart) === 46 &&
        value.charCodeAt(segmentStart + 1) === 46)
    );
  }

  /** @returns {CatalogState} */
  function emptyState() {
    return { filesByPath: new Map(), orderedFiles: [], sourceSummary: {} };
  }

  /**
   * Locate the first path greater than or equal to `path`.
   * @param {Readonly<KnownFile>[]} files
   * @param {string} path
   */
  function lowerBound(files, path) {
    let low = 0;
    let high = files.length;
    while (low < high) {
      const middle = low + Math.floor((high - low) / 2);
      if (codeUnitCompare(files[middle].path, path) < 0) {
        low = middle + 1;
      } else {
        high = middle;
      }
    }
    return low;
  }

  /** @param {Record<string, number>} summary @param {string} source @param {number} delta */
  function adjustSource(summary, source, delta) {
    const next = (summary[source] || 0) + delta;
    if (next > 0) {
      summary[source] = next;
    } else {
      delete summary[source];
    }
  }

  /** @param {CatalogState} target */
  function ensureMutableFiles(target) {
    if (Object.isFrozen(target.orderedFiles)) {
      target.orderedFiles = target.orderedFiles.slice();
    }
  }

  /**
   * Normalize redundant descendants out of a subtree-removal set.
   * @param {readonly string[]} paths
   */
  function normalizeRemovalPaths(paths) {
    const sorted = Array.from(
      new Set(paths.filter(/** @returns {path is string} */ (path) => isCanonicalFilePath(path))),
    ).sort(codeUnitCompare);
    /** @type {string[]} */
    const normalized = [];
    for (const path of sorted) {
      const previous = normalized.at(-1);
      if (previous && (path === previous || path.startsWith(`${previous}/`))) {
        continue;
      }
      normalized.push(path);
    }
    return normalized;
  }

  /**
   * Append the exact and descendant intervals one removal path occupies.
   * Incrementing the descendant separator (`/` -> `0`) gives a strict upper
   * bound without admitting siblings such as `docs-old`.
   *
   * The two intervals are not adjacent in general: every sibling whose next
   * code unit sorts below `/` (`docs.md`, `docs-old`, `docs 2`) lies between
   * `docs` and `docs/…`, and such a sibling may itself be another removal path.
   * @param {Readonly<KnownFile>[]} files
   * @param {string} path
   * @param {Array<{start: number, end: number}>} ranges
   */
  function appendRemovalIntervals(files, path, ranges) {
    const exact = lowerBound(files, path);
    if (files[exact]?.path === path) {
      ranges.push({ end: exact + 1, start: exact });
    }
    const descendantStart = lowerBound(files, `${path}/`);
    const descendantEnd = lowerBound(files, `${path}0`);
    if (descendantEnd > descendantStart) {
      ranges.push({ end: descendantEnd, start: descendantStart });
    }
  }

  /**
   * Order intervals by start and coalesce any that touch, so a single forward
   * pass can remove them.
   * @param {Array<{start: number, end: number}>} ranges
   */
  function sortedDisjointRanges(ranges) {
    ranges.sort((left, right) => left.start - right.start);
    /** @type {Array<{start: number, end: number}>} */
    const merged = [];
    for (const range of ranges) {
      const previous = merged.at(-1);
      if (previous && range.start <= previous.end) {
        previous.end = Math.max(previous.end, range.end);
      } else {
        merged.push({ end: range.end, start: range.start });
      }
    }
    return merged;
  }

  /**
   * Find sorted, disjoint exact-or-descendant intervals in the canonical
   * projection.
   * @param {Readonly<KnownFile>[]} files
   * @param {readonly string[]} paths
   */
  function removalRanges(files, paths) {
    /** @type {Array<{start: number, end: number}>} */
    const ranges = [];
    for (const path of normalizeRemovalPaths(paths)) {
      appendRemovalIntervals(files, path, ranges);
    }
    return sortedDisjointRanges(ranges);
  }

  /** Create an isolated catalog whose snapshots cannot mutate internal state. */
  function create() {
    /** @type {CatalogState} */
    let state = emptyState();
    let revision = 0;
    /** @type {CatalogCoverage} */
    let catalogCoverage = "partial";
    /** @type {{cancel: () => void, record: (mutation: BulkConcurrentMutation) => void} | null} */
    let activeBulkApplication = null;
    /** @type {Array<() => void>} */
    const subscribers = [];
    let notifyDepth = 0;
    let notificationScheduled = false;
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
     * revision. The maintained projection makes `snapshot()` O(1) in catalog
     * size, and a listener calls it when it is ready to use current state.
     *
     * A listener that mutates the catalog would recurse, so re-entrant
     * notification is suppressed: the outermost bump is the only one that
     * reports, and by the time listeners run the nested write has landed.
     */
    function notifySubscribers() {
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

    function scheduleNotification() {
      if (notificationScheduled || subscribers.length === 0) {
        return;
      }
      notificationScheduled = true;
      Promise.resolve().then(() => {
        if (!notificationScheduled) {
          return;
        }
        notificationScheduled = false;
        notifySubscribers();
      });
    }

    /** @param {boolean} [deferNotification=false] */
    function bumpRevision(deferNotification = false) {
      // A revision invalidates both the value and the ownership of the cached
      // projection. In particular, an atomic bulk swap must not retain the
      // previous catalog's full sorted array until some consumer happens to
      // ask for another snapshot.
      memoizedSnapshot = null;
      revision += 1;
      if (deferNotification) {
        scheduleNotification();
        return;
      }
      // A direct mutation supersedes a queued bulk invalidation: listeners
      // run once now and observe the newest revision.
      notificationScheduled = false;
      notifySubscribers();
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
     * @param {CatalogState} target
     * @param {string} path
     * @param {string | null} logicalExtension
     * @param {string} source
     * @param {boolean} [appendIfOrdered=false]
     * @param {string} [displayName]
     */
    function putCanonicalInto(
      target,
      path,
      logicalExtension,
      source,
      appendIfOrdered = false,
      displayName,
    ) {
      const basename = displayBasename(path, displayName);
      const previous = target.filesByPath.get(path);
      const nextLogicalExtension = logicalExtension || previous?.logicalExtension || null;
      if (
        previous &&
        previous.basename === basename &&
        previous.logicalExtension === nextLogicalExtension &&
        previous.source === source
      ) {
        return false;
      }
      const next = Object.freeze({
        basename,
        logicalExtension: nextLogicalExtension,
        path,
        source,
      });
      ensureMutableFiles(target);
      if (previous) {
        const index = lowerBound(target.orderedFiles, path);
        target.orderedFiles[index] = next;
        adjustSource(target.sourceSummary, previous.source, -1);
      } else if (
        appendIfOrdered &&
        (!target.orderedFiles.length ||
          codeUnitCompare(target.orderedFiles[target.orderedFiles.length - 1].path, path) < 0)
      ) {
        // Catalog pages arrive in canonical provider order. ASCII paths — the
        // representative and overwhelmingly common case — are also code-unit
        // ordered, so append without repeating a logarithmic search per file.
        // A Unicode ordering inversion falls back to insertion below and the
        // public projection still keeps its stronger code-unit contract.
        target.orderedFiles.push(next);
      } else {
        const index = lowerBound(target.orderedFiles, path);
        target.orderedFiles.splice(index, 0, next);
      }
      target.filesByPath.set(path, next);
      adjustSource(target.sourceSummary, source, 1);
      return true;
    }

    /**
     * @param {CatalogState} target
     * @param {string} path
     * @param {string | null} logicalExtension
     * @param {string} source
     * @param {boolean} [appendIfOrdered=false]
     */
    function putInto(target, path, logicalExtension, source, appendIfOrdered = false) {
      if (!isCanonicalFilePath(path) || !source) {
        return false;
      }
      return putCanonicalInto(target, path, logicalExtension, source, appendIfOrdered);
    }

    /**
     * @param {string} path
     * @param {string | null} logicalExtension
     * @param {string} source
     */
    function put(path, logicalExtension, source) {
      if (!isCanonicalFilePath(path) || !source) {
        return false;
      }
      const basename = basenameForPath(path);
      if (!basename) {
        return false;
      }
      if (activeBulkApplication) {
        activeBulkApplication.record({ kind: "put", logicalExtension, path, source });
        return false;
      }
      return putCanonicalInto(state, path, logicalExtension, source);
    }

    /**
     * @param {CatalogState} target
     * @param {CatalogWireEntry} entry
     * @param {string} source
     * @param {boolean} [appendIfOrdered=false]
     */
    function putCanonicalEntryInto(target, entry, source, appendIfOrdered = false) {
      if (entry.gitignored === true && source !== NAVIGATION_SOURCE) {
        if (target.filesByPath.get(entry.path)?.source === NAVIGATION_SOURCE) {
          return false;
        }
        return deleteExactFrom(target, entry.path, false);
      }
      const logicalExtension =
        typeof entry.logical_ext === "string" && entry.logical_ext ? entry.logical_ext : null;
      return putCanonicalInto(
        target,
        entry.path,
        logicalExtension,
        source,
        appendIfOrdered,
        entry.name,
      );
    }

    /** @param {CatalogState} target @param {CatalogWireEntry} entry @param {string} source */
    function putEntryInto(target, entry, source) {
      if (entry?.type !== "file" || !isCanonicalFilePath(entry.path)) {
        return false;
      }
      return putCanonicalEntryInto(target, entry, source);
    }

    /** @param {CatalogWireEntry} entry @param {string} source */
    function putEntry(entry, source) {
      if (entry?.type !== "file" || !isCanonicalFilePath(entry.path)) {
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
      if (activeBulkApplication) {
        activeBulkApplication.record({ kind: "entry", entry, source });
        return false;
      }
      return putCanonicalEntryInto(state, entry, source);
    }

    /**
     * Remove one exact leaf from a state while keeping its sorted projection
     * and provenance tally coherent.
     * @param {CatalogState} target
     * @param {string} path
     * @param {boolean} preserveNavigation
     */
    function deleteExactFrom(target, path, preserveNavigation) {
      if (!isCanonicalFilePath(path)) {
        return false;
      }
      const previous = target.filesByPath.get(path);
      if (!previous || (preserveNavigation && previous.source === NAVIGATION_SOURCE)) {
        return false;
      }
      ensureMutableFiles(target);
      const index = lowerBound(target.orderedFiles, path);
      if (target.orderedFiles[index]?.path === path) {
        target.orderedFiles.splice(index, 1);
      }
      target.filesByPath.delete(path);
      adjustSource(target.sourceSummary, previous.source, -1);
      return true;
    }

    /**
     * Apply one point mutation without touching the ordered projection.
     * `replacements` captures the final value for the later linear merge.
     * @param {CatalogState} target
     * @param {BulkConcurrentMutation} mutation
     * @param {Map<string, Readonly<KnownFile> | null>} replacements
     * @param {boolean} preserveFeedOwnership
     */
    function applyPointWithoutProjection(target, mutation, replacements, preserveFeedOwnership) {
      if (mutation.kind === "put") {
        if (
          preserveFeedOwnership &&
          mutation.source === NAVIGATION_SOURCE &&
          target.filesByPath.get(mutation.path)?.source === FEED_SOURCE
        ) {
          return false;
        }
        const previous = target.filesByPath.get(mutation.path);
        const nextLogicalExtension =
          mutation.logicalExtension || previous?.logicalExtension || null;
        if (
          previous &&
          previous.logicalExtension === nextLogicalExtension &&
          previous.source === mutation.source
        ) {
          return false;
        }
        const next = Object.freeze({
          basename: basenameForPath(mutation.path),
          logicalExtension: nextLogicalExtension,
          path: mutation.path,
          source: mutation.source,
        });
        target.filesByPath.set(mutation.path, next);
        if (previous) {
          adjustSource(target.sourceSummary, previous.source, -1);
        }
        adjustSource(target.sourceSummary, mutation.source, 1);
        replacements.set(mutation.path, next);
        return true;
      }
      if (mutation.kind === "entry") {
        const path = mutation.entry.path;
        if (mutation.entry.gitignored === true && mutation.source !== NAVIGATION_SOURCE) {
          const previous = target.filesByPath.get(path);
          if (!previous || previous.source === NAVIGATION_SOURCE) {
            return false;
          }
          target.filesByPath.delete(path);
          adjustSource(target.sourceSummary, previous.source, -1);
          replacements.set(path, null);
          return true;
        }
        const previous = target.filesByPath.get(path);
        const logicalExtension =
          typeof mutation.entry.logical_ext === "string" && mutation.entry.logical_ext
            ? mutation.entry.logical_ext
            : previous?.logicalExtension || null;
        const basename = displayBasename(path, mutation.entry.name);
        if (
          previous &&
          previous.basename === basename &&
          previous.logicalExtension === logicalExtension &&
          previous.source === mutation.source
        ) {
          return false;
        }
        const next = Object.freeze({
          basename,
          logicalExtension,
          path,
          source: mutation.source,
        });
        target.filesByPath.set(path, next);
        if (previous) {
          adjustSource(target.sourceSummary, previous.source, -1);
        }
        adjustSource(target.sourceSummary, mutation.source, 1);
        replacements.set(path, next);
        return true;
      }
      if (mutation.kind === "delete") {
        const previous = target.filesByPath.get(mutation.path);
        if (!previous || (mutation.preserveNavigation && previous.source === NAVIGATION_SOURCE)) {
          return false;
        }
        target.filesByPath.delete(mutation.path);
        adjustSource(target.sourceSummary, previous.source, -1);
        replacements.set(mutation.path, null);
        return true;
      }
      return false;
    }

    /**
     * Replace the affected points in one pass over the canonical projection.
     * @param {CatalogState} target
     * @param {Map<string, Readonly<KnownFile> | null>} replacements
     */
    function mergePointReplacements(target, replacements) {
      const replacementPaths = [...replacements.keys()].sort(codeUnitCompare);
      const merged = [];
      let fileIndex = 0;
      let replacementIndex = 0;
      while (fileIndex < target.orderedFiles.length || replacementIndex < replacementPaths.length) {
        const file = target.orderedFiles[fileIndex];
        const path = replacementPaths[replacementIndex];
        if (path === undefined) {
          if (file) {
            merged.push(file);
            fileIndex += 1;
            continue;
          }
          break;
        }
        if (file && codeUnitCompare(file.path, path) < 0) {
          merged.push(file);
          fileIndex += 1;
          continue;
        }
        const replacement = replacements.get(path);
        if (replacement) {
          merged.push(replacement);
        }
        replacementIndex += 1;
        if (file?.path === path) {
          fileIndex += 1;
        }
      }
      target.orderedFiles = merged;
    }

    /**
     * Prove that a point run contains only strictly ordered new tail entries.
     * This is the common inventory-walk shape and can append in O(k); any
     * replacement, deletion, Unicode ordering inversion, or non-tail entry
     * falls back to the general ordered merge.
     * @param {CatalogState} target
     * @param {BulkConcurrentMutation[]} mutations
     */
    function isAppendablePointRun(target, mutations) {
      let previousPath = target.orderedFiles.at(-1)?.path || null;
      for (const mutation of mutations) {
        let path;
        if (mutation.kind === "put") {
          path = mutation.path;
        } else if (mutation.kind === "entry" && mutation.entry.gitignored !== true) {
          path = mutation.entry.path;
        } else {
          return false;
        }
        if (
          target.filesByPath.has(path) ||
          (previousPath !== null && codeUnitCompare(previousPath, path) >= 0)
        ) {
          return false;
        }
        previousPath = path;
      }
      return mutations.length > 0;
    }

    /**
     * Apply a consecutive point-mutation run while preserving its exact order.
     * @param {CatalogState} target
     * @param {BulkConcurrentMutation[]} mutations
     * @param {boolean} preserveFeedOwnership
     */
    function applyPointRun(target, mutations, preserveFeedOwnership = false) {
      if (isAppendablePointRun(target, mutations)) {
        ensureMutableFiles(target);
        let changed = false;
        for (const mutation of mutations) {
          if (mutation.kind === "put") {
            changed =
              putCanonicalInto(
                target,
                mutation.path,
                mutation.logicalExtension,
                mutation.source,
                true,
              ) || changed;
          } else if (mutation.kind === "entry") {
            changed =
              putCanonicalEntryInto(target, mutation.entry, mutation.source, true) || changed;
          }
        }
        return changed;
      }
      if (mutations.length < POINT_RUN_MERGE_MIN_ITEMS) {
        let changed = false;
        for (const mutation of mutations) {
          if (
            mutation.kind === "put" &&
            preserveFeedOwnership &&
            mutation.source === NAVIGATION_SOURCE &&
            target.filesByPath.get(mutation.path)?.source === FEED_SOURCE
          ) {
            continue;
          }
          changed = applyMutationNow(target, mutation) || changed;
        }
        return changed;
      }
      /** @type {Map<string, Readonly<KnownFile> | null>} */
      const replacements = new Map();
      let changed = false;
      for (const mutation of mutations) {
        changed =
          applyPointWithoutProjection(target, mutation, replacements, preserveFeedOwnership) ||
          changed;
      }
      if (replacements.size > 0) {
        mergePointReplacements(target, replacements);
      }
      return changed;
    }

    /**
     * Remove exact paths and directory descendants through the maintained
     * lexical projection. A miss is O(prefixes log entries), not a complete
     * catalog scan; workItems counts every candidate inspected or removed.
     *
     * Callers group only *consecutive* removes, so relative order with
     * interleaved upserts is preserved — `remove("dir")` then
     * `upsert("dir/child")` still keeps the child.
     * @param {CatalogState} target
     * @param {readonly string[]} paths
     */
    function removeManyFrom(target, paths) {
      const removed = normalizeRemovalPaths(paths);
      if (removed.length === 0) {
        return { candidateVisits: 0, changed: false, workItems: 0 };
      }
      const ranges = removalRanges(target.orderedFiles, removed);
      const candidateVisits = ranges.reduce((total, range) => total + range.end - range.start, 0);
      let workItems = candidateVisits;
      if (ranges.length === 0) {
        return { candidateVisits, changed: false, workItems };
      }
      ensureMutableFiles(target);
      // One forward compaction: every retained row after the first interval
      // moves at most once, however many intervals there are. Splicing each
      // interval would shift the whole suffix once per interval instead.
      const files = target.orderedFiles;
      let write = ranges[0].start;
      let read = write;
      for (const range of ranges) {
        while (read < range.start) {
          files[write] = files[read];
          write += 1;
          read += 1;
        }
        for (; read < range.end; read += 1) {
          const file = files[read];
          workItems += 1;
          target.filesByPath.delete(file.path);
          adjustSource(target.sourceSummary, file.source, -1);
        }
      }
      while (read < files.length) {
        files[write] = files[read];
        write += 1;
        read += 1;
      }
      files.length = write;
      return { candidateVisits, changed: true, workItems };
    }

    /** @param {readonly string[]} paths */
    function removeManyWithoutRevision(paths) {
      const normalized = normalizeRemovalPaths(paths);
      if (normalized.length === 0) {
        return { candidateVisits: 0, changed: false, workItems: 0 };
      }
      if (activeBulkApplication) {
        activeBulkApplication.record({ kind: "remove", paths: new Set(normalized) });
        return { candidateVisits: 0, changed: false, workItems: 0 };
      }
      return removeManyFrom(state, normalized);
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
      if (activeBulkApplication) {
        for (const mutation of eventChangeMutations(ops)) {
          activeBulkApplication.record(mutation);
        }
        return Object.freeze({ candidateVisits: 0, changed: false, workItems: 0 });
      }
      return applyMutationsDirect(eventChangeMutations(ops));
    }

    /** @param {string} path @param {string | null} logicalExtension */
    function observeNavigation(path, logicalExtension) {
      if (put(path, logicalExtension, NAVIGATION_SOURCE)) {
        bumpRevision();
      }
    }

    /** @param {CatalogChangePayload} payload */
    function catalogChangeMutations(payload) {
      /** @type {BulkConcurrentMutation[]} */
      const mutations = [];
      for (const upsert of payload?.upserts || []) {
        if (isCanonicalFilePath(upsert?.p)) {
          mutations.push({
            kind: "put",
            logicalExtension: upsert.e || null,
            path: upsert.p,
            source: "catalog-event",
          });
        }
      }
      for (const path of payload?.remove_files || []) {
        if (isCanonicalFilePath(path)) {
          mutations.push({ kind: "delete", path, preserveNavigation: true });
        }
      }
      for (const path of payload?.non_file_paths || []) {
        if (isCanonicalFilePath(path)) {
          mutations.push({ kind: "delete", path, preserveNavigation: false });
        }
      }
      const removes = normalizeRemovalPaths(payload?.removes || []);
      if (removes.length > 0) {
        mutations.push({ kind: "remove", paths: new Set(removes) });
      }
      return mutations;
    }

    /** @param {EventChangeOperation[]} ops */
    function eventChangeMutations(ops) {
      /** @type {BulkConcurrentMutation[]} */
      const mutations = [];
      /** @type {string[]} */
      let removals = [];
      function flushRemovals() {
        const normalized = normalizeRemovalPaths(removals);
        removals = [];
        if (normalized.length > 0) {
          mutations.push({ kind: "remove", paths: new Set(normalized) });
        }
      }
      for (const op of ops) {
        if (op.op === "upsert" && op.entry?.type === "file" && isCanonicalFilePath(op.entry.path)) {
          flushRemovals();
          mutations.push({ kind: "entry", entry: op.entry, source: "event-change" });
        } else if (op.op === "remove" && isCanonicalFilePath(op.path)) {
          removals.push(op.path);
        }
      }
      flushRemovals();
      return mutations;
    }

    /** @param {CatalogState} target @param {BulkConcurrentMutation} mutation */
    function applyMutationNow(target, mutation) {
      if (mutation.kind === "put") {
        return putInto(target, mutation.path, mutation.logicalExtension, mutation.source);
      }
      if (mutation.kind === "entry") {
        return putEntryInto(target, mutation.entry, mutation.source);
      }
      if (mutation.kind === "delete") {
        return deleteExactFrom(target, mutation.path, mutation.preserveNavigation);
      }
      if (mutation.kind === "remove") {
        return removeManyFrom(target, [...mutation.paths]).changed;
      }
      const next = nextCoverage(catalogCoverage, mutation.value);
      const changed = catalogCoverage !== next;
      catalogCoverage = next;
      return changed;
    }

    /**
     * Apply one already-preflighted steady-state change synchronously.
     * Consecutive point changes merge once; subtree ranges retain their
     * ordering boundary and measured candidate volume.
     * @param {BulkConcurrentMutation[]} mutations
     */
    function applyMutationsDirect(mutations) {
      let changed = false;
      let candidateVisits = 0;
      let workItems = 0;
      /** @type {BulkConcurrentMutation[]} */
      let points = [];
      function flushPoints() {
        if (points.length === 0) {
          return;
        }
        changed = applyPointRun(state, points) || changed;
        workItems += points.length;
        points = [];
      }
      for (const mutation of mutations) {
        if (mutation.kind === "remove") {
          flushPoints();
          const removal = removeManyFrom(state, [...mutation.paths]);
          changed = removal.changed || changed;
          candidateVisits += removal.candidateVisits;
          workItems += removal.workItems;
        } else if (mutation.kind === "coverage") {
          flushPoints();
          changed = applyMutationNow(state, mutation) || changed;
          workItems += 1;
        } else {
          points.push(mutation);
        }
      }
      flushPoints();
      if (changed) {
        bumpRevision();
      }
      return Object.freeze({ candidateVisits, changed, workItems });
    }

    /** @param {BulkConcurrentMutation[]} mutations @param {number} maxWorkItems */
    function needsSlicedApplication(mutations, maxWorkItems) {
      const directLimit = Math.min(DIRECT_CHANGE_MAX_ITEMS, maxWorkItems);
      let workItems = mutations.length;
      for (const mutation of mutations) {
        if (mutation.kind !== "remove") {
          continue;
        }
        const ranges = removalRanges(state.orderedFiles, [...mutation.paths]);
        workItems += ranges.reduce((total, range) => total + 2 * (range.end - range.start), 0);
        if (workItems > directLimit) {
          return true;
        }
      }
      return workItems > directLimit;
    }

    /**
     * Start applying one `/api/catalog` payload through explicitly bounded
     * steps. The caller owns task scheduling; the bulk stage stays invisible
     * until ingestion and concurrent-mutation replay both finish.
     *
     * @param {Array<{p: string, e: string, n?: string}>} files
     * @param {CatalogCoverage} bulkCoverage the root coverage this payload
     *   establishes; it can raise, but never lower, the current coverage
     * @param {boolean} authoritative whether omitted feed paths are stale
     * @returns {BulkSnapshotApplication}
     */
    function beginBulkSnapshot(files, bulkCoverage, authoritative = false) {
      if (!COVERAGE_RANK.has(bulkCoverage)) {
        throw new TypeError("Bulk catalog snapshot requires a coverage state");
      }
      activeBulkApplication?.cancel();
      const stagedState = emptyState();
      /** @type {CatalogCoverage} */
      let stagedCoverage =
        coverageRank(bulkCoverage) > coverageRank(catalogCoverage) ? bulkCoverage : catalogCoverage;
      let fileIndex = 0;
      // Pin the baseline projection. Direct observations join the stage and
      // replay into live state only if the transaction is canceled, so this
      // iterator cannot be perturbed between scheduled slices.
      Object.freeze(state.orderedFiles);
      const baseFiles = state.orderedFiles;
      let baseIndex = 0;
      /** @type {"base" | "files" | "sort" | "merge" | "mutations"} */
      let phase = "base";
      /**
       * Natural UTF-16-ordered runs from the provider's UTF-8-ordered input.
       * @type {Readonly<KnownFile>[][]}
       */
      let feedRuns = [];
      /** @type {Readonly<KnownFile>[][]} */
      let nextFeedRuns = [];
      let feedRunIndex = 0;
      /** @type {{left: Readonly<KnownFile>[], right: Readonly<KnownFile>[],
       *   leftIndex: number, rightIndex: number, merged: Readonly<KnownFile>[]} | null} */
      let feedRunMerge = null;
      /** @type {Readonly<KnownFile>[]} */
      let projectionBase = [];
      /** @type {Readonly<KnownFile>[]} */
      let projectionFeed = [];
      /** @type {Readonly<KnownFile>[]} */
      let mergedProjection = [];
      let projectionBaseIndex = 0;
      let projectionFeedIndex = 0;
      /** @type {BulkConcurrentMutation[]} */
      const concurrentMutations = [];
      /** @type {BulkConcurrentMutation[]} */
      const liveMutations = [];
      let mutationIndex = 0;
      /** @type {{paths: string[], prefixIndex: number,
       *   ranges: Array<{start: number, end: number}>, rangeIndex: number,
       *   read: number, write: number, phase: "seek" | "compact"} | null} */
      let removal = null;
      let finished = false;
      let cancelled = false;

      /**
       * Stage one feed row without mutating the ordered projection. The
       * provider sorts valid paths by UTF-8 bytes, while the browser's public
       * model sorts UTF-16 code units. Recording maximal natural runs here
       * makes the common ASCII case one run and leaves every cross-runtime
       * ordering inversion to the bounded merge phase.
       * @param {{p: string, e: string, n?: string}} file
       */
      function stageFeedFile(file) {
        if (!isCanonicalFilePath(file?.p)) {
          return;
        }
        const previous = stagedState.filesByPath.get(file.p);
        const logicalExtension = file.e || previous?.logicalExtension || null;
        if (
          previous &&
          previous.logicalExtension === logicalExtension &&
          previous.source === FEED_SOURCE
        ) {
          return;
        }
        const next = Object.freeze({
          basename: displayBasename(file.p, file.n),
          logicalExtension,
          path: file.p,
          source: FEED_SOURCE,
        });
        stagedState.filesByPath.set(file.p, next);
        if (previous) {
          adjustSource(stagedState.sourceSummary, previous.source, -1);
        }
        adjustSource(stagedState.sourceSummary, FEED_SOURCE, 1);

        let run = feedRuns.at(-1);
        if (run && codeUnitCompare(run.at(-1)?.path || "", next.path) >= 0) {
          run = undefined;
        }
        if (!run) {
          run = [];
          feedRuns.push(run);
        }
        run.push(next);
      }

      /** Move from feed ingestion or sorting to the final baseline merge. */
      function beginProjectionMerge() {
        const sortedFeed = feedRuns[0] || [];
        if (sortedFeed.length === 0) {
          phase = "mutations";
          return;
        }
        if (
          stagedState.orderedFiles.length === 0 &&
          sortedFeed.length === stagedState.filesByPath.size
        ) {
          // An empty catalog has no retained navigation exceptions. Its
          // single natural run is already the exact immutable projection, so
          // walking every row again would turn one
          // 300k-row delivery into 600k main-thread work items. The size check
          // keeps duplicate/replacement paths on the filtering merge below.
          stagedState.orderedFiles = sortedFeed;
          phase = "mutations";
          return;
        }
        projectionBase = stagedState.orderedFiles;
        projectionFeed = sortedFeed;
        mergedProjection = [];
        projectionBaseIndex = 0;
        projectionFeedIndex = 0;
        phase = "merge";
      }

      /** Publish one immutable state and one complete subscriber view. */
      function finish() {
        Object.freeze(stagedState.orderedFiles);
        state = stagedState;
        catalogCoverage = stagedCoverage;
        finished = true;
        if (activeBulkApplication?.cancel === cancel) {
          activeBulkApplication = null;
        }
        // Building the stage was invisible. Prepare the O(1) snapshot before
        // the queued invalidation so a subscriber cannot pull sorting work
        // into the measured final application slice.
        bumpRevision(true);
        snapshot();
      }

      /** @param {BulkConcurrentMutation} mutation */
      function record(mutation) {
        if (!finished) {
          concurrentMutations.push(mutation);
          liveMutations.push(mutation);
        }
      }

      /** Fold a same-generation stream delta into this transaction.
       * @param {CatalogChangePayload} payload
       */
      function enqueueCatalogChange(payload) {
        for (const mutation of catalogChangeMutations(payload)) {
          concurrentMutations.push(mutation);
        }
      }

      /** Fold a same-generation `fs.change` batch into this transaction.
       * @param {EventChangeOperation[]} ops
       */
      function enqueueEventChange(ops) {
        for (const mutation of eventChangeMutations(ops)) {
          concurrentMutations.push(mutation);
        }
      }

      /** @param {number} maxWorkItems */
      function step(maxWorkItems) {
        if (finished) {
          return Object.freeze({ candidateVisits: 0, cancelled, done: true, workItems: 0 });
        }
        if (!Number.isFinite(maxWorkItems) || maxWorkItems < 1) {
          throw new TypeError("Bulk catalog step requires a positive work-item bound");
        }
        const limit = Math.floor(maxWorkItems);
        let workItems = 0;
        let candidateVisits = 0;
        let pointMutations = 0;

        while (workItems < limit) {
          if (phase === "base") {
            const knownFile = baseFiles[baseIndex];
            if (!knownFile) {
              phase = "files";
              continue;
            }
            baseIndex += 1;
            workItems += 1;
            if (!authoritative || knownFile.source === NAVIGATION_SOURCE) {
              // The pinned baseline is already canonical and unique. An
              // authoritative feed retains only explicit-navigation
              // exceptions; a merging feed retains every prior observation.
              stagedState.filesByPath.set(knownFile.path, knownFile);
              stagedState.orderedFiles.push(knownFile);
              adjustSource(stagedState.sourceSummary, knownFile.source, 1);
            }
            continue;
          }

          if (phase === "files") {
            if (fileIndex >= files.length) {
              if (feedRuns.length > 1) {
                nextFeedRuns = [];
                feedRunIndex = 0;
                phase = "sort";
              } else {
                beginProjectionMerge();
              }
              continue;
            }
            const file = files[fileIndex];
            fileIndex += 1;
            workItems += 1;
            if (file) {
              stageFeedFile(file);
            }
            continue;
          }

          if (phase === "sort") {
            if (!feedRunMerge) {
              if (feedRunIndex >= feedRuns.length) {
                feedRuns = nextFeedRuns;
                nextFeedRuns = [];
                feedRunIndex = 0;
                if (feedRuns.length <= 1) {
                  beginProjectionMerge();
                }
                continue;
              }
              const left = feedRuns[feedRunIndex];
              const right = feedRuns[feedRunIndex + 1];
              if (!right) {
                nextFeedRuns.push(left);
                feedRunIndex += 1;
                continue;
              }
              feedRunMerge = {
                left,
                leftIndex: 0,
                merged: [],
                right,
                rightIndex: 0,
              };
            }
            const left = feedRunMerge.left[feedRunMerge.leftIndex];
            const right = feedRunMerge.right[feedRunMerge.rightIndex];
            if (!left && !right) {
              nextFeedRuns.push(feedRunMerge.merged);
              feedRunIndex += 2;
              feedRunMerge = null;
              continue;
            }
            if (!right || (left && codeUnitCompare(left.path, right.path) <= 0)) {
              feedRunMerge.merged.push(left);
              feedRunMerge.leftIndex += 1;
            } else {
              feedRunMerge.merged.push(right);
              feedRunMerge.rightIndex += 1;
            }
            workItems += 1;
            continue;
          }

          if (phase === "merge") {
            const baseFile = projectionBase[projectionBaseIndex];
            const feedFile = projectionFeed[projectionFeedIndex];
            if (!baseFile && !feedFile) {
              stagedState.orderedFiles = mergedProjection;
              phase = "mutations";
              continue;
            }
            let candidate;
            if (!feedFile || (baseFile && codeUnitCompare(baseFile.path, feedFile.path) <= 0)) {
              candidate = baseFile;
              projectionBaseIndex += 1;
            } else {
              candidate = feedFile;
              projectionFeedIndex += 1;
            }
            // Duplicate feed rows and replaced baseline rows remain in their
            // input arrays, but only the final map-owned object is published.
            if (candidate && stagedState.filesByPath.get(candidate.path) === candidate) {
              mergedProjection.push(candidate);
            }
            workItems += 1;
            continue;
          }

          if (removal) {
            const files = stagedState.orderedFiles;
            if (removal.phase === "seek") {
              const path = removal.paths[removal.prefixIndex];
              if (path !== undefined) {
                // Binary searches only; each path is one charged item.
                appendRemovalIntervals(files, path, removal.ranges);
                removal.prefixIndex += 1;
                workItems += 1;
                continue;
              }
              removal.ranges = sortedDisjointRanges(removal.ranges);
              workItems += removal.ranges.length;
              if (removal.ranges.length === 0) {
                removal = null;
                mutationIndex += 1;
                continue;
              }
              removal.rangeIndex = 0;
              removal.read = removal.ranges[0].start;
              removal.write = removal.read;
              removal.phase = "compact";
              continue;
            }
            // Delete interval rows and slide retained rows left in one
            // forward pass. Every row visited, removed or moved, is charged,
            // so a scattered removal cannot shift the whole suffix per
            // interval inside one slice.
            const range = removal.ranges[removal.rangeIndex];
            if (range && removal.read >= range.end) {
              removal.rangeIndex += 1;
              continue;
            }
            if (range && removal.read >= range.start) {
              const file = files[removal.read];
              removal.read += 1;
              workItems += 1;
              candidateVisits += 1;
              if (file && stagedState.filesByPath.delete(file.path)) {
                adjustSource(stagedState.sourceSummary, file.source, -1);
              }
              continue;
            }
            if (removal.read < files.length) {
              files[removal.write] = files[removal.read];
              removal.write += 1;
              removal.read += 1;
              workItems += 1;
              continue;
            }
            files.length = removal.write;
            removal = null;
            mutationIndex += 1;
            continue;
          }

          const mutation = concurrentMutations[mutationIndex];
          if (!mutation) {
            finish();
            return Object.freeze({ candidateVisits, cancelled: false, done: true, workItems });
          }
          if (mutation.kind === "coverage") {
            if (pointMutations >= DIRECT_CHANGE_MAX_ITEMS) {
              return Object.freeze({ candidateVisits, cancelled: false, done: false, workItems });
            }
            stagedCoverage = nextCoverage(stagedCoverage, mutation.value);
            mutationIndex += 1;
            pointMutations += 1;
            workItems += 1;
          } else {
            if (mutation.kind === "remove") {
              removal = {
                paths: normalizeRemovalPaths([...mutation.paths]),
                phase: "seek",
                prefixIndex: 0,
                rangeIndex: 0,
                ranges: [],
                read: 0,
                write: 0,
              };
              continue;
            }
            const availableItems = limit - workItems;
            /** @type {BulkConcurrentMutation[]} */
            let points = [];
            while (points.length < availableItems) {
              const point = concurrentMutations[mutationIndex + points.length];
              if (!point || point.kind === "remove" || point.kind === "coverage") {
                break;
              }
              points.push(point);
            }
            let appendable = isAppendablePointRun(stagedState, points);
            if (!appendable) {
              const pointLimit = DIRECT_CHANGE_MAX_ITEMS - pointMutations;
              if (pointLimit < 1) {
                return Object.freeze({
                  candidateVisits,
                  cancelled: false,
                  done: false,
                  workItems,
                });
              }
              points = points.slice(0, pointLimit);
              appendable = isAppendablePointRun(stagedState, points);
            }
            applyPointRun(stagedState, points, true);
            mutationIndex += points.length;
            if (!appendable) {
              pointMutations += points.length;
            }
            workItems += points.length;
          }
        }

        return Object.freeze({ candidateVisits, cancelled: false, done: false, workItems });
      }

      function cancel() {
        if (finished) {
          return;
        }
        finished = true;
        cancelled = true;
        if (activeBulkApplication?.cancel === cancel) {
          activeBulkApplication = null;
        }
        // Stream-generation work belongs to the discarded stage. Independent
        // tree/navigation observations do not: replay only those direct
        // mutations into the still-live state after detaching the recorder.
        if (liveMutations.length > 0) {
          applyMutationsDirect(liveMutations);
        }
      }

      activeBulkApplication = { cancel, record };
      return Object.freeze({ cancel, enqueueCatalogChange, enqueueEventChange, step });
    }

    /**
     * Return a staged application only when a steady-state catalog delta can
     * exceed the caller's synchronous work budget. Small point changes stay
     * on the direct COW path instead of cloning the complete Map.
     * @param {CatalogChangePayload} payload
     * @param {number} maxWorkItems
     */
    function beginCatalogChange(payload, maxWorkItems) {
      const mutations = catalogChangeMutations(payload);
      if (!needsSlicedApplication(mutations, maxWorkItems)) {
        return null;
      }
      const application = beginBulkSnapshot([], "partial", false);
      application.enqueueCatalogChange(payload);
      return application;
    }

    /** @param {EventChangeOperation[]} ops @param {number} maxWorkItems */
    function beginEventChange(ops, maxWorkItems) {
      const mutations = eventChangeMutations(ops);
      if (!needsSlicedApplication(mutations, maxWorkItems)) {
        return null;
      }
      const application = beginBulkSnapshot([], "partial", false);
      application.enqueueEventChange(ops);
      return application;
    }

    /**
     * Apply one `catalog.change` event from the live stream.
     * @param {{upserts?: Array<{p: string, e: string}>, removes?: string[],
     *   remove_files?: string[], non_file_paths?: string[]}} payload
     */
    function applyCatalogChange(payload) {
      if (activeBulkApplication) {
        for (const mutation of catalogChangeMutations(payload)) {
          activeBulkApplication.record(mutation);
        }
        return Object.freeze({ candidateVisits: 0, changed: false, workItems: 0 });
      }
      return applyMutationsDirect(catalogChangeMutations(payload));
    }

    /**
     * Flip completeness without new data: the walk finished after an
     * incomplete bulk fetch, and live ops already converged the
     * contents.
     */
    function markComplete() {
      setCoverage("complete");
    }

    /**
     * The walk finished at its file cap after an incomplete bulk fetch. Live
     * ops already converged membership to the index, which is final but does
     * not cover the root. A complete catalog stays complete.
     */
    function markTruncated() {
      setCoverage("truncated");
    }

    /** Retain membership while a new stream re-establishes root coverage. */
    function markIncomplete() {
      setCoverage("partial");
    }

    /** @param {CatalogCoverage} coverage */
    function setCoverage(coverage) {
      if (activeBulkApplication) {
        activeBulkApplication.record({ kind: "coverage", value: coverage });
        return;
      }
      const next = nextCoverage(catalogCoverage, coverage);
      if (next !== catalogCoverage) {
        catalogCoverage = next;
        bumpRevision();
      }
    }

    /**
     * Remove a file or every known descendant of a directory path.
     * @param {string} path
     */
    function removePath(path) {
      if (removeWithoutRevision(path).changed) {
        bumpRevision();
      }
    }

    /** Clear observations after a root swap or resynchronization boundary. */
    function clear() {
      activeBulkApplication?.cancel();
      state = emptyState();
      catalogCoverage = "partial";
      bumpRevision();
    }

    /**
     * Return a stable, immutable view in canonical UTF-16 code-unit path
     * order. The maintained projection makes this O(1) in catalog size;
     * memoization preserves object identity while nothing changed.
     */
    function snapshot() {
      if (memoizedSnapshot && memoizedSnapshot.revision === revision) {
        return memoizedSnapshot;
      }
      Object.freeze(state.orderedFiles);
      memoizedSnapshot = Object.freeze({
        complete: catalogCoverage === "complete",
        files: state.orderedFiles,
        observedCount: state.orderedFiles.length,
        revision,
        sourceSummary: Object.freeze({ ...state.sourceSummary }),
        truncated: catalogCoverage === "truncated",
      });
      return memoizedSnapshot;
    }

    return Object.freeze({
      applyCatalogChange,
      applyEventChange,
      beginBulkSnapshot,
      beginCatalogChange,
      beginEventChange,
      clear,
      markComplete,
      markIncomplete,
      markTruncated,
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
