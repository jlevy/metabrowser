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
  // A pull request's changed files are rows of their own: J and K on one move between files.
  const FILE_KEY_SCOPE = "pull-files";
  // When the view's code and the cached list are read ahead of the tab, on a page that is not
  // showing it: once the shell's own work is done, and no later than this.
  const PREFETCH_IDLE_TIMEOUT_MS = 2000;

  /**
   * What an address names, for the panel: a pull request's page, a native stack's page, or
   * the list and its filter.
   *
   * `file` is the changed file a page's address names, or null. `stack` is the stack whose
   * own page the address is, whose Whole stack row the list marks, or null.
   *
   * @param {MetabrowserPublicPullRouteRuntime} routes
   * @param {string} pathname
   * @param {string} search
   * @returns {Readonly<{page: number | null, filter: string | null, file: string | null, stack: number | null}> | null}
   */
  function pullAddress(routes, pathname, search) {
    const list = routes.parsePulls(pathname, search);
    if (list !== null) {
      return Object.freeze({ page: null, filter: list.state, file: null, stack: null });
    }
    const page = routes.parsePull(pathname);
    if (page === null) {
      // A stack's page is in this space too, and names no one pull request.
      const stack = routes.parseStack(pathname);
      return stack === null
        ? null
        : Object.freeze({ page: null, filter: null, file: null, stack: stack.number });
    }
    return Object.freeze({ page: page.number, filter: null, file: page.file || null, stack: null });
  }

  /**
   * Which tab an address shows, given the tab that is showing; null to leave it. A pull
   * request's address shows Pulls, and a file's address shows Files: leaving the first for the
   * second is the one way a file opens with Pulls in front, by a link on the page or by Back.
   * This only marks a panel for the address the shell already owns.
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
   *   registerPanel(panel: {id: string, label: string, focusRow: () => boolean, onFirstShow: null, onShow: () => void, onHide: () => void, reveal: (how: {scroll: "nearest" | "keep", again?: boolean}) => void, home: () => void}): void,
   *   activate(panelId: string): void,
   *   loadView(kind: string): Promise<MetabrowserPublicViewSpec | null | undefined>,
   *   container(): HTMLElement | null,
   *   toolbar?(): HTMLElement | null,
   *   metadata?(): HTMLElement | null,
   *   refreshParts?(): MetabrowserRefreshParts | null,
   *   scrollRoot(): HTMLElement | null,
   *   openPull(route: {number: number, tab: string, file?: string, jumped?: boolean, reader?: unknown, replace?: boolean, stack?: boolean}): Promise<unknown>,
   *   pageFor(number: number): unknown,
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
    let filter = "open";
    /** @type {string | null} */
    let lastPlace = null;
    let preserveScroll = false;

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
                file: here?.file ?? null,
                shown,
                // Warm PR metadata after the shell's first tree has settled in both
                // repository modes. Details use the shared bounded background scheduler.
                refreshAhead: true,
                checkout,
                // The tab's toolbar in the navigation's slot, which its filters fill.
                toolbar: deps.toolbar?.() ?? null,
                // The band under it, which the list's count and connection lines fill.
                metadata: deps.metadata?.() ?? null,
                // The navigation's one Refresh, to which the list lends its own refresh and
                // the shown pull request page's (static/refresh-plan.js).
                refreshParts: deps.refreshParts?.() ?? null,
                scrollRoot: deps.scrollRoot(),
                open: (
                  /** @type {{number: number, tab: string, file?: string, jumped?: boolean, reader?: unknown, replace?: boolean, stack?: boolean}} */ route,
                ) => deps.openPull(route),
                // A changed file's row links to its address through the route's encoder, and
                // has no link where the path cannot be one.
                fileHref: (/** @type {number} */ number, /** @type {string} */ path) => {
                  try {
                    return deps.routes.pullHref(number, "files", path);
                  } catch {
                    return null;
                  }
                },
                // A stack's changed file's row links to the stack's Changes at that file.
                stackFileHref: (/** @type {number} */ stack, /** @type {string} */ path) => {
                  try {
                    return deps.routes.stackHref(stack, "changes", path);
                  } catch {
                    return null;
                  }
                },
                // The page a file row jumps in, while it is that pull request's.
                pageFor: (/** @type {number} */ number) => deps.pageFor(number),
                onPageChange: (listener) => deps.routes.onPageChange(listener),
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
          const there = address();
          handle?.setCurrent(there?.page ?? null, there?.file ?? null, {
            preserveScroll,
            stack: there?.stack ?? null,
          });
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
     * The list's filter changed: the reader chose it, or a navigation moved the list to the
     * filter that draws the pull request it named (pulls-panel.js, `placeSought`). At the
     * list's address it is part of the address; at a pull request's page it is the panel's,
     * and the address keeps naming that pull request.
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
     * Give the list's roving row focus, the selected pull request's when it has one, as
     * the Pulls tab's letter does after it switches to the tab. Reports whether a row took
     * focus; before the list has rows, the tab button keeps it.
     */
    function focusRow() {
      const container = deps.container();
      // A pull request's row, or a stack's while the list is grouped by stack.
      const row =
        container?.querySelector('.github-pulls-row[tabindex="0"]') ??
        container?.querySelector(".github-pulls-row");
      if (!(row instanceof HTMLElement)) {
        return false;
      }
      row.focus();
      return true;
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
     * A step that stays in one place, such as a fragment in a file, moves no tab.
     * Back from one filter of the list to another shows the list.
     *
     * *preserveScroll* is a tab's landing: the list stays where the reader left it until
     * the address moves on or a reveal asks for the row, and a view that mounts after the
     * landing is told so then. *reveal* is the shell's reveal, which ends that kept scroll.
     * *again* is its one-shot intent for an open of the pull request shown: the row is
     * revealed although the address names the current one (docs/design-system.md,
     * "Navigation Reveals the Item").
     */
    /** @param {{preserveScroll?: boolean, reveal?: boolean, again?: boolean}} [options] */
    function routeChanged(options = {}) {
      if (disposed) {
        return;
      }
      const { pathname, search } = deps.location();
      const herePlace = place(pathname, search);
      if (herePlace !== lastPlace) {
        preserveScroll = options.preserveScroll === true;
        lastPlace = herePlace;
        const tab = tabForAddress(deps.routes, pathname, search, deps.activeTab());
        if (tab !== null) {
          deps.activate(tab);
        }
      } else if (options.preserveScroll) {
        preserveScroll = true;
      } else if (options.reveal === true) {
        // The reader asked for the item, which a tab's landing kept the list away from.
        preserveScroll = false;
      }
      const here = address();
      if (handle !== null) {
        handle.setCurrent(here?.page ?? null, here?.file ?? null, {
          preserveScroll,
          stack: here?.stack ?? null,
          ...(options.again === true ? { again: true } : {}),
        });
        if (here?.filter) {
          handle.setFilter(here.filter);
        }
      }
    }

    /**
     * The Pulls panel's reveal (main-tabs.js, `reveal`): the pull request the address names
     * is marked, its closed stack opens, and its row scrolls into view unless the tab's
     * own landing keeps the list where the reader left it. The pull request already
     * current is revealed only *again*, by an open of it.
     *
     * @param {{scroll: "nearest" | "keep", again?: boolean}} how
     */
    function reveal(how) {
      routeChanged(
        how.scroll === "keep"
          ? { preserveScroll: true }
          : { reveal: true, ...(how.again === true ? { again: true } : {}) },
      );
    }

    /**
     * The Pulls panel's Home (main-tabs.js, `goHome`): the mounted list puts back what a
     * fresh load draws, from the rows it holds. A list not mounted yet draws that already.
     * What the address decides follows the addresses (`routeChanged`): the current pull
     * request the `/view/` Home opens, and the filter the list's address the tab's next
     * open lands on.
     */
    function home() {
      if (!disposed) {
        handle?.home?.();
      }
    }

    /** The active PR renderer may offer stack navigation; custom renderers need not.
     * @returns {MetabrowserPublicPullStackNavigation | null}
     */
    function stackPage() {
      if (disposed || !shown || deps.activeTab() !== PANEL_ID) {
        return null;
      }
      const number = address()?.page;
      if (number === null || number === undefined) {
        return null;
      }
      const page = /** @type {Partial<MetabrowserPublicPullStackNavigation> | null | undefined} */ (
        deps.pageFor(number)
      );
      if (typeof page?.hasStack !== "function" || typeof page.moveStack !== "function") {
        return null;
      }
      return page.hasStack() ? /** @type {MetabrowserPublicPullStackNavigation} */ (page) : null;
    }

    return Object.freeze({
      /** Register the tab, show it where the address asks, and read ahead where it does not. */
      start() {
        deps.registerPanel({
          id: PANEL_ID,
          label: "Pulls",
          focusRow,
          onFirstShow: null,
          onShow,
          onHide,
          reveal,
          home,
        });
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
        // Read metadata in idle time without making Files startup wait for GitHub.
        if (handle === null && mounting === null) {
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
      /** @param {number} number */
      toggleFiles: (number) => handle?.toggleFiles(number) ?? false,
      /** @param {number} number */
      toggleStack: (number) => handle?.toggleStack(number) ?? false,
      /** @param {number} stack */
      toggleStackFiles: (stack) => handle?.toggleStackFiles(stack) ?? false,
      hasStack: () => stackPage() !== null,
      /** @param {-1 | 1} delta */
      moveStack: (delta) => stackPage()?.moveStack(delta) ?? false,
      expand: () => handle?.expand() ?? false,
      collapse: () => handle?.collapse() ?? false,
      /** @param {-1 | 1} delta @param {{repeat?: boolean}} [how] */
      moveFile: (delta, how) => handle?.moveFile(delta, how) ?? false,
      fileLeft: () => handle?.fileLeft() ?? false,
      fileRight: () => handle?.fileRight() ?? false,
      activateFile: () => handle?.activateFile() ?? false,
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
    // Control-N and Control-P, next and previous as in Emacs and the macOS text system,
    // walk the stack, so N stays free and P opens the Pulls tab. They are global, so a
    // focused Pulls row keeps J and K, and Shift changes neither pair; a text field keeps
    // them. They are bound only where Control reaches the page, macOS and iOS: elsewhere
    // Ctrl+N and Ctrl+P are the browser's, a new window and Print, and the stack menu
    // walks the stack (docs/design-system.md, "Control Chords"). A held chord walks once
    // and its repeats are consumed, so none falls through to the browser.
    const stackKeys = shortcuts.controlReachesPage()
      ? [
          shortcuts.register({
            bindings: [{ key: "n", control: true }],
            available: () => nav.hasStack(),
            copy: {
              action: "Next in stack",
              description: "Open the next pull request toward the top of the stack.",
              hint: "Stack",
            },
            group: "pull-stack",
            handler: (context) => repeating(context) === true || nav.moveStack(1),
            id: "pulls.stack.top",
            order: 10,
            repeat: true,
            scope: "global",
            surfaces: { help: "always", reveal: "always" },
          }),
          shortcuts.register({
            bindings: [{ key: "p", control: true }],
            available: () => nav.hasStack(),
            copy: {
              action: "Previous in stack",
              description: "Open the previous pull request toward the stack base.",
              hint: "Stack",
            },
            group: "pull-stack",
            handler: (context) => repeating(context) === true || nav.moveStack(-1),
            id: "pulls.stack.base",
            order: 20,
            repeat: true,
            scope: "global",
            surfaces: { help: "always", reveal: "always" },
          }),
        ]
      : [];
    return [
      ...stackKeys,
      shortcuts.register({
        bindings: [{ key: "ArrowUp" }, { key: "k" }],
        copy: {
          action: "Previous pull request",
          description: "Open the previous pull request in the list, or go to a stack's row.",
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
          description: "Open the next pull request in the list, or go to a stack's row.",
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
        bindings: [{ key: "Enter" }],
        copy: {
          action: "Open pull request",
          description: "Open the focused pull request, or open or close the focused stack.",
          hint: "Open",
        },
        group: "pull-requests",
        handler: () => nav.activateAnchor(),
        id: "pulls.open",
        order: 30,
        scope: KEY_SCOPE,
        surfaces: { help: "always" },
      }),
      shortcuts.register({
        bindings: [{ key: " " }],
        copy: {
          action: "Toggle changed files",
          description:
            "Expand or collapse the changed files of the focused pull request, or the focused stack.",
          hint: "Changes",
        },
        group: "pull-requests",
        handler(context) {
          const event = /** @type {{event?: KeyboardEvent}} */ (context).event;
          const target = event?.target;
          // Consume held Space without toggling again. The element's actual focus can
          // outlast a catalog update that changes the tab stop, so the focused row says
          // which: a stack's row carries its stack's number, and a pull request's row, the
          // item of its three lines, its own, whose changed files Space opens or closes as
          // it does a folder's (mb-1z7j). Space is consumed either way, as every row
          // collection's is, so it does not scroll the list a page from under the row.
          if (!(target instanceof HTMLElement)) {
            return false;
          }
          if (target.matches(".github-pulls-stack-row")) {
            return event?.repeat === true || nav.toggleStack(Number(target.dataset.stack));
          }
          // A Whole stack row's children are its stack's changed files, as a pull request's
          // row's are its own: Space opens or closes them, and Enter opens the stack's page.
          if (target.matches(".github-pulls-whole-row")) {
            return event?.repeat === true || nav.toggleStackFiles(Number(target.dataset.stack));
          }
          if (target.matches(".github-pulls-row")) {
            return event?.repeat === true || nav.toggleFiles(Number(target.dataset.number));
          }
          return false;
        },
        id: "pulls.toggle-files",
        order: 35,
        repeat: true,
        scope: KEY_SCOPE,
        surfaces: { help: "always" },
      }),
      shortcuts.register({
        bindings: [{ key: "ArrowRight" }],
        copy: {
          action: "Show changed files",
          description:
            "Show the focused pull request's changed files, or go to the first; on a stack, its pull requests.",
          hint: "Changes",
        },
        group: "pull-requests",
        handler: () => nav.expand(),
        id: "pulls.files",
        order: 40,
        scope: KEY_SCOPE,
        surfaces: { help: "always" },
      }),
      shortcuts.register({
        bindings: [{ key: "ArrowLeft" }],
        copy: {
          action: "Hide changed files",
          description:
            "Hide the focused pull request's changed files, or go to its stack; on a stack, close it.",
          hint: "Changes",
        },
        group: "pull-requests",
        handler: () => nav.collapse(),
        id: "pulls.hide-files",
        order: 50,
        scope: KEY_SCOPE,
        surfaces: { help: "always" },
      }),
      // A pull request's changed files, a collection of their own: moving shows the file in
      // Changes, and the folders open and close as the Files tree's do.
      shortcuts.register({
        bindings: [{ key: "ArrowUp" }, { key: "k" }],
        copy: {
          action: "Previous changed file",
          description: "Show the previous changed file in Changes.",
          hint: "Browse",
        },
        group: "pull-requests",
        handler: (context) => nav.moveFile(-1, { repeat: repeating(context) === true }),
        id: "pulls.files.previous",
        order: 60,
        repeat: true,
        scope: FILE_KEY_SCOPE,
        surfaces: { help: "always" },
      }),
      shortcuts.register({
        bindings: [{ key: "ArrowDown" }, { key: "j" }],
        copy: {
          action: "Next changed file",
          description: "Show the next changed file in Changes.",
          hint: "Browse",
        },
        group: "pull-requests",
        handler: (context) => nav.moveFile(1, { repeat: repeating(context) === true }),
        id: "pulls.files.next",
        order: 70,
        repeat: true,
        scope: FILE_KEY_SCOPE,
        surfaces: { help: "always" },
      }),
      shortcuts.register({
        bindings: [{ key: "ArrowLeft" }],
        copy: {
          action: "Parent or collapse",
          description: "Collapse the focused folder, or go to the row that holds it.",
          hint: "Navigate folders",
        },
        group: "pull-requests",
        handler: () => nav.fileLeft(),
        id: "pulls.files.parent",
        order: 80,
        repeat: true,
        scope: FILE_KEY_SCOPE,
        surfaces: { help: "always" },
      }),
      shortcuts.register({
        bindings: [{ key: "ArrowRight" }],
        copy: {
          action: "Child or expand",
          description: "Expand the focused folder, or go to its first row.",
          hint: "Navigate folders",
        },
        group: "pull-requests",
        handler: () => nav.fileRight(),
        id: "pulls.files.child",
        order: 90,
        repeat: true,
        scope: FILE_KEY_SCOPE,
        surfaces: { help: "always" },
      }),
      shortcuts.register({
        bindings: [{ key: "Enter" }, { key: " " }],
        copy: {
          action: "Open changed file",
          description: "Open the focused changed file, or toggle the focused folder.",
          hint: "Open",
        },
        group: "pull-requests",
        handler: () => nav.activateFile(),
        id: "pulls.files.open",
        order: 100,
        scope: FILE_KEY_SCOPE,
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
  /** The scope active while a row has focus: a pull request's row's, or a changed file's. */
  /** @type {string | null} */
  let activeScope = null;

  /**
   * Which keys a focused element takes: a pull request's row's, a stack's row's among them, a
   * changed file's row's, or none.
   *
   * @param {EventTarget | null} target
   */
  const scopeOf = (target) =>
    !(target instanceof Element)
      ? null
      : target.closest(".github-pulls-row") !== null
        ? KEY_SCOPE
        : target.closest(".github-pull-file-row, .github-pull-folder-row") !== null
          ? FILE_KEY_SCOPE
          : null;

  function leaveScope() {
    deactivateScope?.();
    deactivateScope = null;
    activeScope = null;
  }

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
    leaveScope();
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
      checkout: sdk.sourceKind() === "filesystem" || Boolean(window.METABROWSER_SOURCE_CHECKOUT),
      location: () => window.location,
      pushHref: (href) => {
        window.history.pushState(null, "", href);
        shell.rememberMainTabAddress();
      },
      activeTab: () =>
        document.querySelector(".nav-tab-bar .tab-btn.active")?.getAttribute("data-tab") ?? null,
      registerPanel: shell.registerNavPanel,
      activate: shell.activateNavPanel,
      loadView: async (kind) => {
        await sdk.ensureKindAssets(kind);
        return sdk.getRegisteredView(kind, kind);
      },
      container: () => document.getElementById("tab-pulls"),
      toolbar: () => document.getElementById("nav-toolbar-pulls"),
      metadata: () => document.getElementById("nav-metadata-pulls"),
      refreshParts: () => window.MetabrowserRefreshPlan?.plan() ?? null,
      scrollRoot: () => document.getElementById("tree-content"),
      openPull: (route) =>
        shell.openPullRequest(route).catch((error) => {
          console.error("metabrowser pulls tab: the pull request could not open", error);
        }),
      // The page host the shell made, which pull-route.js keeps for what sits beside the pane.
      pageFor: (number) => routes.attachedHost()?.pageFor(number) ?? null,
      schedulePrefetch: (callback) => sdk.whenIdle(callback, { timeout: PREFETCH_IDLE_TIMEOUT_MS }),
      cancelPrefetch: (cancel) => /** @type {() => void} */ (cancel)(),
      showFailure(container) {
        const said = document.createElement("p");
        said.className = "github-pulls-empty";
        said.setAttribute("role", "alert");
        said.textContent = "Could not load the pull requests. Reload the page to try again.";
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
        const scope = scopeOf(event.target);
        if (scope !== null && scope !== activeScope) {
          leaveScope();
          deactivateScope = boundShortcuts?.activateScope(scope) ?? null;
          activeScope = scope;
        }
      },
      { signal },
    );
    container?.addEventListener(
      "focusout",
      (event) => {
        if (scopeOf(/** @type {FocusEvent} */ (event).relatedTarget) !== activeScope) {
          leaveScope();
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
    window.addEventListener("popstate", () => nav.routeChanged(), { signal });
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
    routeChanged: (/** @type {{preserveScroll?: boolean}} */ options) =>
      current?.routeChanged(options),
    tabForAddress,
  });
})();
