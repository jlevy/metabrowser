// One delayed diagnostic per episode where rendered folder tallies remain
// unresolved. The application supplies DOM inspection and transport details;
// this module owns only the timer lifecycle so repeated renders cannot create
// a warning storm.
(function registerPendingTallyDiagnostics(root) {
  /**
   * @typedef {object} PendingTallyContext
   * @property {number} elapsedMs
   * @property {number} episode
   */

  /**
   * @typedef {object} PendingTallyWatchdogOptions
   * @property {() => boolean} hasPending
   * @property {(context: PendingTallyContext) => unknown} collect
   * @property {(payload: unknown) => unknown | Promise<unknown>} report
   * @property {number} delayMs
   * @property {(callback: () => void, delayMs: number) => number} [schedule]
   * @property {(handle: number) => void} [cancel]
   * @property {() => number} [now]
   * @property {(error: unknown) => void} [onError]
   */

  /**
   * @param {PendingTallyWatchdogOptions} options
   * @returns {Readonly<{dispose: () => void, reconcile: () => void}>}
   */
  function create(options) {
    const schedule =
      options.schedule || ((callback, delayMs) => window.setTimeout(callback, delayMs));
    const cancel = options.cancel || ((handle) => window.clearTimeout(handle));
    const now = options.now || (() => Date.now());
    const onError = options.onError || (() => {});

    /** @type {number | null} */
    let timer = null;
    let pendingSince = 0;
    let episode = 0;
    let reported = false;
    let disposed = false;

    function resetEpisode() {
      if (timer !== null) {
        cancel(timer);
        timer = null;
      }
      pendingSince = 0;
      reported = false;
    }

    function reportIfStillPending() {
      timer = null;
      if (disposed || !options.hasPending()) {
        resetEpisode();
        return;
      }
      reported = true;
      let payload;
      try {
        payload = options.collect({
          elapsedMs: Math.max(0, now() - pendingSince),
          episode,
        });
      } catch (error) {
        onError(error);
        return;
      }
      Promise.resolve()
        .then(() => options.report(payload))
        .catch(onError);
    }

    function reconcile() {
      if (disposed) {
        return;
      }
      if (!options.hasPending()) {
        resetEpisode();
        return;
      }
      if (timer !== null || reported) {
        return;
      }
      pendingSince = now();
      episode += 1;
      timer = schedule(reportIfStillPending, options.delayMs);
    }

    function dispose() {
      disposed = true;
      resetEpisode();
    }

    return Object.freeze({ dispose, reconcile });
  }

  root.MetabrowserPendingTallyDiagnostics = Object.freeze({ create });
})(window);
