// The pull-request page's routes and its host.
//
// A pull request's page is the view a plugin registers for the `pull-request` kind, the
// GitHub plugin's, and the list's is the same for `pull-request-list`. The host here decides
// what a route does -- switch the shown page's tab or mount a page -- and keeps the tab in the
// URL; the shell supplies the pane, this loads that plugin, and the view gets the host's `open`.
// The view owns everything else: fetching the record, polling, refreshing, and Files changed.
//
// `/pull/<n>[/files]` and `/pulls` are the pull requests' address space (Browser URL
// Grammar). Only such an address, or the Pulls tab, reaches this code, so it is no startup
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
  const PULL_TABS = Object.freeze(["", "files"]);
  // Keep aligned with view_routes.PULLS_ROUTE and cache.paths.PULL_LIST_NAMES.
  const PULLS_PATH = "/pulls";
  const PULL_LISTS = Object.freeze(["all", "open", "closed"]);

  /**
   * Encode a pull request's page: `/pull/<n>` for its conversation,
   * `/pull/<n>/files` for its Files changed.
   *
   * @param {number} number
   * @param {string} [tab]
   * @returns {string}
   */
  function pullHref(number, tab = "") {
    if (!PULL_NUMBER_PATTERN.test(String(number)) || !PULL_TABS.includes(tab)) {
      throw new TypeError("pull route requires a pull-request number and a known tab");
    }
    return `${PULL_PREFIX}${number}${tab ? `/${tab}` : ""}`;
  }

  /**
   * Parse a pull-request page route, or null when the location is not one.
   *
   * @param {string} pathname
   * @returns {Readonly<{number: number, tab: string}> | null}
   */
  function parsePull(pathname) {
    if (typeof pathname !== "string" || !pathname.startsWith(PULL_PREFIX)) {
      return null;
    }
    const segments = pathname.slice(PULL_PREFIX.length).split("/");
    if (segments.length > 1 && segments[segments.length - 1] === "") {
      segments.pop();
    }
    const [number, tab = ""] = segments;
    if (
      segments.length > 2 ||
      !PULL_NUMBER_PATTERN.test(number) ||
      !PULL_TABS.includes(tab) ||
      (segments.length === 2 && !tab)
    ) {
      return null;
    }
    return Object.freeze({ number: Number(number), tab });
  }

  /**
   * The list's address: `/pulls` for all of them and `/pulls?state=<list>` for a filter.
   *
   * @param {string} [state]
   * @returns {string}
   */
  function pullsHref(state = "all") {
    if (!PULL_LISTS.includes(state)) {
      throw new TypeError("pulls route requires a list of pull requests");
    }
    return state === "all" ? PULLS_PATH : `${PULLS_PATH}?state=${state}`;
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
    return Object.freeze({ state: state !== null && PULL_LISTS.includes(state) ? state : "all" });
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
   * @param {string} pathname
   * @param {number | "list" | null} shown
   * @param {boolean} heldTarget
   * @returns {Readonly<{action: "tab", tab: string} | {action: "mount", number: number, tab: string} | {action: "list"}> | null}
   */
  function pullHistoryAction(pathname, shown, heldTarget) {
    if (heldTarget) {
      return null;
    }
    if (parsePulls(pathname) !== null) {
      return shown === "list" ? null : Object.freeze({ action: "list" });
    }
    const route = parsePull(pathname);
    if (route === null) {
      return null;
    }
    return route.number === shown
      ? Object.freeze({ action: "tab", tab: route.tab })
      : Object.freeze({ action: "mount", number: route.number, tab: route.tab });
  }

  /**
   * The shell's host for a pull request's page. It decides what a
   * `/pull/<n>[/files]` route does to the pane -- switch the shown page's tab, or claim
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
   * @template {{setTab?: (tab: string) => void, flush?: () => void, dispose?: () => void}} Handle
   * @param {{
   *   claim: () => number,
   *   isCurrent: (claim: number) => boolean,
   *   mount: (
   *     claim: number,
   *     route: Readonly<{number: number, tab: string, reader?: unknown}>,
   *     open: (route: {number: number, tab: string, reader?: unknown, replace?: boolean}) => Promise<{status: string}>,
   *   ) => Promise<Handle | null | undefined>,
   *   mountList: (claim: number) => Promise<Handle | null | undefined>,
   *   pathname: () => string,
   *   pushHref: (href: string) => void,
   *   replaceHref: (href: string) => void,
   * }} deps
   */
  function createPullPageHost(deps) {
    /** @type {{number: number | "list", claim: number, handle: Handle | null} | null} */
    let page = null;

    // The page that holds the pane, or null once anything else claimed it or while it
    // is still mounting.
    function shown() {
      return page !== null && page.handle !== null && deps.isCurrent(page.claim) ? page : null;
    }

    function dispose() {
      const held = page;
      page = null;
      try {
        held?.handle?.dispose?.();
      } catch (error) {
        console.error("pull-request page dispose error:", error);
      }
    }

    /**
     * Claim the pane for a page and mount it.
     *
     * @param {number | "list"} number
     * @param {(claim: number) => Promise<Handle | null | undefined>} mount
     * @returns {Promise<{status: "opened" | "cancelled"}>}
     */
    async function take(number, mount) {
      const claim = deps.claim();
      /** @type {NonNullable<typeof page>} */
      const mine = { number, claim, handle: null };
      page = mine;
      const handle = await mount(claim);
      if (page !== mine || !deps.isCurrent(claim)) {
        handle?.dispose?.();
        return { status: "cancelled" };
      }
      if (!handle) {
        // Nothing holds the pane, so the next route to this page mounts it again.
        page = null;
        return { status: "opened" };
      }
      mine.handle = handle;
      return { status: "opened" };
    }

    /**
     * Show a route's page, or switch its tab when that page is already shown.
     *
     * @param {Readonly<{number: number, tab: string, reader?: unknown}>} route
     * @returns {Promise<{status: "opened" | "cancelled"}>}
     */
    async function show(route) {
      const current = shown();
      if (current !== null && current.number === route.number) {
        current.handle?.setTab?.(route.tab);
        return { status: "opened" };
      }
      return take(route.number, (claim) => deps.mount(claim, route, open));
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
     * them with one Back. A click, Enter, and the page's own links push.
     *
     * @param {{number: number, tab: string, reader?: unknown, replace?: boolean}} route
     */
    function open(route) {
      const number = Number(route.number);
      let href;
      try {
        href = pullHref(number, route.tab);
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
      return show(
        Object.freeze({
          number,
          tab: route.tab,
          ...(route.reader === undefined ? {} : { reader: route.reader }),
        }),
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
        current?.handle?.setTab?.(landing.tab);
      } else if (landing?.action === "mount") {
        void show(Object.freeze({ number: landing.number, tab: landing.tab }));
      } else if (landing?.action === "list") {
        void showList();
      }
      return landing;
    }

    return Object.freeze({
      dispose,
      onHistory,
      open,
      /** The handle of the pull request's page holding the pane, for what sits beside it, or null. */
      page: () => {
        const current = shown();
        return current === null || current.number === "list" ? null : current.handle;
      },
      show,
      showList,
      shown: () => shown()?.number ?? null,
    });
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
      // Each kind says what it is: a pull request's page, or the list at its address.
      const page = kind === "pull-request";
      const what = page ? "pull-request pages" : "the list of pull requests";
      let view = null;
      try {
        await sdk.ensureKindAssets(kind);
        view = sdk.getRegisteredView(kind, kind);
      } catch (error) {
        // Not the same as no plugin rendering such pages; the next route tries again.
        console.error(`metabrowser: ${what} could not load`, error);
        shell.showLoadFailure(claim, page ? "the pull-request page" : what);
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
      shell.renderNode(host, claim);
      return /** @type {{setTab?: (tab: string) => void, flush?: () => void, dispose?: () => void} | null} */ (
        await view.render(host, { kind, ...context })
      );
    };
  }

  window.MetabrowserPullRoute = Object.freeze({
    createPullPageHost,
    createViewMount,
    parsePull,
    parsePulls,
    pullHistoryAction,
    pullHref,
    pullsHref,
  });
})();
