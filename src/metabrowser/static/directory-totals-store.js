// Public, inventory-backed directory totals cache.
//
// The shell applies each SSE snapshot/change batch before it announces the
// inventory event. Folder plugins can therefore paint complete directory
// totals synchronously without reaching into app.js's private FileStore.

((global) => {
  /** @typedef {Readonly<{path: string, revision: number, state: "pending" | "complete", totalFiles: number, totalBytes: number, unignoredFiles: number, unignoredBytes: number}>} DirectoryTotals */
  const host = /** @type {Window & typeof globalThis} */ (global);
  if (host.metabrowserDirectoryTotalsStore) {
    return;
  }

  /** @type {Map<string, DirectoryTotals>} */
  let totals = new Map();
  /** @type {Map<string, Set<(value: DirectoryTotals | null) => void>>} */
  const subscribers = new Map();
  let revision = 0;

  /** @param {unknown} value */
  const nonnegativeInteger = (value) =>
    Number.isInteger(value) && /** @type {number} */ (value) >= 0
      ? /** @type {number} */ (value)
      : null;

  /** @param {unknown} raw @returns {DirectoryTotals | null} */
  function normalize(raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      return null;
    }
    const entry = /** @type {Record<string, unknown>} */ (raw);
    if (entry.type !== "dir" || typeof entry.path !== "string") {
      return null;
    }
    const totalFiles = nonnegativeInteger(entry.total_files);
    const totalBytes = nonnegativeInteger(entry.total_size);
    const unignoredFiles = nonnegativeInteger(entry.unignored_files);
    const unignoredBytes = nonnegativeInteger(entry.unignored_size);
    const complete =
      totalFiles !== null &&
      totalBytes !== null &&
      unignoredFiles !== null &&
      unignoredBytes !== null;
    return Object.freeze({
      path: entry.path,
      revision,
      state: complete ? "complete" : "pending",
      totalFiles: totalFiles ?? 0,
      totalBytes: totalBytes ?? 0,
      unignoredFiles: unignoredFiles ?? 0,
      unignoredBytes: unignoredBytes ?? 0,
    });
  }

  /** @param {string} path */
  function publish(path) {
    for (const listener of subscribers.get(path) ?? []) {
      try {
        listener(totals.get(path) ?? null);
      } catch (_error) {
        // A plugin listener cannot interrupt delivery to other views.
      }
    }
  }

  /** @param {ReadonlyArray<unknown>} entries */
  function applySnapshot(entries) {
    revision += 1;
    const previousPaths = new Set(totals.keys());
    const next = new Map();
    for (const entry of entries) {
      const value = normalize(entry);
      if (value) {
        next.set(/** @type {string} */ (value.path), value);
        previousPaths.delete(/** @type {string} */ (value.path));
      }
    }
    totals = next;
    const changed = new Set([...totals.keys(), ...previousPaths]);
    for (const path of changed) {
      publish(path);
    }
  }

  /** @param {ReadonlyArray<Record<string, any>>} ops */
  function applyChange(ops) {
    revision += 1;
    const changed = new Set();
    for (const op of ops) {
      if (op?.op === "upsert") {
        const value = normalize(op.entry);
        if (value) {
          const path = /** @type {string} */ (value.path);
          totals.set(path, value);
          changed.add(path);
        }
      } else if (op?.op === "remove" && typeof op.path === "string") {
        if (totals.delete(op.path)) {
          changed.add(op.path);
        }
      }
    }
    for (const path of changed) {
      publish(path);
    }
  }

  /** @param {string} path */
  function get(path) {
    return totals.get(path) ?? null;
  }

  /**
   * @param {string} path
   * @param {(value: DirectoryTotals | null) => void} listener
   */
  function subscribe(path, listener) {
    let listeners = subscribers.get(path);
    if (!listeners) {
      listeners = new Set();
      subscribers.set(path, listeners);
    }
    listeners.add(listener);
    listener(get(path));
    return () => {
      listeners.delete(listener);
      if (listeners.size === 0) {
        subscribers.delete(path);
      }
    };
  }

  host.metabrowserDirectoryTotalsStore = Object.freeze({
    applyChange,
    applySnapshot,
    get,
    subscribe,
  });
})(typeof window !== "undefined" ? window : globalThis);
