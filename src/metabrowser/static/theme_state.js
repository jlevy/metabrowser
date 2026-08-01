// Shared resolved-theme notification boundary for the shell and canvas renderers.

/** @param {Window} global */
((global) => {
  /** @typedef {{mode: "dark" | "light" | "system", resolved: "dark" | "light"}} ThemeChange */
  const themeChangedEvent = "metabrowser:theme-changed";

  /**
   * Subscribe to resolved-theme changes and return an explicit disposer.
   *
   * @param {(detail: ThemeChange) => void} listener
   * @returns {() => void}
   */
  function subscribe(listener) {
    /** @param {Event} event */
    const handleThemeChanged = (event) => {
      if (event instanceof CustomEvent) {
        listener(/** @type {ThemeChange} */ (event.detail));
      }
    };
    global.addEventListener(themeChangedEvent, handleThemeChanged);
    return () => global.removeEventListener(themeChangedEvent, handleThemeChanged);
  }

  /** @param {ThemeChange} detail */
  function notifyChanged(detail) {
    global.dispatchEvent(new CustomEvent(themeChangedEvent, { detail }));
  }

  global.MetabrowserTheme = {
    notifyChanged,
    subscribe,
  };
})(window);
