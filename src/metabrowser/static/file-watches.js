// File watches on the page's event stream (docs/project/architecture/arch-live-delivery.md,
// "File Watches"): the paths this page watches, each registered on the connection its
// one /api/events stream named in its last `fs.snapshot`, and the `file.changed` events
// that stream carries back.
//
// On demand, as the `file-watches` bundle in server.py, not a startup script: only a view
// that shows a live file (a table, a container's children) asks for it, through
// `metabrowser.watchFile`, or app.js's watchContainer. app.js hands it each snapshot's
// connection and each change.
//
// A watch is registered with the generation its reader holds, and the server answers the
// generation now, so a change between the reader's read and the registration reaches it.
// Each new connection, after a reconnect, a resync, a page restored from Back, or a server
// restart, registers every watch again with the generation it holds; a registration on a
// connection the server does not know waits for the next snapshot.
//
// While the page is hidden its watches are unregistered, so the server polls nothing for
// a tab nobody looks at, and registered again with the generations they hold when it is
// shown: a change while hidden reaches its reader once, from the registration's answer.

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
   *   sentOn: string | null,
   * }} Watch
   */

  /**
   * The page's watches over one way to reach the server.
   *
   * @param {{
   *   post: (body: Record<string, unknown>) => Promise<WatchAnswer>,
   *   connection?: string | null,
   *   hidden?: boolean,
   * }} deps
   */
  function createFileWatches(deps) {
    let connection = deps.connection ?? null;
    let hidden = deps.hidden ?? false;
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
     * Unregister *path* when a registration of it was sent on the connection now open,
     * whether or not its answer has come: `send` orders the unregistration after it.
     *
     * @param {string} path
     * @param {Watch} watch
     * @returns {Promise<unknown> | null} the unregistration, or null when none was sent
     */
    function unregister(path, watch) {
      const sentOn = watch.sentOn;
      watch.sentOn = null;
      if (sentOn === null || sentOn !== connection) {
        return null;
      }
      return send(path, { connection: sentOn, path, watch: false }).catch(() => {});
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
      // An answer still to come is for a registration this one replaces.
      watch.asked = ++asks;
      if (connection === null || hidden) {
        setState(watch, "waiting", hidden ? "hidden" : null);
        return;
      }
      const ask = watch.asked;
      /** @type {Record<string, unknown>} */
      const body = { connection, path };
      if (watch.generation !== undefined) {
        body.generation = watch.generation;
      }
      watch.sentOn = connection;
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
      // Not registered, so nothing to unregister.
      watch.sentOn = null;
      const code = typeof body?.code === "string" ? body.code : `status ${answer.status}`;
      // An id from a stream that ended, or a server that restarted: the next snapshot's.
      // Any other refusal is asked again when another watch is released.
      setState(watch, code === "unknown_connection" ? "waiting" : "refused", code);
    }

    /** Ask again for each refused watch: a watch released may have made room. */
    function retryRefused() {
      for (const [path, watch] of watches) {
        if (watch.state === "refused") {
          register(path, watch);
        }
      }
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
            sentOn: null,
          };
          watches.set(path, watch);
          register(path, watch);
        }
        const owned = watch;
        return () => {
          if (!owned.listeners.delete(listener) || owned.listeners.size > 0) {
            return;
          }
          if (watches.get(path) === owned) {
            watches.delete(path);
          }
          owned.asked = -1;
          // Once the server has let it go, a watch it refused for want of room may fit.
          void unregister(path, owned)?.then(retryRefused);
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
          // The connection a registration was sent on has ended with its stream.
          watch.sentOn = null;
          register(path, watch);
        }
      },

      /**
       * The page was hidden or shown: unregister every watch while it is hidden, and
       * register each again, with the generation it holds, when it is shown.
       *
       * @param {boolean} now
       */
      hidden(now) {
        if (now === hidden) {
          return;
        }
        hidden = now;
        for (const [path, watch] of watches) {
          if (hidden) {
            watch.asked = ++asks;
            void unregister(path, watch);
            setState(watch, "waiting", "hidden");
          } else {
            register(path, watch);
          }
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

  // How long a container gathers changes to its file before it reads its children again:
  // the table's LIVE_COALESCE_MS (builtin_plugins/table/table-view.js), for the same
  // reason. The first change starts the window and later ones join it, one read runs at a
  // time, and a change during a read reads once more after it, so a database written
  // continuously costs one children read a window, not one a `file.changed`.
  const CONTAINER_COALESCE_MS = 300;

  /**
   * @typedef {{
   *   timer: ReturnType<typeof setTimeout> | 0,
   *   running: boolean,
   *   again: boolean,
   *   release: () => void,
   * }} Follower
   */

  /**
   * A tree's containers following their files: each expanded container reads its
   * children again after its file changes, a collapsed one on its next expand, and a row
   * the tree drops releases its watch.
   *
   * @param {{
   *   watches: Pick<MetabrowserFileWatchRegistry, "watch">,
   *   setTimeout: (callback: () => void, delayMs: number) => ReturnType<typeof setTimeout>,
   *   clearTimeout: (handle: ReturnType<typeof setTimeout>) => void,
   *   observe: (onMutation: () => void) => () => void,
   * }} deps
   */
  function createContainerFollower(deps) {
    /** @type {Map<HTMLElement, Follower>} */
    const following = new Map();
    /** @type {(() => void) | null} */
    let unobserve = null;

    /** @param {HTMLElement} row */
    function release(row) {
      const follower = following.get(row);
      if (!follower) {
        return;
      }
      following.delete(row);
      if (follower.timer) {
        deps.clearTimeout(follower.timer);
      }
      follower.release();
      if (following.size === 0) {
        unobserve?.();
        unobserve = null;
      }
    }

    /** Release each row the tree no longer holds. */
    function sweep() {
      for (const row of [...following.keys()]) {
        if (!row.isConnected) {
          release(row);
        }
      }
    }

    return Object.freeze({
      /**
       * Follow *row*'s file; *load* reads its children into *children*.
       *
       * @param {HTMLElement} row
       * @param {HTMLElement} children
       * @param {(row: HTMLElement, children: HTMLElement) => Promise<unknown>} load
       */
      follow(row, children, load) {
        if (following.has(row)) {
          return;
        }
        /** @type {Follower} */
        const follower = { timer: 0, running: false, again: false, release: () => {} };
        const read = async () => {
          follower.timer = 0;
          if (!row.isConnected) {
            release(row);
            return;
          }
          if (row.getAttribute("aria-expanded") !== "true") {
            // Collapsed: read on the next expand.
            delete children.dataset.loaded;
            return;
          }
          follower.running = true;
          try {
            await load(row, children);
          } catch (error) {
            console.warn("metabrowser: a container's children could not be read again", error);
          } finally {
            follower.running = false;
          }
          if (follower.again && following.get(row) === follower) {
            follower.again = false;
            schedule();
          }
        };
        const schedule = () => {
          if (follower.running) {
            follower.again = true;
          } else if (!follower.timer) {
            follower.timer = deps.setTimeout(() => void read(), CONTAINER_COALESCE_MS);
          }
        };
        following.set(row, follower);
        unobserve ??= deps.observe(sweep);
        follower.release = deps.watches.watch(row.dataset.path || "", {
          onChange() {
            if (!row.isConnected) {
              release(row);
            } else {
              schedule();
            }
          },
        });
      },
      sweep,
      /** The rows followed, for a session to read. */
      describe() {
        return [...following].map(([row, follower]) =>
          Object.freeze({
            path: row.dataset.path || "",
            pending: Boolean(follower.timer),
            running: follower.running,
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

  const doc = typeof document === "undefined" ? null : document;
  /** @type {ReturnType<typeof createFileWatches> | null} */
  let shared = null;
  /** @type {ReturnType<typeof createContainerFollower> | null} */
  let containers = null;

  function sharedWatches() {
    if (!shared) {
      const made = createFileWatches({
        post,
        connection: window.metabrowserEventConnection ?? null,
        hidden: doc?.visibilityState === "hidden",
      });
      doc?.addEventListener("visibilitychange", () =>
        made.hidden(doc.visibilityState === "hidden"),
      );
      shared = made;
    }
    return shared;
  }

  window.MetabrowserFileWatches = Object.freeze({
    createFileWatches,
    createContainerFollower,
    /** The page's watches, made on first use over the stream's last connection. */
    shared: sharedWatches,
    /**
     * Follow a tree container's file (app.js's watchContainer).
     *
     * @param {HTMLElement} row
     * @param {HTMLElement} children
     * @param {(row: HTMLElement, children: HTMLElement) => Promise<unknown>} load
     */
    followContainer(row, children, load) {
      containers ??= createContainerFollower({
        watches: sharedWatches(),
        setTimeout: (callback, delayMs) => setTimeout(callback, delayMs),
        clearTimeout: (handle) => clearTimeout(handle),
        observe(onMutation) {
          const tree = doc?.getElementById("tree-content");
          if (!tree || typeof MutationObserver !== "function") {
            return () => {};
          }
          const observer = new MutationObserver(onMutation);
          observer.observe(tree, { childList: true, subtree: true });
          return () => observer.disconnect();
        },
      });
      containers.follow(row, children, load);
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
