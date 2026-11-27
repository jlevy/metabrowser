// Reusable inventory-event relevance and active-gated refresh lifecycle.

(() => {
  /** @param {unknown} changedPaths @param {string} scopePath */
  function pathsIntersectScope(changedPaths, scopePath) {
    if (!Array.isArray(changedPaths)) {
      return true;
    }
    return changedPaths.some(
      (changed) =>
        typeof changed === "string" &&
        (changed === scopePath ||
          changed === "" ||
          scopePath === "" ||
          changed.startsWith(`${scopePath}/`) ||
          scopePath.startsWith(`${changed}/`)),
    );
  }

  /**
   * @param {string} scopePath
   * @param {{fetch: (signal: AbortSignal | undefined) => Promise<unknown>, active?: () => boolean, debounceMs?: number, onError?: (error: unknown) => void}} options
   * @param {(value: unknown) => void} onUpdate
   */
  function createInventoryWatch(scopePath, options, onUpdate) {
    let disposed = false;
    let staleValue = false;
    /** @typedef {{done: Promise<void>, settle: () => void}} Cycle */
    /** @type {Cycle | null} */
    let pending = null;
    /** @type {Cycle | null} */
    let requested = null;
    /** @type {number | undefined} */
    let timer;
    // When the oldest change still waiting behind the debounce arrived. A
    // crawl emits inventory changes continuously, and a debounce that
    // restarts on each one would never fire until the stream paused, so a
    // folder's numbers would sit frozen for the whole scan and then jump.
    // Bounding the wait by one window makes the refresh coalesce bursts
    // while still landing at a steady cadence under a continuous stream.
    let oldestPendingAt = 0;
    /** @type {AbortController | undefined} */
    let controller;

    /** @returns {Cycle} */
    function cycle() {
      /** @type {() => void} */
      let settle = () => {};
      /** @type {Promise<void>} */
      const done = new Promise((resolve) => {
        settle = () => resolve();
      });
      return { done, settle };
    }

    function cancelTimer() {
      if (timer !== undefined) {
        clearTimeout(timer);
        timer = undefined;
      }
    }

    /** @param {Cycle} read */
    async function start(read) {
      // This fetch covers every change observed before it starts.
      cancelTimer();
      pending = read;
      staleValue = false;
      controller = typeof AbortController === "function" ? new AbortController() : undefined;
      try {
        const value = await options.fetch(controller?.signal);
        if (!disposed) {
          onUpdate(value);
        }
      } catch (error) {
        if (!disposed && !window.MetabrowserRequestErrors.isAbortError(error)) {
          options.onError?.(error);
        }
      } finally {
        pending = null;
        controller = undefined;
        read.settle();
        if (!disposed && requested !== null) {
          const next = requested;
          requested = null;
          void start(next);
        } else if (!disposed && staleValue && (!options.active || options.active())) {
          void start(cycle());
        }
      }
    }

    // An explicit reread waits for a fetch started after it was requested. Calls made
    // during the same in-flight read share its successor.
    function refresh() {
      if (disposed) {
        return Promise.resolve();
      }
      if (pending !== null) {
        cancelTimer();
        requested ??= cycle();
        return requested.done;
      }
      const next = cycle();
      void start(next);
      return next.done;
    }

    /** @param {Event} event */
    function handleChange(event) {
      const detail = event instanceof CustomEvent ? event.detail : undefined;
      if (disposed || !pathsIntersectScope(detail?.paths, scopePath)) {
        return;
      }
      const windowMs = options.debounceMs ?? 0;
      const now = Date.now();
      if (timer === undefined) {
        oldestPendingAt = now;
      } else {
        clearTimeout(timer);
      }
      const delay = Math.max(0, Math.min(windowMs, oldestPendingAt + windowMs - now));
      timer = window.setTimeout(() => {
        timer = undefined;
        if (disposed) {
          return;
        }
        if (pending !== null || (options.active && !options.active())) {
          staleValue = true;
          return;
        }
        void start(cycle());
      }, delay);
    }

    window.addEventListener("metabrowser:inventory-change", handleChange);
    void start(cycle());
    return Object.freeze({
      refresh,
      stale: () => staleValue,
      dispose() {
        if (disposed) {
          return;
        }
        disposed = true;
        window.removeEventListener("metabrowser:inventory-change", handleChange);
        cancelTimer();
        controller?.abort();
        pending?.settle();
        requested?.settle();
        requested = null;
      },
    });
  }

  window.MetabrowserInventoryScope = Object.freeze({ createInventoryWatch, pathsIntersectScope });
})();
