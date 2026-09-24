// A served mirror's branch and tag selector.
//
// A page on a mirror's pin shows a compact button naming the ref it was rendered for.
// Opening it lists the mirror's branches or tags from GET /api/source/refs, the
// default branch first and the served ref marked, narrowed by a filter box; the server
// bounds and counts the list, and the page says when it stops short. Choosing a ref
// switches the served pin with POST /api/source/pin -- a same-origin JSON request
// behind the server's guard -- and names the page's own /view/ address, so the answer
// says where the page goes: the same file or folder when the new revision has it,
// else the root.
//
// Every decision lives here without a DOM: `describe` turns the selector's state into
// what it shows, and `createSelector` owns loading, filtering, stale answers, and the
// switch through injected dependencies. `mount` is the browser glue that supplies real
// fetch, timers, focus, and paint. tests/dom/source-ref-selector-session.js runs the
// same functions from the command line.

(() => {
  const REFS_ROUTE = "/api/source/refs";
  const PIN_ROUTE = "/api/source/pin";
  const VIEW_PREFIX = "/view/";
  const BRANCH_PREFIX = "refs/remotes/origin/";
  const TAG_PREFIX = "refs/tags/";
  const PULL_HEAD = /^refs\/pull\/([1-9][0-9]{0,9})\/head$/;
  // Typing narrows the list through the server, which reads the mirror's refs once per
  // request; waiting for a short pause in typing asks once per word, not per key.
  const FILTER_DELAY_MS = 150;

  /** @type {Readonly<Record<MetabrowserSourceRefKind, string>>} */
  const KIND_PLURAL = Object.freeze({ branch: "branches", tag: "tags" });

  /**
   * What the button says for the ref and commit a page was rendered for. Pure.
   *
   * @param {MetabrowserSourcePage | null} shown
   * @returns {{kind: string, name: string}}
   */
  function shownLabel(shown) {
    if (shown === null) {
      return { kind: "Revision", name: "" };
    }
    const ref = shown.ref ?? "";
    if (ref.startsWith(BRANCH_PREFIX)) {
      return { kind: "Branch", name: ref.slice(BRANCH_PREFIX.length) };
    }
    if (ref.startsWith(TAG_PREFIX)) {
      return { kind: "Tag", name: ref.slice(TAG_PREFIX.length) };
    }
    const pull = PULL_HEAD.exec(ref);
    if (pull !== null) {
      return { kind: "Pull request", name: `#${pull[1]}` };
    }
    return { kind: "Commit", name: shown.pin.slice(0, 12) };
  }

  /**
   * @param {unknown} value
   * @returns {value is MetabrowserSourceRefListing}
   */
  function isListing(value) {
    if (value === null || typeof value !== "object") {
      return false;
    }
    const record = /** @type {Record<string, unknown>} */ (value);
    return (
      (record.kind === "branch" || record.kind === "tag") &&
      typeof record.query === "string" &&
      typeof record.total === "number" &&
      typeof record.truncated === "boolean" &&
      Array.isArray(record.refs)
    );
  }

  /**
   * What the selector shows for one state. Pure.
   *
   * @param {MetabrowserSourceRefSelectorState} state
   * @returns {MetabrowserSourceRefSelectorModel}
   */
  function describe(state) {
    const label = shownLabel(state.shown);
    const plural = KIND_PLURAL[state.kind];
    const listing = state.listing;
    /** @type {MetabrowserSourceRefSelectorModel["rows"]} */
    const rows =
      listing === null
        ? []
        : listing.refs.map((row) => ({
            name: row.name,
            ref: row.ref,
            commit: row.commit.slice(0, 12),
            default: row.default,
            current: row.current,
          }));
    let note = "";
    if (state.loading && listing === null) {
      note = `Loading ${plural}…`;
    } else if (listing !== null && listing.refs.length === 0) {
      note = listing.query === "" ? `The mirror has no ${plural}.` : `No ${plural} match.`;
    } else if (listing?.truncated) {
      note = `Showing ${listing.refs.length} of ${listing.total} ${plural}; filter to narrow.`;
    }
    return {
      button: label.name === "" ? label.kind : `${label.kind}: ${label.name}`,
      open: state.open,
      kind: state.kind,
      query: state.query,
      loading: state.loading,
      switching: state.switching,
      rows,
      note,
      error: state.error,
    };
  }

  /**
   * Where a key moves focus among the list's rows. Pure.
   *
   * *index* is the focused row, or -1 for the filter box; the answer is the row to
   * focus, -1 for the filter box, or `null` when the key does not move focus there.
   * Down from the filter box enters the list and up from the first row leaves it;
   * Home and End jump within the list but are left to the filter box's own caret.
   *
   * @param {string} key
   * @param {number} index
   * @param {number} count
   * @returns {number | null}
   */
  function moveRow(key, index, count) {
    if (count === 0) {
      return null;
    }
    if (index < 0) {
      return key === "ArrowDown" ? 0 : null;
    }
    switch (key) {
      case "ArrowDown":
        return Math.min(index + 1, count - 1);
      case "ArrowUp":
        return index - 1;
      case "Home":
        return 0;
      case "End":
        return count - 1;
      default:
        return null;
    }
  }

  /**
   * Why a switch was refused, the way the selector says it.
   *
   * @param {number} status
   * @param {unknown} body
   */
  function switchFailure(status, body) {
    const record = /** @type {{code?: unknown} | null} */ (
      body !== null && typeof body === "object" ? body : null
    );
    const code = record !== null && typeof record.code === "string" ? record.code : "";
    if (code === "selection_pending") {
      return "The mirror is fetching that ref; choose it again when the fetch ends.";
    }
    if (code === "selection_not_found") {
      return "That ref is no longer in the mirror.";
    }
    return `Could not switch (${code || `HTTP ${status}`}).`;
  }

  /**
   * The loading, filtering, and switching state machine for one page.
   *
   * *options.shown* is the pin and ref the page was rendered for, which the server
   * writes into a pin's page. A switch that leaves the server serving exactly that
   * only closes the selector; any other answer opens where the server says.
   *
   * @param {MetabrowserSourceRefSelectorDependencies} deps
   * @param {{shown?: MetabrowserSourcePage | null}} [options]
   */
  function createSelector(deps, options = {}) {
    /** @type {MetabrowserSourceRefSelectorState} */
    const state = {
      shown: options.shown ?? null,
      open: false,
      kind: "branch",
      query: "",
      listing: null,
      loading: false,
      switching: false,
      error: null,
    };
    // Each listing request takes the next number; only the newest one's answer counts,
    // so a slow answer to an older filter never replaces a newer one. A newer request,
    // closing, or disposal also aborts the older one, so the server is not left reading
    // refs for a list nobody will see.
    let requested = 0;
    /** @type {AbortController | null} */
    let inflight = null;
    /** @type {unknown} */
    let filterTimer = null;
    let disposed = false;

    function render() {
      if (!disposed) {
        deps.render(describe(state));
      }
    }

    function clearFilterTimer() {
      if (filterTimer !== null) {
        deps.cancel(filterTimer);
        filterTimer = null;
      }
    }

    function abortInflight() {
      inflight?.abort();
      inflight = null;
    }

    async function load() {
      clearFilterTimer();
      abortInflight();
      requested += 1;
      const ticket = requested;
      const controller = new AbortController();
      inflight = controller;
      state.loading = true;
      render();
      const params = new URLSearchParams({ kind: state.kind });
      if (state.query !== "") {
        params.set("q", state.query);
      }
      /** @type {MetabrowserSourceRefListing | null} */
      let listing = null;
      /** @type {string | null} */
      let error = null;
      try {
        const response = await deps.request(
          "GET",
          `${REFS_ROUTE}?${params}`,
          undefined,
          controller.signal,
        );
        if (response.status === 200 && isListing(response.body)) {
          listing = response.body;
        } else {
          error = `The ${KIND_PLURAL[state.kind]} could not be listed (HTTP ${response.status}).`;
        }
      } catch {
        error = "The server did not answer.";
      }
      if (disposed || ticket !== requested) {
        return;
      }
      inflight = null;
      state.loading = false;
      state.listing = listing;
      state.error = error;
      render();
    }

    function open() {
      if (disposed || state.open) {
        return Promise.resolve();
      }
      state.open = true;
      state.error = null;
      return load();
    }

    function close() {
      if (disposed || !state.open) {
        return;
      }
      clearFilterTimer();
      // An answer still on its way belongs to a list nobody is looking at.
      abortInflight();
      requested += 1;
      state.open = false;
      state.loading = false;
      render();
    }

    function toggle() {
      if (state.open) {
        close();
        return Promise.resolve();
      }
      return open();
    }

    /** @param {MetabrowserSourceRefKind} kind */
    function setKind(kind) {
      if (disposed || !state.open || kind === state.kind) {
        return Promise.resolve();
      }
      state.kind = kind;
      state.listing = null;
      return load();
    }

    /** @param {string} query */
    function setQuery(query) {
      if (disposed || !state.open || query === state.query) {
        return;
      }
      state.query = query;
      clearFilterTimer();
      filterTimer = deps.schedule(() => {
        filterTimer = null;
        void load();
      }, FILTER_DELAY_MS);
    }

    /** @param {string} ref The full store ref a listed row names. */
    async function choose(ref) {
      if (disposed || state.switching) {
        return;
      }
      state.switching = true;
      state.error = null;
      render();
      const view = deps.currentView();
      /** @type {Record<string, string>} */
      const body = { ref };
      if (view?.startsWith(VIEW_PREFIX)) {
        body.view = view;
      }
      try {
        const response = await deps.request("POST", PIN_ROUTE, body);
        if (disposed) {
          return;
        }
        const answer =
          /** @type {{status?: MetabrowserSourceStatus, view_href?: unknown} | null} */ (
            response.body
          );
        if (response.status === 200 && answer !== null) {
          const served = answer.status;
          const shown = state.shown;
          if (
            served !== undefined &&
            shown !== null &&
            served.pin === shown.pin &&
            served.ref === shown.ref
          ) {
            state.switching = false;
            close();
            return;
          }
          const href = answer.view_href;
          deps.navigate(
            typeof href === "string" && href.startsWith(VIEW_PREFIX) ? href : VIEW_PREFIX,
          );
          return;
        }
        state.error = switchFailure(response.status, response.body);
      } catch {
        state.error = "The switch request failed.";
      }
      state.switching = false;
      render();
    }

    function dispose() {
      disposed = true;
      clearFilterTimer();
      abortInflight();
    }

    render();
    return Object.freeze({
      open,
      close,
      toggle,
      setKind,
      setQuery,
      choose,
      dispose,
      snapshot: () => ({ ...state, filterPending: filterTimer !== null }),
    });
  }

  /**
   * Paint one model. Browser only.
   *
   * The skeleton is built once so the filter box keeps its focus and caret while the
   * list under it changes; only the button's text, the tabs' state, the list, and the
   * notes are repainted.
   *
   * @param {MetabrowserSourceRefSelectorParts} parts
   * @param {MetabrowserSourceRefSelectorModel} model
   * @param {(ref: string) => void} choose
   */
  function paint(parts, model, choose) {
    parts.toggle.textContent = model.button;
    parts.toggle.setAttribute("aria-expanded", String(model.open));
    parts.panel.hidden = !model.open;
    parts.root.dataset.open = String(model.open);
    if (!model.open) {
      return;
    }
    for (const [kind, tab] of Object.entries(parts.tabs)) {
      tab.setAttribute("aria-pressed", String(kind === model.kind));
    }
    parts.filter.placeholder = `Filter ${KIND_PLURAL[model.kind]}`;
    parts.filter.setAttribute("aria-label", `Filter ${KIND_PLURAL[model.kind]}`);
    if (parts.filter.value !== model.query) {
      parts.filter.value = model.query;
    }
    parts.list.setAttribute("aria-busy", String(model.loading || model.switching));
    // One row takes Tab at a time: the served one, else the first. Arrow keys move
    // among the rest.
    const current = model.rows.findIndex((row) => row.current);
    const roving = current >= 0 ? current : 0;
    const items = model.rows.map((row, index) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "menu-item source-ref-selector-row";
      button.disabled = model.switching;
      button.tabIndex = index === roving ? 0 : -1;
      if (row.current) {
        button.setAttribute("aria-current", "true");
      }
      const name = document.createElement("span");
      name.className = "source-ref-selector-name";
      name.textContent = row.name;
      button.append(name);
      if (row.default) {
        const badge = document.createElement("span");
        badge.className = "source-ref-selector-badge";
        badge.textContent = "default";
        button.append(badge);
      }
      const commit = document.createElement("span");
      commit.className = "source-ref-selector-commit";
      commit.textContent = row.commit;
      button.append(commit);
      button.addEventListener("click", () => choose(row.ref));
      // The row's name is cut short with an ellipsis when it is wider than the list;
      // the tooltip then carries the whole name. pointerenter comes before the
      // mouseenter the shell's tooltip listens for.
      button.addEventListener("pointerenter", () => {
        if (name.scrollWidth > name.clientWidth) {
          button.dataset.tipText = row.name;
        } else {
          delete button.dataset.tipText;
        }
      });
      item.append(button);
      return item;
    });
    parts.list.replaceChildren(...items);
    parts.note.textContent = model.note;
    parts.note.hidden = model.note === "";
    parts.error.textContent = model.error ?? "";
    parts.error.hidden = model.error === null;
  }

  /**
   * Build the selector's elements inside *element*. Browser only.
   *
   * @param {HTMLElement} element
   * @returns {MetabrowserSourceRefSelectorParts}
   */
  function build(element) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "source-ref-selector-toggle";
    toggle.setAttribute("aria-haspopup", "dialog");
    toggle.dataset.tipText = "Switch branch or tag";
    const panel = document.createElement("div");
    panel.className = "source-ref-selector-panel menu";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Switch branch or tag");
    panel.hidden = true;
    const tabs = /** @type {Record<MetabrowserSourceRefKind, HTMLButtonElement>} */ ({});
    const tabRow = document.createElement("div");
    tabRow.className = "source-ref-selector-kinds";
    tabRow.setAttribute("role", "group");
    tabRow.setAttribute("aria-label", "Show");
    for (const kind of /** @type {MetabrowserSourceRefKind[]} */ (["branch", "tag"])) {
      const tab = document.createElement("button");
      tab.type = "button";
      tab.className = "source-ref-selector-kind";
      tab.textContent = kind === "branch" ? "Branches" : "Tags";
      tabs[kind] = tab;
      tabRow.append(tab);
    }
    const filter = document.createElement("input");
    filter.type = "search";
    filter.className = "source-ref-selector-filter";
    filter.autocomplete = "off";
    filter.spellcheck = false;
    const list = document.createElement("ul");
    list.className = "source-ref-selector-list";
    const note = document.createElement("p");
    note.className = "source-ref-selector-note";
    note.setAttribute("role", "status");
    const error = document.createElement("p");
    error.className = "source-ref-selector-error";
    error.setAttribute("role", "alert");
    panel.append(tabRow, filter, list, note, error);
    element.replaceChildren(toggle, panel);
    element.hidden = false;
    return { root: element, toggle, panel, tabs, filter, list, note, error };
  }

  /**
   * Start the selector on this page with the browser's fetch, timers, focus, and paint.
   *
   * @param {HTMLElement} element
   */
  function mount(element) {
    const parts = build(element);
    /** @type {ReturnType<typeof createSelector> | null} */
    let selector = null;
    const choose = (/** @type {string} */ ref) => void selector?.choose(ref);
    selector = createSelector(
      {
        async request(method, route, body, signal) {
          const response = await fetch(route, {
            method,
            signal,
            headers: method === "POST" ? { "content-type": "application/json" } : {},
            cache: "no-store",
            body: method === "POST" ? JSON.stringify(body ?? {}) : undefined,
          });
          let parsed = null;
          try {
            parsed = await response.json();
          } catch {
            parsed = null;
          }
          return { status: response.status, etag: null, body: parsed };
        },
        schedule: (callback, delayMs) => window.setTimeout(callback, delayMs),
        cancel: (handle) => window.clearTimeout(/** @type {number} */ (handle)),
        render: (model) => paint(parts, model, choose),
        navigate: (href) => window.location.assign(href),
        currentView: () => window.location.pathname,
      },
      { shown: window.METABROWSER_SOURCE_PIN ?? null },
    );
    const mounted = selector;
    const listening = new AbortController();
    const signal = listening.signal;
    parts.toggle.addEventListener(
      "click",
      () => {
        void mounted.toggle();
        if (!parts.panel.hidden) {
          parts.filter.focus();
        }
      },
      { signal },
    );
    for (const [kind, tab] of Object.entries(parts.tabs)) {
      tab.addEventListener(
        "click",
        () => void mounted.setKind(/** @type {MetabrowserSourceRefKind} */ (kind)),
        { signal },
      );
    }
    parts.filter.addEventListener("input", () => mounted.setQuery(parts.filter.value), {
      signal,
    });
    const rows = () =>
      /** @type {HTMLButtonElement[]} */ ([...parts.list.querySelectorAll("button")]);
    // While the list is open, Escape closes it from anywhere on the page and Tab stays
    // inside it, wrapping at either end, as in a dialog.
    document.addEventListener(
      "keydown",
      (event) => {
        if (parts.panel.hidden) {
          return;
        }
        if (event.key === "Escape") {
          event.preventDefault();
          mounted.close();
          parts.toggle.focus();
          return;
        }
        if (event.key !== "Tab") {
          return;
        }
        /** @type {HTMLElement[]} */
        const stops = [
          ...Object.values(parts.tabs),
          parts.filter,
          ...rows().filter((row) => row.tabIndex === 0 && !row.disabled),
        ];
        const at = stops.indexOf(/** @type {HTMLElement} */ (document.activeElement));
        const next = event.shiftKey
          ? at <= 0
            ? stops.length - 1
            : at - 1
          : at === -1 || at === stops.length - 1
            ? 0
            : at + 1;
        event.preventDefault();
        stops[next]?.focus();
      },
      { signal },
    );
    parts.panel.addEventListener(
      "keydown",
      (event) => {
        const list = rows();
        const index = list.indexOf(/** @type {HTMLButtonElement} */ (event.target));
        if (index < 0 && event.target !== parts.filter) {
          return;
        }
        const next = moveRow(event.key, index, list.length);
        if (next === null) {
          return;
        }
        event.preventDefault();
        if (next < 0) {
          parts.filter.focus();
          return;
        }
        for (const [at, row] of list.entries()) {
          row.tabIndex = at === next ? 0 : -1;
        }
        list[next]?.focus();
      },
      { signal },
    );
    // Focus that leaves the selector for another part of the page closes the list.
    element.addEventListener(
      "focusout",
      (event) => {
        const to = /** @type {Node | null} */ (event.relatedTarget);
        if (!parts.panel.hidden && to !== null && !element.contains(to)) {
          mounted.close();
        }
      },
      { signal },
    );
    // A pointer press anywhere else closes the list, as a menu closes.
    document.addEventListener(
      "pointerdown",
      (event) => {
        if (!parts.panel.hidden && !element.contains(/** @type {Node | null} */ (event.target))) {
          mounted.close();
        }
      },
      { signal },
    );
    return Object.freeze({
      ...mounted,
      dispose() {
        listening.abort();
        mounted.dispose();
        element.replaceChildren();
        element.hidden = true;
      },
    });
  }

  window.MetabrowserSourceRefSelector = Object.freeze({
    FILTER_DELAY_MS,
    createSelector,
    describe,
    mount,
    moveRow,
    shownLabel,
  });
})();
