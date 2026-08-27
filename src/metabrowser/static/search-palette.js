// Accessible, keyboard-first surface for browser-local file navigation.

(() => {
  /** Default DOM cap for the transient result list. */
  const DEFAULT_MAX_ROWS = 100;
  let paletteSerial = 0;

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
   * @property {readonly string[]} errors
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

  /** @param {number} count @param {string} [modifier] */
  function fileCount(count, modifier = "") {
    const noun = count === 1 ? "file" : "files";
    return `${count.toLocaleString()}${modifier ? ` ${modifier}` : ""} ${noun}`;
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
   *   overlay: Window["MetabrowserOverlay"],
   *   resolveFocusFallback?: (previous: HTMLElement | null) => HTMLElement | null,
   *   shortcuts: ReturnType<Window["MetabrowserKeyboardShortcuts"]["create"]>,
   * }} options
   */
  function create(options) {
    if (
      !options?.controller ||
      typeof options.openFile !== "function" ||
      !options.shortcuts ||
      !options.overlay
    ) {
      throw new TypeError(
        "Search palette requires a controller, open-file action, shortcuts, and overlays",
      );
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

    /** @type {ReturnType<Window["MetabrowserOverlay"]["createModal"]> | null} */
    let modal = null;
    const unregisterClose = options.shortcuts.register({
      allowInEditable: true,
      bindings: [{ key: "Escape" }],
      copy: {
        action: "Close Quick File",
        description: "Close Quick File and restore focus to the previous control.",
        hint: "Close",
      },
      group: "quick-file",
      handler: () => {
        if (!modal?.isOpen()) {
          return false;
        }
        close();
        return true;
      },
      id: "quick-file.close",
      order: 60,
      scope: "quick-file",
      surfaces: { help: "always", "quick-file": "active" },
    });
    modal = options.overlay.createModal({
      className: "search-palette-dialog",
      closeCommandId: "quick-file.close",
      document: hostDocument,
      initialFocus: input,
      onClose: resetAfterClose,
      onOpen: resetForOpen,
      resolveFocusFallback: options.resolveFocusFallback,
      scope: "quick-file",
      shortcuts: options.shortcuts,
      title: "Quick File",
    });
    const overlay = modal.element;
    overlay.classList.add("search-palette-overlay");
    modal.body.classList.add("search-palette-body");
    modal.body.append(input, listbox, status, hint);

    /** @type {PaletteResult[]} */
    let results = [];
    /** @type {PaletteSearchState | null} */
    let searchState = null;
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
        const scope = fileCount(snapshot.observedCount, snapshot.complete ? "" : "indexed");
        status.textContent = snapshot.complete
          ? `Search includes ${scope}.`
          : `Search includes ${scope}. Scanning continues.`;
        return;
      }
      if (!searchState || searchState.phase === "searching") {
        // Leave the previous line in place until the search is slow enough to
        // be worth reporting; scheduleSearchingStatus re-renders if it is.
        if (!announceSearching) {
          return;
        }
        const snapshot = options.getCatalogSnapshot();
        const scope = fileCount(snapshot.observedCount, snapshot.complete ? "" : "indexed");
        status.textContent = `Searching ${scope}…`;
        return;
      }
      const limitMessage = searchState.truncated ? " Showing the top matches." : "";
      if (searchState.errors?.length) {
        status.textContent = `Could not complete the search. Try again.${limitMessage}`;
        return;
      }
      status.textContent = `${searchState.statusMessage || "No matches."}${limitMessage}`;
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

    /**
     * Step the active result, wrapping at both ends.
     *
     * The list is bounded by maxRows and has no Home or End command — those
     * keys stay with the query box's caret — so wrapping is what keeps the far
     * end of the list one keystroke away.
     *
     * @param {number} delta
     */
    function moveActiveIndex(delta) {
      if (results.length === 0) {
        setActiveIndex(-1);
        return;
      }
      if (activeIndex < 0) {
        setActiveIndex(delta > 0 ? 0 : results.length - 1);
        return;
      }
      const next = (activeIndex + delta) % results.length;
      setActiveIndex(next < 0 ? next + results.length : next);
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
            console.warn("Quick File search failed", error);
            actionStatus = "Could not complete the search. Try again.";
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
        console.warn("Quick File open failed", error);
        outcome = {
          message: "Could not open this file. Try again.",
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
          console.warn("Quick File stale-result cleanup failed", error);
          actionStatus = "Could not refresh search results. Try again.";
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
        actionStatus = outcome.message || "Could not open this file. Try again.";
        renderStatus();
        return;
      }
      actionStatus = "";
      renderStatus();
    }

    function resetForOpen() {
      input.setAttribute("aria-expanded", "true");
      input.value = "";
      searchState = null;
      results = [];
      activeIndex = -1;
      selectedResultId = null;
      actionStatus = "";
      renderResults();
      renderStatus();
    }

    function resetAfterClose() {
      options.controller.cancel();
      clearSearchingStatus();
      clearCatalogRefresh();
      actionSerial += 1;
      opening = false;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
    }

    /** @param {HTMLElement | null} [trigger] */
    function open(trigger = null) {
      if (disposed) {
        return;
      }
      modal?.open(trigger);
      input.select();
    }

    /** @param {boolean} [restoreFocus] */
    function close(restoreFocus = true) {
      modal?.close({ restoreFocus });
    }

    /** @param {Event} event */
    function handleInput(event) {
      if (/** @type {{isComposing?: boolean}} */ (event).isComposing) {
        return;
      }
      runSearch();
    }

    function renderShortcutHints() {
      const groups = options.shortcuts.snapshot("quick-file");
      const rendered = [];
      for (const group of groups) {
        for (const command of group.commands) {
          const item = hostDocument.createElement("span");
          item.className = "search-palette-hint-group";
          const binding = hostDocument.createElement("span");
          binding.className = "search-palette-hint-binding";
          options.shortcuts.appendBinding(binding, command.bindings);
          const label = hostDocument.createElement("span");
          label.textContent = command.copy.hint;
          item.append(binding, label);
          rendered.push(item);
        }
      }
      hint.replaceChildren(...rendered);
    }

    function registerCommands() {
      return [
        options.shortcuts.register({
          bindings: [{ key: "t" }, { key: "/" }],
          control: modal?.control,
          copy: {
            action: "Quick File",
            description: "Find and open a file from the current folder.",
            hint: "Quick File",
          },
          group: "anywhere",
          handler: (context) => {
            const trigger = context.trigger;
            open(
              trigger && typeof trigger === "object" ? /** @type {HTMLElement} */ (trigger) : null,
            );
            return true;
          },
          id: "quick-file.open",
          order: 20,
          scope: "global",
          surfaces: { help: "always", nav: "always" },
        }),
        options.shortcuts.register({
          allowInEditable: true,
          bindings: [{ key: "ArrowUp" }],
          copy: {
            action: "Previous result",
            description: "Move to the previous Quick File result, wrapping at the top.",
            hint: "Move",
          },
          group: "quick-file",
          handler: () => {
            moveActiveIndex(-1);
            return true;
          },
          id: "quick-file.previous",
          order: 10,
          repeat: true,
          scope: "quick-file",
          surfaces: { help: "always", "quick-file": "active" },
        }),
        options.shortcuts.register({
          allowInEditable: true,
          bindings: [{ key: "ArrowDown" }],
          copy: {
            action: "Next result",
            description: "Move to the next Quick File result, wrapping at the bottom.",
            hint: "Move",
          },
          group: "quick-file",
          handler: () => {
            moveActiveIndex(1);
            return true;
          },
          id: "quick-file.next",
          order: 20,
          repeat: true,
          scope: "quick-file",
          surfaces: { help: "always", "quick-file": "active" },
        }),
        // Home and End deliberately have no command here. The query box is an
        // editable combobox, so those keys belong to its caret: claiming them
        // would take line-start and line-end away from the field, which the
        // design system reserves for native editing behavior. The result list
        // is bounded at maxRows and the arrow commands wrap, so the ends of the
        // list stay one keystroke away.
        options.shortcuts.register({
          allowInEditable: true,
          bindings: [{ key: "Enter" }],
          copy: {
            action: "Open result",
            description: "Open the active Quick File result.",
            hint: "Open",
          },
          group: "quick-file",
          handler: () => {
            if (!results[activeIndex] || opening || !rowsMatchQuery()) {
              return false;
            }
            void acceptIndex(activeIndex);
            return true;
          },
          id: "quick-file.activate",
          order: 50,
          scope: "quick-file",
          surfaces: { help: "always", "quick-file": "active" },
        }),
      ];
    }

    const unsubscribe = options.controller.subscribe(consumeState);
    const unsubscribeCatalog = options.subscribeCatalog?.(onCatalogChanged) || (() => {});
    const unregisterCommands = registerCommands();
    const unsubscribeHints = options.shortcuts.subscribe(renderShortcutHints);
    renderShortcutHints();
    // Tab belongs to the shared modal focus trap, which cycles the query box
    // and the dialog's Close control in both directions. A palette-local Tab
    // handler would preventDefault before the trap ran and strand Shift+Tab.
    input.addEventListener("input", handleInput);

    function dispose() {
      if (disposed) {
        return;
      }
      close(false);
      disposed = true;
      clearCatalogRefresh();
      unsubscribe();
      unsubscribeCatalog();
      unsubscribeHints();
      input.removeEventListener("input", handleInput);
      for (const unregister of unregisterCommands) {
        unregister();
      }
      modal?.dispose();
      modal = null;
      unregisterClose();
    }

    return Object.freeze({ close, dispose, element: overlay, isOpen: () => !overlay.hidden, open });
  }

  window.MetabrowserSearchPalette = Object.freeze({ create });
})();
