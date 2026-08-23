// Multiplexed live envelope store for path-scoped resources.

(() => {
  /**
   * @template T
   * @param {{fetchEnvelope: (path: string, signal: AbortSignal | undefined) => Promise<T>, pathsIntersect: (paths: unknown, path: string) => boolean, debounceMs: number}} options
   */
  function createResourceContextStore(options) {
    /** @type {Map<string, {value?: T, listeners: Set<(value: T) => void>, timer?: number, controller?: AbortController, generation: number}>} */
    const records = new Map();
    let disposed = false;

    /** @param {string} path */
    function getRecord(path) {
      let record = records.get(path);
      if (!record) {
        record = { listeners: new Set(), generation: 0 };
        records.set(path, record);
      }
      return record;
    }

    /** @param {string} path @param {T} value */
    function seed(path, value) {
      if (disposed) {
        return;
      }
      const record = getRecord(path);
      record.value = value;
      for (const listener of record.listeners) {
        listener(value);
      }
    }

    /** @param {string} path */
    async function refresh(path) {
      if (disposed) {
        return;
      }
      const record = getRecord(path);
      record.controller?.abort();
      record.controller = typeof AbortController === "function" ? new AbortController() : undefined;
      const generation = ++record.generation;
      try {
        const value = await options.fetchEnvelope(path, record.controller?.signal);
        if (!disposed && records.get(path) === record && generation === record.generation) {
          seed(path, value);
        }
      } catch (error) {
        if (!window.MetabrowserRequestErrors.isAbortError(error)) {
          console.warn("resource context refresh failed", error);
        }
      }
    }

    /** @param {Event} event */
    function handleChange(event) {
      const detail = event instanceof CustomEvent ? event.detail : undefined;
      for (const [path, record] of records) {
        if (!record.listeners.size || !options.pathsIntersect(detail?.paths, path)) {
          continue;
        }
        if (record.timer !== undefined) {
          clearTimeout(record.timer);
        }
        record.timer = window.setTimeout(() => {
          record.timer = undefined;
          void refresh(path);
        }, options.debounceMs);
      }
    }

    const canListen = typeof window.addEventListener === "function";
    if (canListen) {
      window.addEventListener("metabrowser:inventory-change", handleChange);
    }
    return Object.freeze({
      seed,
      /** @param {string} path @param {(value: T) => void} listener */
      subscribe(path, listener) {
        const record = getRecord(path);
        record.listeners.add(listener);
        if (record.value !== undefined) {
          listener(record.value);
        }
        let subscribed = true;
        return () => {
          if (!subscribed) {
            return;
          }
          subscribed = false;
          record.listeners.delete(listener);
          if (!record.listeners.size) {
            if (record.timer !== undefined) {
              clearTimeout(record.timer);
            }
            record.controller?.abort();
            records.delete(path);
          }
        };
      },
      refresh,
      dispose() {
        if (disposed) {
          return;
        }
        disposed = true;
        if (canListen) {
          window.removeEventListener("metabrowser:inventory-change", handleChange);
        }
        for (const record of records.values()) {
          if (record.timer !== undefined) {
            clearTimeout(record.timer);
          }
          record.controller?.abort();
        }
        records.clear();
      },
    });
  }

  window.MetabrowserResourceContext = Object.freeze({ createResourceContextStore });
})();
