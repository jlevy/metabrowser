// Accessible, keyboard-first surface for navigating to Quick Search results.

(() => {
  /** Default DOM cap for the transient result list. */
  const DEFAULT_MAX_ROWS = 100;
  // The registry events that change what the hint row shows, the rule the
  // navigation strip in keyboard-help.js follows: a registration adds or drops
  // a command, and a scope change shows or hides the active ones.
  const HINT_EVENT_KINDS = new Set(["registration", "scope"]);
  let paletteSerial = 0;

  /** @typedef {ReturnType<ReturnType<Window["MetabrowserSearch"]["createController"]>["state"]>["results"][number]} PaletteResult */

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
   * @property {(request: {target: "all" | "file", match: "fuzzy", query: string}) =>
   *   Promise<PaletteSearchState | null>} search
   * @property {(listener: (state: PaletteSearchState) => void) => () => void} subscribe
   */

  /**
   * A failed open always carries the message to show, so the palette never
   * classifies an outcome a second time.
   *
   * @typedef {{focusTarget?: HTMLElement | null, message?: string, status: "opened" | "not-found" | "cancelled"}
   *   | {focusTarget?: HTMLElement | null, message: string, status: "error" | "unreachable"}} OpenOutcome
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
   *   describeOpenFailure: (error: unknown) => {message: string, status: "error" | "unreachable"},
   *   document?: Document,
   *   getCatalogSnapshot: () => {complete: boolean, observedCount: number, truncated: boolean},
   *   subscribeCatalog?: (listener: () => void) => () => void,
   *   getFileIcon?: (path: string) => {cls?: string, svg?: string},
   *   maxRows?: number,
   *   onNotFound?: (path: string) => void | Promise<void>,
   *   onOpen?: () => void,
   *   openFile: (path: string) => OpenOutcome | Promise<OpenOutcome>,
   *   openPull?: (number: number) => OpenOutcome | Promise<OpenOutcome>,
   *   overlay: Window["MetabrowserOverlay"],
   *   resolveFocusFallback?: (previous: HTMLElement | null) => HTMLElement | null,
   *   shortcuts: ReturnType<Window["MetabrowserKeyboardShortcuts"]["create"]>,
   * }} options
   */
  function create(options) {
    if (
      !options?.controller ||
      typeof options.openFile !== "function" ||
      typeof options.describeOpenFailure !== "function" ||
      !options.shortcuts ||
      !options.overlay
    ) {
      throw new TypeError(
        "Search palette requires a controller, open-file action, failure description, shortcuts, and overlays",
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
    const includesPulls = typeof options.openPull === "function";
    paletteSerial += 1;
    const idPrefix = `metabrowser-quick-search-${paletteSerial}`;

    const input = hostDocument.createElement("input");
    input.className = "search-palette-input";
    input.id = `${idPrefix}-query`;
    input.setAttribute("type", "text");
    input.setAttribute("role", "combobox");
    input.setAttribute(
      "aria-label",
      includesPulls ? "Find a file or pull request" : "Find a known file",
    );
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", `${idPrefix}-results`);
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("autocomplete", "off");
    input.setAttribute("spellcheck", "false");
    input.setAttribute(
      "placeholder",
      includesPulls ? "Search files or PRs. Type # for recent PRs." : "Type a file name or path",
    );

    const listbox = hostDocument.createElement("div");
    listbox.className = "search-palette-results";
    listbox.id = `${idPrefix}-results`;
    listbox.setAttribute("role", "listbox");
    listbox.setAttribute("aria-label", includesPulls ? "Search matches" : "Known file matches");

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
        action: "Close Quick Search",
        description: "Close Quick Search and restore focus to the previous control.",
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
      title: "Quick Search",
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
    // The connection message an unreachable open left on screen, so a later
    // reconnect retires that message and nothing else.
    let unreachableStatus = "";
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
    let catalogRefreshPending = false;

    // File coverage can change in bursts. Coalesce them, and let a mixed
    // search finish its PR reads before replacing its file snapshot.
    const CATALOG_REFRESH_WINDOW_MS = 150;

    function searchHoldsCatalogRefresh() {
      return includesPulls && searchState?.phase === "searching";
    }

    function scheduleCatalogRefresh() {
      if (!catalogRefreshPending || catalogRefreshTimer !== null || searchHoldsCatalogRefresh()) {
        return;
      }
      catalogRefreshTimer = setTimeout(() => {
        catalogRefreshTimer = null;
        if (disposed || overlay.hidden || opening) {
          catalogRefreshPending = false;
          return;
        }
        if (searchHoldsCatalogRefresh()) {
          return;
        }
        catalogRefreshPending = false;
        if (input.value.trim()) {
          runSearch(true);
        } else {
          renderStatus();
        }
      }, CATALOG_REFRESH_WINDOW_MS);
    }

    function onCatalogChanged() {
      if (
        disposed ||
        overlay.hidden ||
        opening ||
        (includesPulls && window.MetabrowserSearch.isExplicitPullQuery(input.value))
      ) {
        return;
      }
      catalogRefreshPending = true;
      scheduleCatalogRefresh();
    }

    function clearCatalogRefresh() {
      catalogRefreshPending = false;
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
        // A walk stopped at the file cap is final even though it is not complete.
        const coverage = snapshot.complete
          ? ""
          : snapshot.truncated
            ? " Indexing stopped at the file limit."
            : " Scanning continues.";
        status.textContent = includesPulls
          ? `Search includes ${scope} and cached pull requests.${coverage}`
          : `Search includes ${scope}.${coverage}`;
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
        const spinner = hostDocument.createElement("span");
        spinner.className = "spinner spinner-sm";
        spinner.setAttribute("aria-hidden", "true");
        const message = includesPulls ? "Searching…" : `Searching ${scope}…`;
        status.replaceChildren(spinner, hostDocument.createTextNode(message));
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

    /** @param {HTMLElement} option @param {Extract<PaletteResult, {kind: "file"}>} result */
    function appendFileResult(option, result) {
      option.setAttribute(
        "aria-label",
        [result.description, result.label].filter(Boolean).join("/"),
      );
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
        appendHighlightedText(hostDocument, description, result.description, result.matchRanges, 0);
        // Add the parent-path separator after highlighting so path offsets and
        // text selection both stay accurate.
        description.append(hostDocument.createTextNode("/"));
        text.append(description);
      }
      option.append(icon, text);
    }

    /** @param {HTMLElement} option @param {Extract<PaletteResult, {kind: "pull"}>} result */
    function appendPullResult(option, result) {
      option.classList.add("search-palette-option-pull");
      const number = `#${result.number}`;
      const state = result.state[0].toUpperCase() + result.state.slice(1);
      option.setAttribute("aria-label", `Pull request ${number}, ${result.label}, ${state}`);

      const text = hostDocument.createElement("span");
      text.className = "search-palette-option-text";
      const label = hostDocument.createElement("span");
      label.className = "search-palette-label";
      appendHighlightedText(hostDocument, label, result.label, result.matchRanges, 0);
      const description = hostDocument.createElement("span");
      description.className = "search-palette-description";
      const identifier = hostDocument.createElement("span");
      identifier.className = "search-palette-pull-number";
      identifier.textContent = number;
      description.append(identifier, hostDocument.createTextNode(` · ${state}`));
      text.append(label, description);
      option.append(text);
    }

    function renderResults() {
      listbox.replaceChildren();
      for (let index = 0; index < results.length; index += 1) {
        const result = results[index];
        const option = hostDocument.createElement("div");
        option.className = "search-palette-option";
        option.id = optionId(index);
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", "false");
        if (result.kind === "pull") {
          appendPullResult(option, result);
        } else {
          appendFileResult(option, result);
        }
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
      if (overlay.hidden || state === searchState || state.request?.query !== input.value) {
        return;
      }
      searchState = state;
      const sameQuery = rowsMatchQuery();
      const previousSelection = selectedResultId;
      // Hold the painted rows through the empty first composition. On a
      // same-query refresh, also keep the selection while its provider waits.
      if (
        state.phase === "searching" &&
        results.length > 0 &&
        (state.results.length === 0 ||
          (includesPulls &&
            sameQuery &&
            previousSelection !== null &&
            !state.results.some((result) => result.id === previousSelection)))
      ) {
        renderStatus();
        return;
      }
      if (state.phase === "complete") {
        clearSearchingStatus();
        scheduleCatalogRefresh();
      }
      const previousIndex = sameQuery ? activeIndex : -1;
      const scrollTop = sameQuery ? listbox.scrollTop : 0;
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
      listbox.scrollTop = scrollTop;
      if (previousIndex >= 0 && activeIndex !== previousIndex) {
        // A late group is appended after the file rows, but a file catalog
        // refresh can grow the files ahead of a selected pull request. Keep
        // the same result selected and in view as its position changes.
        syncActiveOption(true);
      }
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
        .search({ match: "fuzzy", query, target: includesPulls ? "all" : "file" })
        .then((state) => {
          if (state) {
            consumeState(state);
          }
        })
        .catch((error) => {
          if (!overlay.hidden && input.value === query) {
            console.warn("Quick Search search failed", error);
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
      // would open a result that matched the previous query — a fast
      // typist entering B lands on a hit for A. Rows go live again the moment
      // their own completion arrives.
      if (!result || opening || !rowsMatchQuery()) {
        return;
      }
      actionSerial += 1;
      const actionId = actionSerial;
      opening = true;
      const name = result.kind === "file" ? result.path : `#${result.number}`;
      actionStatus = `Opening ${name}…`;
      renderStatus();
      /** @type {OpenOutcome} */
      let outcome;
      try {
        outcome =
          result.kind === "file"
            ? await options.openFile(result.path)
            : ((await options.openPull?.(result.number)) ?? { status: "cancelled" });
      } catch (error) {
        console.warn("Quick Search open failed", error);
        const failure = options.describeOpenFailure(error);
        outcome =
          result.kind === "pull" && failure.status === "error"
            ? { status: "error", message: "Could not open this pull request. Try again." }
            : failure;
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
        const kind = result.kind === "file" ? "file" : "pull request";
        actionStatus = outcome.message || `That ${kind} is no longer available.`;
        try {
          if (result.kind === "file") {
            await options.onNotFound?.(result.path);
          }
        } catch (error) {
          console.warn("Quick Search stale-result cleanup failed", error);
          actionStatus = "Could not refresh search results. Try again.";
          renderStatus();
          return;
        }
        if (disposed || actionId !== actionSerial || overlay.hidden) {
          return;
        }
        results = results.filter((candidate) => candidate.id !== result.id);
        activeIndex = Math.min(index, results.length - 1);
        selectedResultId = results[activeIndex]?.id || null;
        renderResults();
        if (result.kind === "file") {
          runSearch(true);
        }
        renderStatus();
        return;
      }
      if (outcome.status === "error" || outcome.status === "unreachable") {
        // Both keep the palette open with the query intact so the reader can
        // retry. An unreachable server says so instead of blaming the file.
        actionStatus = outcome.message;
        unreachableStatus = outcome.status === "unreachable" ? outcome.message : "";
        renderStatus();
        return;
      }
      actionStatus = "";
      renderStatus();
    }

    function resetForOpen() {
      options.onOpen?.();
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

    /**
     * The server answers again. A status saying it is unreachable no longer
     * describes the page, so the query's own status returns. Any other status
     * the reader has since caused stays.
     */
    function reconnected() {
      if (disposed || !unreachableStatus || actionStatus !== unreachableStatus) {
        return;
      }
      actionStatus = "";
      unreachableStatus = "";
      renderStatus();
    }

    /** @param {Event} event */
    function handleInput(event) {
      if (/** @type {{isComposing?: boolean}} */ (event).isComposing) {
        return;
      }
      if (includesPulls) {
        clearCatalogRefresh();
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
            action: "Quick Search",
            description: "Find and open a file or, on GitHub, a cached pull request.",
            hint: "Quick Search",
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
          surfaces: { help: "always", nav: "always", reveal: "always" },
        }),
        options.shortcuts.register({
          allowInEditable: true,
          bindings: [{ key: "ArrowUp" }],
          copy: {
            action: "Previous result",
            description: "Move to the previous Quick Search result, wrapping at the top.",
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
            description: "Move to the next Quick Search result, wrapping at the bottom.",
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
            description: "Open the active Quick Search result.",
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
    const unsubscribeHints = options.shortcuts.subscribe((event) => {
      const kinds = event.kind === "batch" ? event.kinds || [] : [event.kind];
      if (kinds.some((kind) => HINT_EVENT_KINDS.has(kind))) {
        renderShortcutHints();
      }
    });
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

    return Object.freeze({
      close,
      dispose,
      element: overlay,
      isOpen: () => !overlay.hidden,
      open,
      reconnected,
    });
  }

  window.MetabrowserSearchPalette = Object.freeze({ create });
})();
