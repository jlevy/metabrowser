// The Pulls tab's host: the shell owns the tab, and a plugin owns the view.
//
// The server writes the tab into a shell whose served root is a GitHub repository, and this
// module into that shell's `shell-tools` bundle. So a folder fetches none of this, and the
// decision costs no request, no Git, and no gh: it was made from the repository context the
// server already had. What is left is here: which tab an address shows, mounting on demand
// the view a plugin registers for the `pull-request-list` kind and handing it what it needs,
// when it is shown and hidden, and its keys, whose text the shortcut registry owns.
//
// Every decision lives here without a DOM. `createPullsNav` takes the shell through injected
// dependencies, and `mount` is the browser glue. tests/dom/pulls-nav-session.js runs the same
// functions from the command line.

(() => {
  const PANEL_ID = "pulls";
  const KIND = "pull-request-list";
  const KEY_SCOPE = "pull-rows";
  // When the view's code and the cached list are read ahead of the tab, on a page that is not
  // showing it: once the shell's own work is done, and no later than this.
  const PREFETCH_IDLE_TIMEOUT_MS = 2000;

  /**
   * What an address names, for the panel: a pull request's page, or the list and its filter.
   *
   * @param {MetabrowserPublicPullRouteRuntime} routes
   * @param {string} pathname
   * @param {string} search
   * @returns {Readonly<{page: number | null, filter: string | null}> | null}
   */
  function pullAddress(routes, pathname, search) {
    const list = routes.parsePulls(pathname, search);
    if (list !== null) {
      return Object.freeze({ page: null, filter: list.state });
    }
    const page = routes.parsePull(pathname);
    return page === null ? null : Object.freeze({ page: page.number, filter: null });
  }

  /**
   * Which tab an address shows, given the tab that is showing; null to leave it. A pull
   * request's address shows Pulls, and a file's address shows Files: leaving the first for the
   * second is the one way a file opens with Pulls in front, by a link on the page or by Back.
   * Selecting a tab by hand changes no address, so nothing here moves it off that tab until
   * the address changes.
   *
   * @param {MetabrowserPublicPullRouteRuntime} routes
   * @param {string} pathname
   * @param {string} search
   * @param {string | null} active
   * @returns {string | null}
   */
  function tabForAddress(routes, pathname, search, active) {
    if (pullAddress(routes, pathname, search) !== null) {
      return active === PANEL_ID ? null : PANEL_ID;
    }
    return active === PANEL_ID && pathname.startsWith("/view/") ? "files" : null;
  }

  /**
   * @param {{
   *   routes: MetabrowserPublicPullRouteRuntime,
   *   location(): {pathname: string, search: string},
   *   pushHref(href: string): void,
   *   activeTab(): string | null,
   *   registerPanel(panel: {id: string, label: string, onFirstShow: null, onShow: () => void, onHide: () => void}): void,
   *   activate(panelId: string): void,
   *   loadView(kind: string): Promise<MetabrowserPublicViewSpec | null | undefined>,
   *   container(): HTMLElement | null,
   *   scrollRoot(): HTMLElement | null,
   *   openPull(route: {number: number, tab: string, reader?: unknown, replace?: boolean}): Promise<unknown>,
   *   schedulePrefetch(callback: () => void): unknown,
   *   cancelPrefetch(handle: unknown): void,
   *   showFailure(container: HTMLElement): void,
   *   checkout?: boolean,
   * }} deps
   */
  function createPullsNav(deps) {
    const checkout = deps.checkout === true;
    /** @type {MetabrowserPublicPullsPanelHandle | null} */
    let handle = null;
    /** @type {Promise<void> | null} */
    let mounting = null;
    let shown = false;
    let disposed = false;
    /** @type {unknown} */
    let prefetch = null;
    let filter = "all";
    /** @type {string | null} */
    let lastPlace = null;

    function address() {
      const { pathname, search } = deps.location();
      return pullAddress(deps.routes, pathname, search);
    }

    function cancelPrefetch() {
      if (prefetch !== null) {
        deps.cancelPrefetch(prefetch);
        prefetch = null;
      }
    }

    /** Mount the view once, on the first show or the prefetch. A failed load tries again. */
    function ensureMounted() {
      if (handle !== null || disposed) {
        return Promise.resolve();
      }
      mounting ??= (async () => {
        cancelPrefetch();
        const container = deps.container();
        if (container === null) {
          return;
        }
        try {
          const view = await deps.loadView(KIND);
          if (!view) {
            throw new Error("no plugin renders the list of pull requests");
          }
          const here = address();
          if (here?.filter) {
            filter = here.filter;
          }
          const mounted = /** @type {MetabrowserPublicPullsPanelHandle | null | undefined} */ (
            await view.render(container, {
              kind: KIND,
              pullsNav: Object.freeze({
                filter,
                current: here?.page ?? null,
                shown,
                // A checkout reads and refreshes nothing until the tab is shown, by the plan's
                // rule for a checkout: the network only once the reader opens the tab. On a
                // mirror, starting the list's refresh once the first tree has settled was
                // measured against leaving it for the tab's first show, nine back-to-back pairs
                // on pallets/click at a load average of 4 to 6: first row 1.001x and the mirror's
                // own refresh 0.998x. Started as the page starts, it was 1.09x to 1.14x on the
                // first row, past the plan's 1.1x, so it starts here and not there.
                refreshAhead: !checkout,
                checkout,
                scrollRoot: deps.scrollRoot(),
                open: (
                  /** @type {{number: number, tab: string, reader?: unknown, replace?: boolean}} */ route,
                ) => deps.openPull(route),
                filterChanged: filterChanged,
              }),
            })
          );
          // Whatever replaced the page while the view loaded: this mount is nobody's.
          if (disposed) {
            mounted?.dispose();
            return;
          }
          handle = mounted ?? null;
          // The reader may have moved on while it loaded.
          handle?.setShown(shown);
          handle?.setCurrent(address()?.page ?? null);
        } catch (error) {
          console.error("metabrowser pulls tab: the list could not load", error);
          if (shown && !disposed) {
            deps.showFailure(container);
          }
        }
      })().finally(() => {
        mounting = null;
      });
      return mounting;
    }

    /**
     * The reader chose a filter. At the list's address it is part of the address; at a pull
     * request's page it is the panel's, and the address keeps naming that pull request.
     *
     * @param {string} state
     */
    function filterChanged(state) {
      filter = state;
      const { pathname, search } = deps.location();
      if (deps.routes.parsePulls(pathname, search) !== null) {
        const href = deps.routes.pullsHref(state);
        deps.pushHref(href);
        // The page is at that place now, so Back to the filter it left is a step to another.
        lastPlace = href;
      }
    }

    function onShow() {
      shown = true;
      if (handle === null) {
        void ensureMounted();
      } else {
        handle.setShown(true);
      }
    }

    function onHide() {
      shown = false;
      handle?.setShown(false);
    }

    /**
     * What of an address can move a tab: its path, and at the list's address its filter too,
     * which is part of that address. A fragment or a file's query is a step within one place.
     *
     * @param {string} pathname
     * @param {string} search
     */
    function place(pathname, search) {
      const list = deps.routes.parsePulls(pathname, search);
      return list === null ? pathname : deps.routes.pullsHref(list.state);
    }

    /**
     * The address changed, by history or in the page: which tab, and what the panel marks.
     * A step that stays in one place, such as a fragment in a file, moves no tab, so a reader
     * who chose Pulls there by hand keeps it; Back from one filter of the list to another is
     * a new place, and shows the list.
     */
    function routeChanged() {
      if (disposed) {
        return;
      }
      const { pathname, search } = deps.location();
      if (place(pathname, search) !== lastPlace) {
        lastPlace = place(pathname, search);
        const tab = tabForAddress(deps.routes, pathname, search, deps.activeTab());
        if (tab !== null) {
          deps.activate(tab);
        }
      }
      const here = address();
      if (handle !== null) {
        handle.setCurrent(here?.page ?? null);
        if (here?.filter) {
          handle.setFilter(here.filter);
        }
      }
    }

    return Object.freeze({
      /** Register the tab, show it where the address asks, and read ahead where it does not. */
      start() {
        deps.registerPanel({ id: PANEL_ID, label: "Pulls", onFirstShow: null, onShow, onHide });
        const { pathname, search } = deps.location();
        lastPlace = place(pathname, search);
        if (deps.activeTab() === PANEL_ID) {
          // The server drew the tab in front at this address; it has not been told it shows.
          deps.activate(PANEL_ID);
        } else {
          const tab = tabForAddress(deps.routes, pathname, search, deps.activeTab());
          if (tab !== null) {
            deps.activate(tab);
          }
        }
        // A checkout's tab mounts on its first show: even the cached read would load the
        // cache into a folder's server, and its refresh asks GitHub.
        if (handle === null && mounting === null && !checkout) {
          prefetch = deps.schedulePrefetch(() => {
            prefetch = null;
            void ensureMounted();
          });
        }
      },
      routeChanged,
      /** @param {-1 | 1} delta @param {{repeat?: boolean}} [how] */
      move: (delta, how) => handle?.move(delta, how) ?? false,
      released() {
        handle?.released();
      },
      activateAnchor: () => handle?.activateAnchor() ?? false,
      dispose() {
        disposed = true;
        shown = false;
        cancelPrefetch();
        handle?.dispose();
        handle = null;
      },
      snapshot: () => ({ mounted: handle !== null, mounting: mounting !== null, shown, disposed }),
    });
  }

  /**
   * The registry's descriptors for a row's keys. They are the row collection's contract
   * (docs/design-system.md, "Navigational Row Collections"): Help and the hints read this
   * text, and no other surface keeps a copy.
   *
   * @param {ReturnType<typeof createPullsNav>} nav
   * @param {ReturnType<Window["MetabrowserKeyboardShortcuts"]["create"]>} shortcuts
   */
  function registerKeys(nav, shortcuts) {
    /** @param {Record<string, unknown>} context */
    const repeating = (context) => /** @type {{event?: KeyboardEvent}} */ (context).event?.repeat;
    return [
      shortcuts.register({
        bindings: [{ key: "ArrowUp" }, { key: "k" }],
        copy: {
          action: "Previous pull request",
          description: "Open the previous pull request in the list.",
          hint: "Browse",
        },
        group: "pull-requests",
        handler: (context) => nav.move(-1, { repeat: repeating(context) === true }),
        id: "pulls.previous",
        order: 10,
        repeat: true,
        scope: KEY_SCOPE,
        surfaces: { help: "always" },
      }),
      shortcuts.register({
        bindings: [{ key: "ArrowDown" }, { key: "j" }],
        copy: {
          action: "Next pull request",
          description: "Open the next pull request in the list.",
          hint: "Browse",
        },
        group: "pull-requests",
        handler: (context) => nav.move(1, { repeat: repeating(context) === true }),
        id: "pulls.next",
        order: 20,
        repeat: true,
        scope: KEY_SCOPE,
        surfaces: { help: "always" },
      }),
      shortcuts.register({
        bindings: [{ key: "Enter" }, { key: " " }],
        copy: {
          action: "Open pull request",
          description: "Open the focused pull request.",
          hint: "Open",
        },
        group: "pull-requests",
        handler: () => nav.activateAnchor(),
        id: "pulls.open",
        order: 30,
        scope: KEY_SCOPE,
        surfaces: { help: "always" },
      }),
    ];
  }

  /** @type {ReturnType<typeof createPullsNav> | null} */
  let current = null;
  /** The host's listeners on the page, which end with it; each init makes its own. */
  /** @type {AbortController | null} */
  let listening = null;
  // The keys that walk the rows: only their release ends a walk, and not a modifier's.
  const WALK_KEYS = new Set(["ArrowUp", "ArrowDown", "j", "k", "J", "K"]);
  /** @type {Array<() => void>} */
  let unregisterKeys = [];
  /** @type {(() => void) | null} */
  let deactivateScope = null;

  /** @param {EventTarget | null} target */
  const isRow = (target) =>
    target instanceof Element && target.closest("a.github-pulls-row") !== null;

  /**
   * Bind the row keys to a registry, which a page brought back from the back/forward cache
   * after a real teardown rebuilds.
   *
   * @param {Parameters<typeof registerKeys>[1] | null} shortcuts
   */
  function bindShortcuts(shortcuts) {
    for (const unregister of unregisterKeys) {
      unregister();
    }
    unregisterKeys = [];
    deactivateScope?.();
    deactivateScope = null;
    if (current !== null && shortcuts !== null) {
      unregisterKeys = registerKeys(current, shortcuts);
      boundShortcuts = shortcuts;
    }
  }
  /** @type {Parameters<typeof registerKeys>[1] | null} */
  let boundShortcuts = null;

  /**
   * Start the tab on this page, once the pull-request routes are here. The first show mounts
   * the view, and the list's keys need only the tab's container to know a row has focus.
   *
   * @returns {Promise<void>}
   */
  async function init() {
    const shell = window.MetabrowserShell;
    const assets = window.MetabrowserAssets;
    if (current !== null || !shell || !assets) {
      return;
    }
    if (!window.MetabrowserPullRoute) {
      await assets.ensureAsset("pull-route");
    }
    const routes = window.MetabrowserPullRoute;
    const sdk = window.metabrowser;
    if (!routes) {
      return;
    }
    const nav = createPullsNav({
      routes,
      // The shell draws the tab on a pin of a GitHub mirror, and on a folder only when it is
      // a GitHub checkout.
      checkout: sdk.sourceKind() === "filesystem",
      location: () => window.location,
      pushHref: (href) => window.history.pushState(null, "", href),
      activeTab: () =>
        document.querySelector(".nav-tab-bar .tab-btn.active")?.getAttribute("data-tab") ?? null,
      registerPanel: shell.registerNavPanel,
      activate: shell.activateNavPanel,
      loadView: async (kind) => {
        await sdk.ensureKindAssets(kind);
        return sdk.getRegisteredView(kind, kind);
      },
      container: () => document.getElementById("tab-pulls"),
      scrollRoot: () => document.getElementById("tree-content"),
      openPull: (route) =>
        shell.openPullRequest(route).catch((error) => {
          console.error("metabrowser pulls tab: the pull request could not open", error);
        }),
      schedulePrefetch: (callback) =>
        typeof window.requestIdleCallback === "function"
          ? window.requestIdleCallback(callback, { timeout: PREFETCH_IDLE_TIMEOUT_MS })
          : window.setTimeout(callback, PREFETCH_IDLE_TIMEOUT_MS),
      cancelPrefetch: (handle) => {
        if (typeof window.cancelIdleCallback === "function") {
          window.cancelIdleCallback(/** @type {number} */ (handle));
        } else {
          window.clearTimeout(/** @type {number} */ (handle));
        }
      },
      showFailure(container) {
        const said = document.createElement("p");
        said.className = "github-pulls-empty";
        said.setAttribute("role", "alert");
        said.textContent = "Could not load the pull requests. Refresh the page to try again.";
        container.replaceChildren(said);
      },
    });
    current = nav;
    bindShortcuts(shell.shortcuts());
    nav.start();
    const container = document.getElementById("tab-pulls");
    listening = new AbortController();
    const { signal } = listening;
    container?.addEventListener(
      "focusin",
      (event) => {
        if (isRow(event.target) && deactivateScope === null) {
          deactivateScope = boundShortcuts?.activateScope(KEY_SCOPE) ?? null;
        }
      },
      { signal },
    );
    container?.addEventListener(
      "focusout",
      (event) => {
        if (!isRow(/** @type {FocusEvent} */ (event).relatedTarget)) {
          deactivateScope?.();
          deactivateScope = null;
        }
      },
      { signal },
    );
    container?.addEventListener(
      "keyup",
      (event) => {
        if (WALK_KEYS.has(/** @type {KeyboardEvent} */ (event).key)) {
          nav.released();
        }
      },
      { signal },
    );
    window.addEventListener("popstate", nav.routeChanged, { signal });
  }

  /** End the tab and everything it holds: the view, the keys, and the listeners. */
  function dispose() {
    listening?.abort();
    listening = null;
    bindShortcuts(null);
    current?.dispose();
    current = null;
    window.MetabrowserShell?.removeNavPanel(PANEL_ID);
  }

  window.MetabrowserPullsNav = Object.freeze({
    bindShortcuts,
    createPullsNav,
    dispose,
    init,
    pullAddress,
    registerKeys,
    routeChanged: () => current?.routeChanged(),
    tabForAddress,
  });
})();
