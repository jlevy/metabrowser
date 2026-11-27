// The pull-request page's routes and its host.
//
// A pull request's page is the view a plugin registers for the `pull-request` kind, the
// GitHub plugin's, and the list's is the same for `pull-request-list`. The host here decides
// what a route does -- switch the shown page's tab or mount a page -- and keeps the tab in the
// URL; the shell supplies the pane, this loads that plugin, and the view gets the host's `open`.
// The view owns everything else: fetching the record, polling, refreshing, and Files changed.
//
// `/pull/<n>` and its subroutes, `/stack/<n>` and its subroutes, a native stack's page, and
// `/pulls` are the pull requests' address space (Browser URL Grammar). Only such an address, or the Pulls tab, reaches this code, so it is no startup
// script of any other page. The server writes it into the shell of a pull-request address,
// where the page needs it before it can show anything; anything else takes it as the
// `pull-route` on-demand bundle.
//
// Measured 2026-10-01: in navigation.js, a startup script, this was 1,818 of 13,265
// compressed bytes on every folder's page. See
// explorations/performance-loop/experiments/exp-037.

(() => {
  const PULL_PREFIX = "/pull/";
  // Keep aligned with view_routes._PULL_NUMBER and PULL_ROUTE_TABS.
  const PULL_NUMBER_PATTERN = /^[1-9][0-9]{0,9}$/;
  const PULL_TABS = Object.freeze(["", "conversation", "docs", "files", "guided", "checks"]);
  // Keep aligned with view_routes.PULLS_ROUTE and cache.paths.PULL_LIST_NAMES.
  const PULLS_PATH = "/pulls";
  const PULL_LISTS = Object.freeze(["open", "closed", "all"]);
  // Keep aligned with view_routes.STACK_ROUTE_PREFIX and STACK_ROUTE_TABS. A stack's number
  // is GitHub's, spelled as a pull request's is.
  const STACK_PREFIX = "/stack/";
  const STACK_TABS = Object.freeze(["", "guided", "docs", "changes"]);

  /**
   * Whether *segment* may be one segment of a changed file's path: a path in the pull
   * request's comparison, checked for shape as view_routes._pull_file_segments checks it.
   *
   * @param {string} segment
   */
  function isFileSegment(segment) {
    return (
      segment !== "" &&
      segment !== "." &&
      segment !== ".." &&
      !segment.includes("/") &&
      !segment.includes("\\") &&
      !segment.includes("\0")
    );
  }

  /**
   * Encode a pull request's page: `/pull/<n>` for its front page (Guided Review when the
   * description carries a guide, Conversation otherwise), `/pull/<n>/conversation` for
   * Conversation, `/pull/<n>/files` for Changes, `/pull/<n>/guided` for Guided Review, and
   * `/pull/<n>/checks` for Checks.
   * Only Changes can name a file,
   * with each segment of the path percent-encoded.
   *
   * @param {number} number
   * @param {string} [tab]
   * @param {string} [file]
   * @returns {string}
   */
  function pullHref(number, tab = "", file = "") {
    return tabbedHref(PULL_PREFIX, PULL_TABS, "files", "pull", number, tab, file);
  }

  /**
   * Encode a native stack's page: `/stack/<n>` for its front page, `/stack/<n>/guided`,
   * `/stack/<n>/docs`, and `/stack/<n>/changes` for its tabs. Only Changes can name a file.
   *
   * @param {number} number
   * @param {string} [tab]
   * @param {string} [file]
   * @returns {string}
   */
  function stackHref(number, tab = "", file = "") {
    return tabbedHref(STACK_PREFIX, STACK_TABS, "changes", "stack", number, tab, file);
  }

  /**
   * @param {string} prefix
   * @param {readonly string[]} tabs
   * @param {string} fileTab The one tab that names a file.
   * @param {string} what
   * @param {number} number
   * @param {string} tab
   * @param {string} file
   */
  function tabbedHref(prefix, tabs, fileTab, what, number, tab, file) {
    if (!PULL_NUMBER_PATTERN.test(String(number)) || !tabs.includes(tab)) {
      throw new TypeError(`${what} route requires a ${what} number and a known tab`);
    }
    const head = `${prefix}${number}${tab ? `/${tab}` : ""}`;
    if (!file) {
      return head;
    }
    const segments = typeof file === "string" && tab === fileTab ? file.split("/") : [""];
    if (!segments.every(isFileSegment)) {
      throw new TypeError(`${what} route requires a normalized changed-file path`);
    }
    try {
      return `${head}/${segments.map((segment) => encodeURIComponent(segment)).join("/")}`;
    } catch (error) {
      throw new TypeError(`${what} route names a file by a path that is not Unicode`, {
        cause: error,
      });
    }
  }

  /**
   * Parse a pull-request page route, or null when the location is not one. `file` is the
   * changed file it names, or "" for the page.
   *
   * @param {string} pathname
   * @returns {Readonly<{number: number, tab: string, file: string}> | null}
   */
  function parsePull(pathname) {
    return parseTabbed(pathname, PULL_PREFIX, PULL_TABS, "files");
  }

  /**
   * Parse a native stack's page route, or null when the location is not one. `file` is the
   * file of its comparison that Changes names, or "" for the page. `stack` says the number
   * is a stack's, so the host's `show` opens the stack's page for it.
   *
   * @param {string} pathname
   * @returns {Readonly<{number: number, tab: string, file: string, stack: true}> | null}
   */
  function parseStack(pathname) {
    const route = parseTabbed(pathname, STACK_PREFIX, STACK_TABS, "changes");
    return route === null ? null : Object.freeze({ ...route, stack: /** @type {const} */ (true) });
  }

  /**
   * @param {string} pathname
   * @param {string} prefix
   * @param {readonly string[]} tabs
   * @param {string} fileTab
   * @returns {Readonly<{number: number, tab: string, file: string}> | null}
   */
  function parseTabbed(pathname, prefix, tabs, fileTab) {
    if (typeof pathname !== "string" || !pathname.startsWith(prefix)) {
      return null;
    }
    const segments = pathname.slice(prefix.length).split("/");
    // A trailing slash names the same page; a file has none.
    if ((segments.length === 2 || segments.length === 3) && segments[segments.length - 1] === "") {
      segments.pop();
    }
    const [number, tab = "", ...inner] = segments;
    if (
      !PULL_NUMBER_PATTERN.test(number) ||
      !tabs.includes(tab) ||
      (segments.length >= 2 && !tab) ||
      (inner.length > 0 && tab !== fileTab)
    ) {
      return null;
    }
    let decoded;
    try {
      decoded = inner.map((segment) => decodeURIComponent(segment));
    } catch {
      return null;
    }
    if (!decoded.every(isFileSegment)) {
      return null;
    }
    return Object.freeze({ number: Number(number), tab, file: decoded.join("/") });
  }

  /**
   * The list's address: `/pulls` for open pull requests and `/pulls?state=<list>` for a filter.
   *
   * @param {string} [state]
   * @returns {string}
   */
  function pullsHref(state = "open") {
    if (!PULL_LISTS.includes(state)) {
      throw new TypeError("pulls route requires a list of pull requests");
    }
    return state === "open" ? PULLS_PATH : `${PULLS_PATH}?state=${state}`;
  }

  /**
   * Parse the list's route, or null when the location is not it. A `state` the list does
   * not have is the default: the address still names the list, as a typed one may.
   *
   * @param {string} pathname
   * @param {string} [search]
   * @returns {Readonly<{state: string}> | null}
   */
  function parsePulls(pathname, search = "") {
    if (pathname !== PULLS_PATH) {
      return null;
    }
    const state = new URLSearchParams(search).get("state");
    return Object.freeze({ state: state !== null && PULL_LISTS.includes(state) ? state : "open" });
  }

  /**
   * What the shell does when history lands on *pathname*. Pure.
   *
   * *shown* is the pull request whose page holds the pane, `"list"` when the list's address
   * holds it, or null, and *heldTarget* whether the navigation controller holds a `/view/`
   * target. A pull-request route is no target, so the controller applies a landing on one
   * only when it held a target before, and then mounts the page itself. Otherwise -- back
   * and forward between a page's tabs, or onto an entry a commit replaced while the page
   * was shown -- this route decides: the page shown for the same number switches its tab,
   * and anything else mounts the page. A step between the list's filters changes nothing
   * here, since the pane says the same of each.
   *
   * A landing on one changed file's address, `/pull/<n>/files/<path>`, also names the
   * file: the page shows it in Files changed, as a click on its row in the Pulls tab does.
   * A stack's page is held as `stack:<n>`, and a landing on another stack's address, or on
   * one while no stack's page holds the pane, is `stack`.
   *
   * @param {string} pathname
   * @param {number | "list" | `stack:${number}` | null} shown
   * @param {boolean} heldTarget
   * @returns {Readonly<{action: "tab", tab: string, file?: string} | {action: "mount", number: number, tab: string, file?: string} | {action: "stack", number: number, tab: string, file?: string} | {action: "list"}> | null}
   */
  function pullHistoryAction(pathname, shown, heldTarget) {
    if (heldTarget) {
      return null;
    }
    if (parsePulls(pathname) !== null) {
      return shown === "list" ? null : Object.freeze({ action: "list" });
    }
    const stack = parseStack(pathname);
    if (stack !== null) {
      const file = stack.file ? { file: stack.file } : {};
      return shown === stackKey(stack.number)
        ? Object.freeze({ action: "tab", tab: stack.tab, ...file })
        : Object.freeze({ action: "stack", number: stack.number, tab: stack.tab, ...file });
    }
    const route = parsePull(pathname);
    if (route === null) {
      return null;
    }
    const file = route.file ? { file: route.file } : {};
    return route.number === shown
      ? Object.freeze({ action: "tab", tab: route.tab, ...file })
      : Object.freeze({ action: "mount", number: route.number, tab: route.tab, ...file });
  }

  /**
   * The key a stack's page holds the pane by, apart from a pull request of its number.
   *
   * @param {number} number
   * @returns {`stack:${number}`}
   */
  function stackKey(number) {
    return `stack:${number}`;
  }

  /**
   * The shell's host for a pull request's page. It decides what a
   * pull-request route does to the pane -- switch the shown page's tab, or claim
   * the pane and mount a page -- keeps the page's tab in the URL, and disposes a render
   * a later claim superseded. The list's address holds the pane the same way. The shell
   * supplies the pane and the history; nothing here touches the DOM.
   *
   * *claim* claims the pane and returns its token; the shell's claim calls `dispose`, so
   * whatever claims the pane next replaces the page. *mount* loads and renders the page
   * for a claim and resolves to its handle, or to null when nothing was mounted (the
   * claim was superseded, or no plugin renders the page); the page gets `open` to move
   * to a tab or to another pull request's page. A route from a reader's selection in the
   * Pulls tab also carries `reader`, which only the page reads. *mountList* is the same
   * for the list's address.
   *
   * A route that names one changed file lands on it: the page's `showFile`, once the page
   * holds the pane, shows Files changed at that file. The host keeps the page it made, and
   * `pageFor` hands it to what sits beside the pane, the Pulls tab, which walks a pull
   * request's files without moving the address on every key.
   *
   * A native stack's page (`/stack/<n>`) is held the same way, by its own key, and mounted
   * by *mount* with a route that says `stack: true`, as `show` and `open` take one; its
   * `open` takes `{stack: true}` for another of its tabs and a plain route for a member's
   * page.
   *
   * @template {{land?: (route: {tab: string, file?: string}) => void, setTab?: (tab: string) => void, showFile?: (path: string) => unknown, flush?: () => void, ready?: Promise<void>, cancelPending?: () => void, dispose?: () => void}} Handle
   * @param {{
   *   claim: () => number,
   *   isCurrent: (claim: number) => boolean,
   *   mount: (
   *     claim: number,
   *     route: Readonly<{number: number, tab: string, reader?: unknown, stack?: boolean}>,
   *     open: (route: {number: number, tab: string, file?: string, stack?: boolean, reader?: unknown, replace?: boolean}) => Promise<{status: string}>,
   *   ) => Promise<Handle | null | undefined>,
   *   mountList: (claim: number) => Promise<Handle | null | undefined>,
   *   pathname: () => string,
   *   pushHref: (href: string) => void,
   *   replaceHref: (href: string) => void,
   * }} deps
   */
  function createPullPageHost(deps) {
    /** @type {{number: number | "list" | `stack:${number}`, claim: number, handle: Handle | null, ready: boolean, opening: Promise<{status: "opened" | "cancelled"}> | null, pendingRoute: {tab: string, file?: string, jumped?: boolean} | null, restore: boolean} | null} */
    let page = null;

    // The page that holds the pane, or null once anything else claimed it or while it
    // is still mounting.
    function shown() {
      return page !== null && page.handle !== null && page.ready && deps.isCurrent(page.claim)
        ? page
        : null;
    }

    function dispose() {
      const held = page;
      page = null;
      notifyPage();
      try {
        held?.handle?.dispose?.();
      } catch (error) {
        console.error("pull-request page dispose error:", error);
      }
    }

    /** Stop the page immediately; only an already visible page may leave inert DOM behind.
     * @returns {(() => void) | null}
     */
    function release() {
      const held = page;
      page = null;
      notifyPage();
      if (!held?.handle) {
        return null;
      }
      if (!held.ready || typeof held.handle.cancelPending !== "function") {
        held.handle.dispose?.();
        return null;
      }
      held.handle.cancelPending();
      return () => held.handle?.dispose?.();
    }

    /**
     * A route's place on a page that holds the pane: its tab, or the one file it names.
     *
     * @param {Handle | null} handle
     * @param {Readonly<{tab: string, file?: string, jumped?: boolean}>} route
     * @param {boolean} restore Whether the current history entry owns a saved place.
     */
    function land(handle, route, restore) {
      if (route.jumped === true) {
        // The walk already moved the diff. Confirm its tab after the URL owns it.
        handle?.setTab?.(route.tab);
      } else if (restore) {
        handle?.land?.(route);
      } else if (route.file && typeof handle?.showFile === "function") {
        handle.showFile(route.file);
      } else {
        handle?.setTab?.(route.tab);
      }
    }

    /**
     * Claim the pane for a page and mount it.
     *
     * @param {number | "list" | `stack:${number}`} number
     * @param {(claim: number) => Promise<Handle | null | undefined>} mount
     * @param {string} [file] The changed file the route names, which the page lands on.
     * @param {boolean} [restore] A route landing, rather than a reader's new selection.
     * @param {string} [fileTab] The tab that shows a file: Files changed, or a stack's Changes.
     * @returns {Promise<{status: "opened" | "cancelled"}>}
     */
    async function take(number, mount, file = "", restore = true, fileTab = "files") {
      const claim = deps.claim();
      /** @type {NonNullable<typeof page>} */
      const mine = {
        number,
        claim,
        handle: null,
        ready: false,
        opening: null,
        pendingRoute: null,
        restore,
      };
      page = mine;
      notifyPage();
      const handle = await mount(claim);
      if (page !== mine || !deps.isCurrent(claim)) {
        handle?.dispose?.();
        return { status: "cancelled" };
      }
      if (!handle) {
        // Nothing holds the pane, so the next route to this page mounts it again.
        page = null;
        notifyPage();
        return { status: "opened" };
      }
      // Track the instance before awaiting readiness so a new claim can cancel it now.
      mine.handle = handle;
      try {
        if (handle.ready) {
          await handle.ready;
        }
      } catch {
        handle.dispose?.();
        if (page === mine) {
          page = null;
          notifyPage();
        }
        return { status: "cancelled" };
      }
      if (page !== mine || !deps.isCurrent(claim)) {
        handle.dispose?.();
        return { status: "cancelled" };
      }
      mine.ready = true;
      notifyPage();
      if (mine.pendingRoute) {
        land(handle, mine.pendingRoute, mine.restore);
      } else if (file) {
        land(handle, { tab: fileTab, file }, restore);
      }
      return { status: "opened" };
    }

    /**
     * Show a route's page, or switch its tab, or go to its file, when that page is already
     * shown. A route that says `stack: true`, as `parseStack`'s does, is a stack's page.
     *
     * @param {Readonly<{number: number, tab: string, file?: string, jumped?: boolean, reader?: unknown, stack?: boolean}>} route
     * @param {{restore?: boolean}} [how]
     * @returns {Promise<{status: "opened" | "cancelled"}>}
     */
    async function show(route, how = {}) {
      if (route.stack === true) {
        return showStack(route, how);
      }
      return showAt(route.number, route, (claim) => deps.mount(claim, route, open), how, "files");
    }

    /**
     * Show a native stack's page, or switch its tab, or go to its file in Changes.
     *
     * @param {Readonly<{number: number, tab: string, file?: string}>} route
     * @param {{restore?: boolean}} [how]
     * @returns {Promise<{status: "opened" | "cancelled"}>}
     */
    async function showStack(route, how = {}) {
      const stack = Object.freeze({ ...route, stack: true });
      return showAt(
        stackKey(route.number),
        route,
        (claim) => deps.mount(claim, stack, open),
        how,
        "changes",
      );
    }

    /**
     * @param {number | `stack:${number}`} key
     * @param {Readonly<{number: number, tab: string, file?: string, jumped?: boolean}>} route
     * @param {(claim: number) => Promise<Handle | null | undefined>} mount
     * @param {{restore?: boolean}} how
     * @param {string} fileTab
     * @returns {Promise<{status: "opened" | "cancelled"}>}
     */
    async function showAt(key, route, mount, how, fileTab) {
      const current = shown();
      if (current !== null && current.number === key) {
        land(current.handle, route, how.restore !== false);
        return { status: "opened" };
      }
      if (page !== null && page.number === key && deps.isCurrent(page.claim)) {
        // Route changes during the core wait join the same instance and keep only the
        // latest tab/file intent. They must not restart its selected provider request.
        page.pendingRoute = route;
        page.restore = how.restore !== false;
        return page.opening ?? { status: "cancelled" };
      }
      const opening = take(key, mount, route.file ?? "", how.restore !== false, fileTab);
      if (page?.number === key) {
        page.opening = opening;
      }
      return opening;
    }

    /** Show the list's address in the pane, unless it already holds the pane. */
    async function showList() {
      if (shown()?.number === "list") {
        return { status: /** @type {const} */ ("opened") };
      }
      return take("list", deps.mountList);
    }

    /**
     * Go to a page's tab or another pull request's page. A tab is a selection within
     * the page, so it owns the URL (Browser URL Grammar) and back and forward move
     * between tabs. The page shown writes its place into its own history entry first: a
     * nav row's click is outside its pane, and a key is no click at all.
     *
     * A route with *replace* is a key's skim through the Pulls tab's rows: it replaces the
     * entry, as the file tree's and Git's keys do, so a reader who passed ten rows leaves
     * them with one Back. A click, Enter, and the page's own links push. A *file* is one
     * row of a pull request's changed files, and its address is that file's. *jumped* says
     * the page of that number shows the file already, since a walk of its files jumped it key
     * by key, so only the address moves.
     *
     * A route with *stack* is a native stack's page, `/stack/<n>`, and one of its tabs.
     *
     * @param {{number: number, tab: string, file?: string, jumped?: boolean, stack?: boolean, reader?: unknown, replace?: boolean}} route
     */
    function open(route) {
      const number = Number(route.number);
      const file = typeof route.file === "string" ? route.file : "";
      const stack = route.stack === true;
      let href;
      try {
        href = stack ? stackHref(number, route.tab, file) : pullHref(number, route.tab, file);
      } catch (error) {
        return Promise.reject(error);
      }
      if (deps.pathname() !== href) {
        shown()?.handle?.flush?.();
        if (route.replace === true) {
          deps.replaceHref(href);
        } else {
          deps.pushHref(href);
        }
      }
      if (stack) {
        return showStack(Object.freeze({ number, tab: route.tab, ...(file ? { file } : {}) }), {
          restore: false,
        });
      }
      return show(
        Object.freeze({
          number,
          tab: route.tab,
          ...(file ? { file } : {}),
          ...(route.jumped === true ? { jumped: true } : {}),
          ...(route.reader === undefined ? {} : { reader: route.reader }),
        }),
        { restore: false },
      );
    }

    /**
     * Apply a history landing that `pullHistoryAction` says is the page's.
     *
     * @param {string} pathname
     * @param {boolean} heldTarget
     */
    function onHistory(pathname, heldTarget) {
      const current = shown();
      const landing = pullHistoryAction(pathname, current ? current.number : null, heldTarget);
      if (landing?.action === "tab") {
        land(current?.handle ?? null, landing, true);
      } else if (landing?.action === "mount") {
        void show(
          Object.freeze({
            number: landing.number,
            tab: landing.tab,
            ...(landing.file ? { file: landing.file } : {}),
          }),
        );
      } else if (landing?.action === "stack") {
        void showStack(
          Object.freeze({
            number: landing.number,
            tab: landing.tab,
            ...(landing.file ? { file: landing.file } : {}),
          }),
        );
      } else if (landing?.action === "list") {
        void showList();
      }
      return landing;
    }

    /** The handle of the pull request's page holding the pane, or null: never a stack's. */
    function shownPage() {
      const current = shown();
      return current === null || typeof current.number !== "number" ? null : current.handle;
    }

    const host = Object.freeze({
      dispose,
      release,
      onHistory,
      open,
      /** The handle of the pull request's page holding the pane, for what sits beside it, or null. */
      page: shownPage,
      /**
       * The page of pull request *number* when it holds the pane, or null: what the Pulls
       * tab's changed files of that pull request jump in.
       *
       * @param {number} number
       */
      pageFor: (number) => (shown()?.number === number ? shownPage() : null),
      /** @param {number} number */
      stackFor(number) {
        const current = shown();
        return current !== null && current.number === stackKey(number) ? current.handle : null;
      },
      show,
      showList,
      showStack,
      shown: () => shown()?.number ?? null,
    });
    attached = host;
    notifyPage();
    return host;
  }

  /**
   * The host the shell made, which it makes once, for what sits beside the pane and cannot
   * reach the shell's own copy: the Pulls tab. Null until a pull-request route has opened.
   *
   * @type {{pageFor: (number: number) => unknown, stackFor: (number: number) => unknown} | null}
   */
  let attached = null;
  /** @type {Set<() => void>} */
  const pageListeners = new Set();
  function notifyPage() {
    for (const listener of pageListeners) {
      listener();
    }
  }

  /**
   * How the shell loads and renders a route-backed kind's view into the pane for a claim. Here
   * and not in the shell, as only an address in this space needs it.
   *
   * @param {{
   *   sdk: MetabrowserPublicSdk,
   *   isCurrent: (claim: number) => boolean,
   *   renderHtml: (html: string, claim: number) => unknown,
   *   renderNode: (node: HTMLElement, claim: number) => unknown,
   *   beginNavigation: (claim: number) => boolean,
   *   endNavigation: (claim: number) => void,
   *   stageNode: (node: HTMLElement, claim: number) => (() => void) | null,
   *   showLoadFailure: (claim: number, what: string) => void,
   * }} shell
   */
  function createViewMount(shell) {
    /**
     * @param {number} claim
     * @param {string} kind Both the kind and its view's id.
     * @param {Record<string, unknown>} context
     */
    return async (claim, kind, context) => {
      const { sdk } = shell;
      // Each kind says what it is: a pull request's page, a stack's, or the list at its address.
      const stack = kind === "pull-stack";
      const page = kind === "pull-request" || stack;
      const what = stack
        ? "stack pages"
        : page
          ? "pull-request pages"
          : "the list of pull requests";
      const failed = stack ? "the stack page" : page ? "the pull-request page" : what;
      let view = null;
      try {
        await sdk.ensureKindAssets(kind);
        view = sdk.getRegisteredView(kind, kind);
      } catch (error) {
        // Not the same as no plugin rendering such pages; the next route tries again.
        console.error(`metabrowser: ${what} could not load`, error);
        shell.showLoadFailure(claim, failed);
        return null;
      }
      if (!shell.isCurrent(claim)) {
        return null;
      }
      if (!view) {
        shell.renderHtml(`<div class="preview-empty">No plugin renders ${what} here.</div>`, claim);
        return null;
      }
      const host = document.createElement("div");
      host.className = `content-body ${kind}-host`;
      const retained = page && shell.beginNavigation(claim);
      const cleanupStage = retained ? shell.stageNode(host, claim) : null;
      if (!retained) {
        shell.renderNode(host, claim);
      }
      let instance;
      try {
        instance =
          /** @type {{setTab?: (tab: string) => void, land?: (route: {tab: string, file?: string}) => void, showFile?: (path: string) => unknown, flush?: () => void, ready?: Promise<void>, activate?: () => void, cancelPending?: () => void, dispose?: () => void}} */ (
            (await view.render(host, { kind, ...context })) ?? {}
          );
      } catch (error) {
        cleanupStage?.();
        shell.endNavigation(claim);
        if (shell.isCurrent(claim)) {
          shell.showLoadFailure(claim, failed);
        }
        console.error(`metabrowser: ${what} could not render`, error);
        return null;
      }
      let disposed = false;
      // Only a real cancellation capability promises that disposal can wait for handoff.
      const stop =
        typeof instance.cancelPending === "function"
          ? () => {
              host.inert = true;
              instance.cancelPending?.();
            }
          : undefined;
      const dispose = () => {
        if (disposed) {
          return;
        }
        disposed = true;
        cleanupStage?.();
        instance.dispose?.();
        shell.endNavigation(claim);
      };
      if (!shell.isCurrent(claim)) {
        dispose();
        return null;
      }
      const ready = Promise.resolve(instance.ready).then(
        () => {
          if (disposed || !shell.isCurrent(claim)) {
            return;
          }
          if (retained) {
            shell.renderNode(host, claim);
            cleanupStage?.();
          }
          instance.activate?.();
          shell.endNavigation(claim);
        },
        (error) => {
          dispose();
          if (shell.isCurrent(claim)) {
            shell.showLoadFailure(claim, failed);
          }
          console.error("metabrowser: pull-request readiness failed", error);
          throw error;
        },
      );
      return { ...instance, ready, cancelPending: stop, dispose };
    };
  }

  window.MetabrowserPullRoute = Object.freeze({
    /** @returns {{pageFor: (number: number) => unknown, stackFor: (number: number) => unknown} | null} */
    attachedHost: () => attached,
    /** A page became available, started replacement, or was disposed. @param {() => void} listener */
    onPageChange(listener) {
      pageListeners.add(listener);
      return () => pageListeners.delete(listener);
    },
    createPullPageHost,
    createViewMount,
    parsePull,
    parsePulls,
    parseStack,
    pullHistoryAction,
    pullHref,
    pullsHref,
    stackHref,
  });
})();
