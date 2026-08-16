/** @typedef {{publish: (value: unknown) => void, subscribe: (listener: (value: unknown) => void) => () => void, release: () => void}} FolderRollupProjection */

/**
 * Share the latest validated rollup projection among panels mounted for one path.
 *
 * The pool does not fetch data. The File Breakdown remains the single rollup
 * watcher and publishes projections for lightweight sibling views.
 */
export function createFolderRollupProjectionPool() {
  /** @type {Map<string, {refs: number, current: unknown, listeners: Set<(value: unknown) => void>}>} */
  const sessions = new Map();
  return Object.freeze({
    /** @param {string} path @returns {FolderRollupProjection} */
    acquire(path) {
      let session = sessions.get(path);
      if (!session) {
        session = { refs: 0, current: undefined, listeners: new Set() };
        sessions.set(path, session);
      }
      session.refs += 1;
      let released = false;
      /** @type {Set<(value: unknown) => void>} */
      const ownedListeners = new Set();
      return Object.freeze({
        /** @param {unknown} value */
        publish(value) {
          if (released) {
            return;
          }
          session.current = value;
          for (const listener of [...session.listeners]) {
            try {
              listener(value);
            } catch (error) {
              console.warn("Folder rollup projection listener failed.", error);
            }
          }
        },
        /** @param {(value: unknown) => void} listener */
        subscribe(listener) {
          if (released) {
            throw new TypeError("cannot subscribe to a released rollup projection");
          }
          session.listeners.add(listener);
          ownedListeners.add(listener);
          if (session.current !== undefined) {
            listener(session.current);
          }
          return () => {
            ownedListeners.delete(listener);
            session.listeners.delete(listener);
          };
        },
        release() {
          if (released) {
            return;
          }
          released = true;
          for (const listener of ownedListeners) {
            session.listeners.delete(listener);
          }
          ownedListeners.clear();
          session.refs -= 1;
          if (session.refs === 0) {
            sessions.delete(path);
          }
        },
      });
    },
  });
}
