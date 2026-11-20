// A Git revision's page while its files' ages are being read.
//
// The server reads each file's last-commit time in the background (docs/project/
// architecture/arch-git.md, "File Ages") and never makes a page wait for it: a tree, a
// grouped tree, or a Recent list asked for before the answer lands carries an `ages` state
// of `dating`, with every file undated. This module watches for that state. While a
// response says `dating` it asks /api/index/progress, which carries the same state, every
// `GIT_AGES_POLL_MS`; when the answer lands, or the read fails, it asks the shell to draw
// again, once, so the rows that had no age get one without the reader doing anything. A
// response that says anything else stops the watch, so a page whose Git has no file ages
// (no `ages` key at all) never asks.
//
// The controller is the whole decision and takes its fetch, timers, and landing callback
// as dependencies, so tests/dom/revision-ages-session.js runs it from the command line;
// `mount` is the browser glue that supplies the real ones.

/** @param {Window} global */
((global) => {
  const PROGRESS_ROUTE = "/api/index/progress";
  // The server ends a read at GIT_AGES_TIMEOUT_S (settings.py) and says so, so a watch that
  // has gone on for much longer than that has lost the answer, and stops rather than ask
  // for as long as the page is open.
  const GIVE_UP_AFTER_MS = 120_000;

  /**
   * @param {{
   *   fetchState: () => Promise<{state: string} | null>,
   *   landed: (state: {state: string}) => void,
   *   setTimer: (run: () => void, ms: number) => unknown,
   *   clearTimer: (timer: unknown) => void,
   *   now: () => number,
   *   pollMs: number,
   * }} deps
   */
  function createController(deps) {
    /** @type {unknown} */
    let timer = null;
    let watching = false;
    let startedAt = 0;
    let generation = 0;

    function stop() {
      generation += 1;
      watching = false;
      if (timer !== null) {
        deps.clearTimer(timer);
        timer = null;
      }
    }

    function schedule() {
      timer = deps.setTimer(() => {
        timer = null;
        void poll();
      }, deps.pollMs);
    }

    async function poll() {
      const mine = generation;
      /** @type {{state: string} | null} */
      let state = null;
      try {
        state = await deps.fetchState();
      } catch {
        state = null;
      }
      if (mine !== generation) {
        return;
      }
      if (state !== null && state.state === "dating") {
        if (deps.now() - startedAt >= GIVE_UP_AFTER_MS) {
          stop();
          return;
        }
        schedule();
        return;
      }
      stop();
      if (state !== null) {
        deps.landed(state);
      }
    }

    /**
     * Look at the `ages` of a response. `dating` starts a watch, unless one is running; any
     * other state ends it, and a response with no `ages` is not about file ages.
     *
     * @param {{state?: string} | null | undefined} ages
     */
    function observe(ages) {
      if (ages === null || ages === undefined || typeof ages.state !== "string") {
        return;
      }
      if (ages.state !== "dating") {
        stop();
        return;
      }
      if (watching) {
        return;
      }
      watching = true;
      startedAt = deps.now();
      schedule();
    }

    return Object.freeze({
      observe,
      stop,
      isWatching: () => watching,
    });
  }

  /**
   * The controller on the page: real fetch and timers, and the shell's own redraw.
   *
   * @param {{ reload: (state: {state: string}) => void, pollMs?: number }} options
   */
  function mount(options) {
    return createController({
      fetchState: async () => {
        const response = await global.fetch(PROGRESS_ROUTE, { cache: "no-store" });
        if (!response.ok) {
          return null;
        }
        const body = await response.json();
        return body && typeof body.ages === "object" && body.ages ? body.ages : null;
      },
      landed: options.reload,
      setTimer: (run, ms) => global.setTimeout(run, ms),
      clearTimer: (timer) => global.clearTimeout(/** @type {number} */ (timer)),
      now: () => Date.now(),
      pollMs: options.pollMs ?? global.METABROWSER_SETTINGS?.GIT_AGES_POLL_MS ?? 500,
    });
  }

  /**  {ReturnType<typeof createController> | null} */
  let shared = null;

  /**
   * The page's one watch: the shell hands it every `ages` a response carries, and hears of
   * the answer as a `metabrowser:file-ages-landed` event on the window.
   *
   * @param {{state?: string} | null | undefined} ages
   */
  function observe(ages) {
    shared ??= mount({
      reload: (state) =>
        global.dispatchEvent(
          new global.CustomEvent("metabrowser:file-ages-landed", { detail: state }),
        ),
    });
    shared.observe(ages);
  }

  global.MetabrowserRevisionAges = Object.freeze({ createController, mount, observe });
})(window);
