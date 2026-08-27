// Active-view subscriptions and dynamic print metadata.

(() => {
  /** @type {WeakMap<HTMLElement, {active: boolean, listeners: Set<(active: boolean) => void>}>} */
  const records = new WeakMap();

  /** @param {HTMLElement} container */
  function recordFor(container) {
    let record = records.get(container);
    if (!record) {
      record = { active: false, listeners: new Set() };
      records.set(container, record);
    }
    return record;
  }

  /** @param {HTMLElement} container @param {boolean} active */
  function setActive(container, active) {
    const record = recordFor(container);
    if (record.active === active) {
      return;
    }
    record.active = active;
    container.dataset.activeView = active ? "true" : "false";
    for (const listener of record.listeners) {
      listener(active);
    }
  }

  /** @param {HTMLElement} container */
  function isActive(container) {
    return recordFor(container).active;
  }

  /** @param {HTMLElement} container @param {(active: boolean) => void} listener */
  function subscribeActive(container, listener) {
    const record = recordFor(container);
    record.listeners.add(listener);
    listener(record.active);
    let subscribed = true;
    return () => {
      if (subscribed) {
        subscribed = false;
        record.listeners.delete(listener);
      }
    };
  }

  /** @param {HTMLElement} container @param {{printable: boolean, profile?: string, runtime?: string}} state */
  function setPrintState(container, state) {
    if (!state || typeof state.printable !== "boolean") {
      throw new TypeError("print state requires a boolean printable value");
    }
    const profile = state.profile ?? "plain";
    if (
      typeof profile !== "string" ||
      (state.runtime !== undefined && typeof state.runtime !== "string")
    ) {
      throw new TypeError("print profile and runtime must be strings");
    }
    container.dataset.printable = state.printable ? "true" : "false";
    container.dataset.printProfile = profile;
    if (state.runtime) {
      container.dataset.renderRuntime = state.runtime;
    } else {
      delete container.dataset.renderRuntime;
    }
    if (isActive(container)) {
      container.dispatchEvent(
        new CustomEvent("metabrowser:view-print-state", {
          bubbles: true,
          detail: Object.freeze({ ...state, profile }),
        }),
      );
    }
  }

  window.MetabrowserViewState = Object.freeze({
    isActive,
    setActive,
    setPrintState,
    subscribeActive,
  });
})();
