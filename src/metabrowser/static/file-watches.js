// File watches on the page's event stream (docs/project/architecture/arch-live-delivery.md,
// "File Watches"): the paths this page watches, each registered on the connection its
// one /api/events stream named in its last `fs.snapshot`, and the `file.changed` events
// that stream carries back.
//
// On demand, as the `file-watches` bundle in server.py, not a startup script: only a view
// that shows a live file (a table, a container's children) asks for it, through
// `metabrowser.watchFile`. app.js hands it each snapshot's connection and each change.
//
// A watch is registered with the generation its reader holds, and the server answers the
// generation now, so a change between the reader's read and the registration reaches it.
// Each new connection, after a reconnect, a resync, a page restored from Back, or a server
// restart, registers every watch again with the generation it holds; a registration on a
// connection the server does not know waits for the next snapshot.

(() => {
  if (window.MetabrowserFileWatches) {
    return;
  }

  /** @typedef {MetabrowserFileChange} FileChange */
  /** @typedef {MetabrowserFileWatchState} WatchState */
  /** @typedef {MetabrowserFileWatchListener} WatchListener */
  /** @typedef {{status: number, body: unknown}} WatchAnswer */
  /**
   * @typedef {{
   *   generation: string | null | undefined,
   *   listeners: Set<WatchListener>,
   *   state: WatchState,
   *   reason: string | null,
   *   asked: number,
   * }} Watch
   */

  /**
   * The page's watches over one way to reach the server.
   *
   * @param {{
   *   post: (body: Record<string, unknown>) => Promise<WatchAnswer>,
   *   connection?: string | null,
   * }} deps
   */
  function createFileWatches(deps) {
    let connection = deps.connection ?? null;
    /** @type {Map<string, Watch>} */
    const watches = new Map();
    // Each path's last request, so an unregistration and the registration after it reach
    // the server in the order they were made.
    /** @type {Map<string, Promise<unknown>>} */
    const lastRequest = new Map();
    let asks = 0;

    /**
     * @param {string} path
     * @param {Record<string, unknown>} body
     * @returns {Promise<WatchAnswer>}
     */
    function send(path, body) {
      const request = (lastRequest.get(path) ?? Promise.resolve()).then(
        () => deps.post(body),
        () => deps.post(body),
      );
      lastRequest.set(path, request);
      const forget = () => {
        if (lastRequest.get(path) === request) {
          lastRequest.delete(path);
        }
      };
      request.then(forget, forget);
      return request;
    }

    /**
     * @param {Watch} watch
     * @param {WatchState} state
     * @param {string | null} reason
     */
    function setState(watch, state, reason) {
      if (watch.state === state && watch.reason === reason) {
        return;
      }
      watch.state = state;
      watch.reason = reason;
      for (const listener of [...watch.listeners]) {
        listener.onState?.(state, reason);
      }
    }

    /**
     * @param {Watch} watch
     * @param {FileChange} change
     */
    function notify(watch, change) {
      for (const listener of [...watch.listeners]) {
        try {
          listener.onChange(change);
        } catch (error) {
          console.warn("metabrowser: a file watch's listener failed", error);
        }
      }
    }

    /**
     * @param {string} path
     * @param {Watch} watch
     */
    function register(path, watch) {
      if (connection === null) {
        setState(watch, "waiting", null);
        return;
      }
      const ask = ++asks;
      watch.asked = ask;
      /** @type {Record<string, unknown>} */
      const body = { connection, path };
      if (watch.generation !== undefined) {
        body.generation = watch.generation;
      }
      send(path, body).then(
        (answer) => settle(path, watch, ask, answer),
        () => {
          if (watches.get(path) === watch && watch.asked === ask) {
            // The next snapshot registers it again.
            setState(watch, "waiting", "unreachable");
          }
        },
      );
    }

    /**
     * @param {string} path
     * @param {Watch} watch
     * @param {number} ask
     * @param {WatchAnswer} answer
     */
    function settle(path, watch, ask, answer) {
      if (watches.get(path) !== watch || watch.asked !== ask) {
        return;
      }
      const body = /** @type {{generation?: unknown, code?: unknown} | null} */ (answer.body);
      if (answer.status === 200) {
        const generation = typeof body?.generation === "string" ? body.generation : null;
        const held = watch.generation;
        watch.generation = generation;
        setState(watch, "live", null);
        if (held !== undefined && held !== generation) {
          notify(watch, { path, generation });
        }
        return;
      }
      const code = typeof body?.code === "string" ? body.code : `status ${answer.status}`;
      // An id from a stream that ended, or a server that restarted: the next snapshot's.
      setState(watch, code === "unknown_connection" ? "waiting" : "refused", code);
    }

    return Object.freeze({
      /**
       * Watch *path*; *generation* is the one the reader read, when it has one.
       *
       * @param {string} path
       * @param {WatchListener} listener
       * @param {string | null} [generation]
       * @returns {() => void}
       */
      watch(path, listener, generation) {
        let watch = watches.get(path);
        if (watch) {
          watch.listeners.add(listener);
          listener.onState?.(watch.state, watch.reason);
          const held = watch.generation;
          if (generation !== undefined && held !== undefined && generation !== held) {
            // This reader read another generation than the watch holds: tell it.
            void Promise.resolve().then(() => {
              if (watch?.listeners.has(listener)) {
                listener.onChange({ path, generation: held });
              }
            });
          }
        } else {
          watch = {
            generation,
            listeners: new Set([listener]),
            state: "waiting",
            reason: null,
            asked: 0,
          };
          watches.set(path, watch);
          register(path, watch);
        }
        const owned = watch;
        return () => {
          if (!owned.listeners.delete(listener) || owned.listeners.size > 0) {
            return;
          }
          watches.delete(path);
          owned.asked = -1;
          if (connection !== null && owned.state === "live") {
            send(path, { connection, path, watch: false }).catch(() => {});
          }
        };
      },

      /**
       * The stream's new connection: register every watch on it.
       *
       * @param {string | null} id
       */
      connected(id) {
        connection = id;
        for (const [path, watch] of watches) {
          register(path, watch);
        }
      },

      /**
       * A `file.changed` the stream carried.
       *
       * @param {FileChange} change
       */
      changed(change) {
        const watch = watches.get(change.path);
        if (!watch || watch.generation === change.generation) {
          return;
        }
        watch.generation = change.generation;
        notify(watch, change);
      },

      /** Each watch as the page holds it, for a session to read. */
      describe() {
        return [...watches].map(([path, watch]) =>
          Object.freeze({
            path,
            state: watch.state,
            reason: watch.reason,
            generation: watch.generation ?? null,
            listeners: watch.listeners.size,
          }),
        );
      },
    });
  }

  /**
   * @param {Record<string, unknown>} body
   * @returns {Promise<WatchAnswer>}
   */
  async function post(body) {
    const response = await fetch("/api/events/watch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    /** @type {unknown} */
    let answer = null;
    try {
      answer = await response.json();
    } catch {
      answer = null;
    }
    return { status: response.status, body: answer };
  }

  /** @type {ReturnType<typeof createFileWatches> | null} */
  let shared = null;

  window.MetabrowserFileWatches = Object.freeze({
    createFileWatches,
    /** The page's watches, made on first use over the stream's last connection. */
    shared() {
      shared ??= createFileWatches({ post, connection: window.metabrowserEventConnection ?? null });
      return shared;
    },
    /** @param {string | null} id */
    connected(id) {
      shared?.connected(id);
    },
    /** @param {FileChange} change */
    changed(change) {
      shared?.changed(change);
    },
  });
})();
