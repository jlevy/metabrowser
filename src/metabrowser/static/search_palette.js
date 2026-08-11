// Accessible, keyboard-first surface for browser-local file navigation.

(() => {
  /** Default DOM cap for the transient result list. */
  const DEFAULT_MAX_ROWS = 100;
  let paletteSerial = 0;

  // Keys that open the palette from anywhere in the app. `/` is the
  // browser-search convention; `t` matches github.com's go-to-file, so the
  // reflex carries over from the site these files usually came from. Both are
  // equal — neither is a modifier-prefixed alias of the other.
  const OPEN_KEYS = Object.freeze(["/", "t"]);

  // The hint row under the results. Keys render through the .kbd component;
  // the labels are ordinary chrome text, so the row reads as a sentence.
  const HINT_GROUPS = Object.freeze([
    { keys: ["↑", "↓"], label: "choose" },
    { keys: ["Enter"], label: "open" },
    { keys: ["Esc"], label: "close" },
  ]);

  /**
   * @typedef {object} PaletteResult
   * @property {string} description
   * @property {string} id
   * @property {"file"} kind
   * @property {string} label
   * @property {readonly Readonly<{start: number, end: number}>[]} matchRanges
   * @property {string} path
   */

  /**
   * @typedef {object} PaletteSearchState
   * @property {"idle" | "searching" | "complete"} phase
   * @property {Readonly<{query: string}> | null} request
   * @property {readonly PaletteResult[]} results
   * @property {string} statusMessage
   * @property {boolean} truncated
   */

  /**
   * @typedef {object} PaletteController
   * @property {() => void} cancel
   * @property {(request: {target: "file", match: "fuzzy", query: string}) =>
   *   Promise<PaletteSearchState | null>} search
   * @property {(listener: (state: PaletteSearchState) => void) => () => void} subscribe
   */

  /**
   * @typedef {object} OpenOutcome
   * @property {HTMLElement | null} [focusTarget]
   * @property {string} [message]
   * @property {"opened" | "not-found" | "error" | "cancelled"} status
   */

  /** @param {unknown} value @returns {value is HTMLElement} */
  function focusable(value) {
    return Boolean(value && typeof (/** @type {{focus?: unknown}} */ (value).focus) === "function");
  }

  /**
   * Build one "KEY KEY label" cluster for the hint row.
   *
   * Keys are written in natural case here; .kbd applies the caps treatment, so
   * the accessible name stays "Enter" rather than shouting at a screen reader.
   * @param {Document} hostDocument
   * @param {readonly string[]} keys
   * @param {string} label
   */
  function hintGroup(hostDocument, keys, label) {
    const group = hostDocument.createElement("span");
    group.className = "search-palette-hint-group";
    for (const key of keys) {
      const element = hostDocument.createElement("kbd");
      element.className = "kbd";
      element.textContent = key;
      group.append(element);
    }
    const text = hostDocument.createElement("span");
    text.textContent = label;
    group.append(text);
    return group;
  }

  /** @param {EventTarget | null} target */
  function isEditableTarget(target) {
    if (!target || typeof (/** @type {{tagName?: unknown}} */ (target).tagName) !== "string") {
      return false;
    }
    const element = /** @type {HTMLElement} */ (target);
    const tagName = element.tagName.toLowerCase();
    return (
      tagName === "input" ||
      tagName === "textarea" ||
      tagName === "select" ||
      element.isContentEditable
    );
  }

  /**
   * Append text and matching marks without interpreting result strings as markup.
   * @param {Document} hostDocument
   * @param {HTMLElement} container
   * @param {string} text
   * @param {readonly Readonly<{start: number, end: number}>[]} ranges
   * @param {number} pathOffset
   */
  function appendHighlightedText(hostDocument, container, text, ranges, pathOffset) {
    let cursor = 0;
    for (const range of ranges) {
      const start = Math.max(0, range.start - pathOffset);
      const end = Math.min(text.length, range.end - pathOffset);
      if (end <= 0 || start >= text.length || end <= start) {
        continue;
      }
      const boundedStart = Math.max(cursor, start);
      if (boundedStart > cursor) {
        container.append(hostDocument.createTextNode(text.slice(cursor, boundedStart)));
      }
      if (end > boundedStart) {
        const mark = hostDocument.createElement("mark");
        mark.textContent = text.slice(boundedStart, end);
        container.append(mark);
        cursor = end;
      }
    }
    if (cursor < text.length) {
      container.append(hostDocument.createTextNode(text.slice(cursor)));
    }
  }

  /**
   * @param {{
   *   controller: PaletteController,
   *   document?: Document,
   *   getCatalogSnapshot: () => {complete: boolean, observedCount: number},
   *   subscribeCatalog?: (listener: () => void) => () => void,
   *   getFileIcon?: (path: string) => {cls?: string, svg?: string},
   *   maxRows?: number,
   *   onNotFound?: (path: string) => void | Promise<void>,
   *   openFile: (path: string) => OpenOutcome | Promise<OpenOutcome>,
   * }} options
   */
  function create(options) {
    if (!options?.controller || typeof options.openFile !== "function") {
      throw new TypeError("Search palette requires a controller and open-file action");
    }
    const hostDocument = options.document || window.document;
    if (!hostDocument?.body) {
      throw new Error("Search palette requires a document body");
    }
    const maxRows =
      typeof options.maxRows === "number" && Number.isFinite(options.maxRows) && options.maxRows > 0
        ? Math.floor(options.maxRows)
        : DEFAULT_MAX_ROWS;
    paletteSerial += 1;
    const idPrefix = `metabrowser-quick-file-${paletteSerial}`;

    const overlay = hostDocument.createElement("div");
    overlay.className = "search-palette-overlay";
    overlay.hidden = true;

    const dialog = hostDocument.createElement("section");
    dialog.className = "search-palette-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", `${idPrefix}-title`);

    const title = hostDocument.createElement("h2");
    title.className = "search-palette-title";
    title.id = `${idPrefix}-title`;
    title.textContent = "Quick File";

    const input = hostDocument.createElement("input");
    input.className = "search-palette-input";
    input.id = `${idPrefix}-query`;
    input.setAttribute("type", "text");
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-label", "Find a known file");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", `${idPrefix}-results`);
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("autocomplete", "off");
    input.setAttribute("spellcheck", "false");
    input.setAttribute("placeholder", "Type a file name or path");

    const listbox = hostDocument.createElement("div");
    listbox.className = "search-palette-results";
    listbox.id = `${idPrefix}-results`;
    listbox.setAttribute("role", "listbox");
    listbox.setAttribute("aria-label", "Known file matches");

    const status = hostDocument.createElement("div");
    status.className = "search-palette-status";
    status.id = `${idPrefix}-status`;
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.setAttribute("aria-atomic", "true");

    const hint = hostDocument.createElement("div");
    hint.className = "search-palette-hint";
    for (const group of HINT_GROUPS) {
      hint.append(hintGroup(hostDocument, group.keys, group.label));
    }

    dialog.append(title, input, listbox, status, hint);
    overlay.append(dialog);
    hostDocument.body.append(overlay);

    /** @type {PaletteResult[]} */
    let results = [];
    /** @type {PaletteSearchState | null} */
    let searchState = null;
    /** @type {HTMLElement | null} */
    let previousFocus = null;
    /** @type {string | null} */
    let selectedResultId = null;
    let activeIndex = -1;
    let actionStatus = "";
    let opening = false;
    let disposed = false;
    let actionSerial = 0;
    /** @type {ReturnType<typeof setTimeout> | null} */
    let searchingStatusTimer = null;
    let announceSearching = false;
    // The query whose results are currently painted. Diverges from input.value
    // only while rows are held through a pending search.
    let renderedQuery = "";
    /** @type {ReturnType<typeof setTimeout> | null} */
    let catalogRefreshTimer = null;

    // Coverage arrives in bursts — one bulk payload, then a stream of deltas
    // while the walk finishes. Re-running per delta would thrash, so changes
    // coalesce into at most one re-run per window. Leading-edge coalescing
    // rather than a trailing debounce: on a large root the deltas may never
    // pause, and a trailing timer would keep resetting and never fire.
    const CATALOG_REFRESH_WINDOW_MS = 150;

    /**
     * The catalog moved underneath an open palette.
     *
     * A search reads one immutable snapshot, so results reflect coverage at
     * the moment the query ran. Without this a query typed while the bulk feed
     * was still arriving would keep its original, thinner result set even
     * after the catalog completed, and the user would have to edit the query
     * to see the rest.
     *
     * Re-running is safe rather than disruptive: the controller cancels the
     * superseded search, consumeState re-selects by result id so the keyboard
     * position survives, and because the query text is unchanged the rows
     * never go inert — the held-rows path repaints them without a flicker.
     */
    function onCatalogChanged() {
      if (disposed || overlay.hidden || opening || catalogRefreshTimer !== null) {
        return;
      }
      catalogRefreshTimer = setTimeout(() => {
        catalogRefreshTimer = null;
        if (disposed || overlay.hidden || opening) {
          return;
        }
        if (input.value.trim()) {
          runSearch(true);
        } else {
          // No query to re-run, but the idle line quotes the observed count,
          // which is exactly what just changed.
          renderStatus();
        }
      }, CATALOG_REFRESH_WINDOW_MS);
    }

    function clearCatalogRefresh() {
      if (catalogRefreshTimer !== null) {
        clearTimeout(catalogRefreshTimer);
        catalogRefreshTimer = null;
      }
    }

    /** Rendered rows describe the query in the box, so acting on them is safe. */
    function rowsMatchQuery() {
      return renderedQuery === input.value;
    }

    /**
     * Mirror row activation into the accessibility tree.
     *
     * Deliberately no visual change: held rows are normally stale for a few
     * milliseconds, and dimming them on every keystroke would reintroduce
     * exactly the flicker holding them was meant to remove. Assistive tech
     * still learns the rows are not actionable while they lag the query.
     */
    function syncRowActivation() {
      const stale = !rowsMatchQuery();
      for (const node of listbox.querySelectorAll('[role="option"]')) {
        node.setAttribute("aria-disabled", String(stale));
      }
    }

    // Below this threshold a search finishes before the eye registers it, so
    // announcing it would only flash a line of text that is immediately
    // replaced. Mirrors LOADING_INDICATOR_DELAY_MS in app.js.
    const SEARCHING_STATUS_DELAY_MS = 120;

    function scheduleSearchingStatus() {
      if (searchingStatusTimer !== null) {
        return;
      }
      searchingStatusTimer = setTimeout(() => {
        searchingStatusTimer = null;
        announceSearching = true;
        renderStatus();
      }, SEARCHING_STATUS_DELAY_MS);
    }

    function clearSearchingStatus() {
      if (searchingStatusTimer !== null) {
        clearTimeout(searchingStatusTimer);
        searchingStatusTimer = null;
      }
      announceSearching = false;
    }

    function renderStatus() {
      const query = input.value.trim();
      if (actionStatus) {
        status.textContent = actionStatus;
        return;
      }
      if (!query) {
        const snapshot = options.getCatalogSnapshot();
        const coverage = snapshot.complete ? "" : " Local coverage is incomplete.";
        const noun = snapshot.complete ? "files" : "observed files";
        status.textContent = `Type a filename to search ${snapshot.observedCount} ${noun}.${coverage}`;
        return;
      }
      if (!searchState || searchState.phase === "searching") {
        // Leave the previous line in place until the search is slow enough to
        // be worth reporting; scheduleSearchingStatus re-renders if it is.
        if (!announceSearching) {
          return;
        }
        const snapshot = options.getCatalogSnapshot();
        const noun = snapshot.complete ? "files" : "observed files";
        status.textContent = `Searching ${snapshot.observedCount} ${noun}…`;
        return;
      }
      const limitMessage = searchState.truncated ? " Results are limited." : "";
      status.textContent = `${searchState.statusMessage || "No known file matches."}${limitMessage}`;
    }

    /** @param {number} index */
    function optionId(index) {
      return `${idPrefix}-option-${index}`;
    }

    /** @param {boolean} scroll */
    function syncActiveOption(scroll) {
      const optionsNodes = listbox.querySelectorAll('[role="option"]');
      optionsNodes.forEach((optionNode, index) => {
        const active = index === activeIndex;
        optionNode.setAttribute("aria-selected", String(active));
        optionNode.classList.toggle("active", active);
        if (active && scroll) {
          optionNode.scrollIntoView({ block: "nearest" });
        }
      });
      const activeResult = results[activeIndex];
      if (activeResult) {
        selectedResultId = activeResult.id;
        input.setAttribute("aria-activedescendant", optionId(activeIndex));
      } else {
        selectedResultId = null;
        input.removeAttribute("aria-activedescendant");
      }
    }

    /** @param {number} index @param {boolean} [scroll] */
    function setActiveIndex(index, scroll = true) {
      if (results.length === 0) {
        activeIndex = -1;
      } else {
        activeIndex = Math.max(0, Math.min(results.length - 1, index));
      }
      syncActiveOption(scroll);
    }

    function renderResults() {
      listbox.replaceChildren();
      for (let index = 0; index < results.length; index += 1) {
        const result = results[index];
        const option = hostDocument.createElement("div");
        option.className = "search-palette-option";
        option.id = optionId(index);
        option.setAttribute("role", "option");
        option.setAttribute("aria-label", result.path);
        option.setAttribute("aria-selected", "false");

        const icon = hostDocument.createElement("span");
        icon.className = "search-palette-icon";
        icon.setAttribute("aria-hidden", "true");
        const iconData = options.getFileIcon?.(result.path);
        if (iconData?.cls && /^ft-[a-z0-9-]+$/u.test(iconData.cls)) {
          icon.classList.add(iconData.cls);
        }
        if (typeof iconData?.svg === "string") {
          icon.innerHTML = iconData.svg;
        }

        const text = hostDocument.createElement("span");
        text.className = "search-palette-option-text";
        const label = hostDocument.createElement("span");
        label.className = "search-palette-label";
        const labelOffset = result.description ? result.description.length + 1 : 0;
        appendHighlightedText(hostDocument, label, result.label, result.matchRanges, labelOffset);
        text.append(label);
        if (result.description) {
          const description = hostDocument.createElement("span");
          description.className = "search-palette-description";
          appendHighlightedText(
            hostDocument,
            description,
            result.description,
            result.matchRanges,
            0,
          );
          // Trailing separator so the line reads as the enclosing directory
          // rather than a path fragment. Appended after the highlighted text
          // instead of joining the provider's string, because match ranges are
          // offsets into the raw path and would all shift by one. Real text,
          // not generated content, so the path stays selectable.
          description.append(hostDocument.createTextNode("/"));
          text.append(description);
        }
        option.append(icon, text);
        option.addEventListener("pointermove", () => {
          setActiveIndex(index, false);
        });
        option.addEventListener("click", () => {
          void acceptIndex(index);
        });
        listbox.append(option);
      }
      syncActiveOption(false);
      syncRowActivation();
    }

    /** @param {PaletteSearchState} state */
    function consumeState(state) {
      if (overlay.hidden || state.request?.query !== input.value) {
        return;
      }
      searchState = state;
      // A search publishes "searching" once before any provider has returned,
      // so that first composition is always empty. Rendering it would blank the
      // list between keystrokes and refill it a few milliseconds later. Hold
      // the rows already on screen instead — the same reason selectFile leaves
      // the previous file in the preview during a fast fetch rather than
      // flashing a spinner. A completed search with no matches still clears,
      // because it is no longer pending.
      if (state.phase === "searching" && state.results.length === 0 && results.length > 0) {
        renderStatus();
        return;
      }
      clearSearchingStatus();
      const previousSelection = selectedResultId;
      results = state.results.slice(0, maxRows);
      renderedQuery = state.request?.query ?? "";
      activeIndex = previousSelection
        ? results.findIndex((result) => result.id === previousSelection)
        : results.length > 0
          ? 0
          : -1;
      if (activeIndex < 0 && results.length > 0) {
        activeIndex = 0;
      }
      renderResults();
      renderStatus();
    }

    /** @param {boolean} [preserveActionStatus] */
    function runSearch(preserveActionStatus = false) {
      const query = input.value;
      if (!preserveActionStatus) {
        actionStatus = "";
      }
      if (!query.trim()) {
        options.controller.cancel();
        clearSearchingStatus();
        searchState = null;
        results = [];
        renderedQuery = query;
        activeIndex = -1;
        selectedResultId = null;
        renderResults();
        renderStatus();
        return;
      }
      scheduleSearchingStatus();
      syncRowActivation();
      renderStatus();
      options.controller
        .search({ match: "fuzzy", query, target: "file" })
        .then((state) => {
          if (state) {
            consumeState(state);
          }
        })
        .catch((error) => {
          if (!overlay.hidden && input.value === query) {
            actionStatus = error instanceof Error ? error.message : "Search failed. Try again.";
            renderStatus();
          }
        });
    }

    /** @param {number} index */
    async function acceptIndex(index) {
      const result = results[index];
      // Held rows stay painted so typing does not flicker, but they describe
      // the query that produced them, not what is in the box now. Opening one
      // would navigate to a file that matched the previous query — a fast
      // typist entering B lands on a hit for A. Rows go live again the moment
      // their own completion arrives.
      if (!result || opening || !rowsMatchQuery()) {
        return;
      }
      actionSerial += 1;
      const actionId = actionSerial;
      opening = true;
      actionStatus = `Opening ${result.path}…`;
      renderStatus();
      /** @type {OpenOutcome} */
      let outcome;
      try {
        outcome = await options.openFile(result.path);
      } catch (error) {
        outcome = {
          message: error instanceof Error ? error.message : "Could not open file. Try again.",
          status: "error",
        };
      }
      if (disposed || actionId !== actionSerial || overlay.hidden) {
        return;
      }
      opening = false;
      if (outcome.status === "opened") {
        close(false);
        if (focusable(outcome.focusTarget)) {
          outcome.focusTarget.focus();
        }
        return;
      }
      if (outcome.status === "not-found") {
        actionStatus = outcome.message || "That file is no longer available.";
        try {
          await options.onNotFound?.(result.path);
        } catch (error) {
          actionStatus =
            error instanceof Error
              ? error.message
              : "Could not remove the stale result. Try again.";
          renderStatus();
          return;
        }
        if (disposed || actionId !== actionSerial || overlay.hidden) {
          return;
        }
        results = results.filter((candidate) => candidate.path !== result.path);
        activeIndex = Math.min(index, results.length - 1);
        selectedResultId = results[activeIndex]?.id || null;
        renderResults();
        runSearch(true);
        renderStatus();
        return;
      }
      if (outcome.status === "error") {
        actionStatus = outcome.message || "Could not open file. Try again.";
        renderStatus();
        return;
      }
      actionStatus = "";
      renderStatus();
    }

    function open() {
      if (disposed) {
        return;
      }
      if (!overlay.hidden) {
        input.focus();
        input.select();
        return;
      }
      previousFocus = focusable(hostDocument.activeElement)
        ? /** @type {HTMLElement} */ (hostDocument.activeElement)
        : null;
      overlay.hidden = false;
      input.setAttribute("aria-expanded", "true");
      input.value = "";
      searchState = null;
      results = [];
      activeIndex = -1;
      selectedResultId = null;
      actionStatus = "";
      renderResults();
      renderStatus();
      input.focus();
      input.select();
    }

    /** @param {boolean} [restoreFocus] */
    function close(restoreFocus = true) {
      if (overlay.hidden) {
        return;
      }
      options.controller.cancel();
      clearSearchingStatus();
      clearCatalogRefresh();
      actionSerial += 1;
      opening = false;
      overlay.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      const focusTarget = previousFocus;
      previousFocus = null;
      if (restoreFocus && focusable(focusTarget) && focusTarget.isConnected) {
        focusTarget.focus();
      }
    }

    /** @param {KeyboardEvent} event */
    function handleGlobalKeydown(event) {
      // Letter keys compare case-insensitively so a stuck caps lock still
      // opens the palette; the shift guard below is what keeps `?` and `T`
      // from triggering it, matching github.com.
      if (
        !OPEN_KEYS.includes(event.key.toLowerCase()) ||
        event.defaultPrevented ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.isComposing ||
        isEditableTarget(event.target)
      ) {
        return;
      }
      event.preventDefault();
      open();
    }

    /** @param {KeyboardEvent} event */
    function handleInputKeydown(event) {
      if (event.key === "Tab") {
        event.preventDefault();
        input.focus();
        return;
      }
      if (event.isComposing) {
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex(activeIndex < 0 ? 0 : activeIndex + 1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex(activeIndex < 0 ? results.length - 1 : activeIndex - 1);
      } else if (event.key === "Home") {
        event.preventDefault();
        setActiveIndex(0);
      } else if (event.key === "End") {
        event.preventDefault();
        setActiveIndex(results.length - 1);
      } else if (event.key === "Enter") {
        event.preventDefault();
        void acceptIndex(activeIndex);
      } else if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
    }

    /** @param {Event} event */
    function handleInput(event) {
      if (/** @type {{isComposing?: boolean}} */ (event).isComposing) {
        return;
      }
      runSearch();
    }

    /** @param {PointerEvent} event */
    function handleOverlayPointerdown(event) {
      if (event.target === overlay) {
        close();
      }
    }

    const unsubscribe = options.controller.subscribe(consumeState);
    const unsubscribeCatalog = options.subscribeCatalog?.(onCatalogChanged) || (() => {});
    hostDocument.addEventListener("keydown", handleGlobalKeydown);
    input.addEventListener("input", handleInput);
    input.addEventListener("keydown", handleInputKeydown);
    overlay.addEventListener("pointerdown", handleOverlayPointerdown);

    function dispose() {
      if (disposed) {
        return;
      }
      close(false);
      disposed = true;
      clearCatalogRefresh();
      unsubscribe();
      unsubscribeCatalog();
      hostDocument.removeEventListener("keydown", handleGlobalKeydown);
      input.removeEventListener("input", handleInput);
      input.removeEventListener("keydown", handleInputKeydown);
      overlay.removeEventListener("pointerdown", handleOverlayPointerdown);
      overlay.remove();
    }

    return Object.freeze({ close, dispose, element: overlay, isOpen: () => !overlay.hidden, open });
  }

  window.MetabrowserSearchPalette = Object.freeze({ create });
})();
