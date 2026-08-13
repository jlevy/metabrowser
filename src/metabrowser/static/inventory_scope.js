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
    let pending = false;
    let staleValue = false;
    /** @type {number | undefined} */
    let timer;
    /** @type {AbortController | undefined} */
    let controller;

    async function refresh() {
      if (disposed || pending) {
        staleValue = !disposed;
        return;
      }
      pending = true;
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
        pending = false;
        controller = undefined;
        if (staleValue && !disposed && (!options.active || options.active())) {
          void refresh();
        }
      }
    }

    /** @param {Event} event */
    function handleChange(event) {
      const detail = event instanceof CustomEvent ? event.detail : undefined;
      if (disposed || !pathsIntersectScope(detail?.paths, scopePath)) {
        return;
      }
      if (timer !== undefined) {
        clearTimeout(timer);
      }
      timer = window.setTimeout(() => {
        timer = undefined;
        if (options.active && !options.active()) {
          staleValue = true;
          return;
        }
        void refresh();
      }, options.debounceMs ?? 0);
    }

    window.addEventListener("metabrowser:inventory-change", handleChange);
    void refresh();
    return Object.freeze({
      refresh,
      stale: () => staleValue,
      dispose() {
        if (disposed) {
          return;
        }
        disposed = true;
        window.removeEventListener("metabrowser:inventory-change", handleChange);
        if (timer !== undefined) {
          clearTimeout(timer);
        }
        controller?.abort();
      },
    });
  }

  window.MetabrowserInventoryScope = Object.freeze({ createInventoryWatch, pathsIntersectScope });
})();
