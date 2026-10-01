// The pull-request page's routes and its host.
//
// `/pull/<n>[/files]` is the served pull request's address space (Browser URL Grammar).
// Only a server that serves a pull request has such a page, and only an address under
// `/pull/` reaches this code, so it is not a startup script: it is the `pull-route`
// on-demand bundle, which the shell starts fetching as it loads when the address is
// one, and waits for before it applies that address.
//
// Measured 2026-10-01: in navigation.js, a startup script, this was 1,818 of 13,265
// compressed bytes on every folder's page. See
// explorations/performance-loop/experiments/exp-037.

(() => {
  const PULL_PREFIX = "/pull/";
  // Keep aligned with view_routes._PULL_NUMBER and PULL_ROUTE_TABS.
  const PULL_NUMBER_PATTERN = /^[1-9][0-9]{0,9}$/;
  const PULL_TABS = Object.freeze(["", "files"]);

  /**
   * Encode the served pull request's page: `/pull/<n>` for its conversation,
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
   * What the shell does when history lands on *pathname*. Pure.
   *
   * *shown* is the pull request whose page holds the pane, or null, and *heldTarget*
   * whether the navigation controller holds a `/view/` target. A pull-request route is
   * no target, so the controller applies a landing on one only when it held a target
   * before, and then mounts the page itself. Otherwise -- back and forward between a
   * page's tabs, or onto an entry a commit replaced while the page was shown -- this
   * route decides: the page shown for the same number switches its tab, and anything
   * else mounts the page.
   *
   * @param {string} pathname
   * @param {number | null} shown
   * @param {boolean} heldTarget
   * @returns {Readonly<{action: "tab", tab: string} | {action: "mount", number: number, tab: string}> | null}
   */
  function pullHistoryAction(pathname, shown, heldTarget) {
    const route = parsePull(pathname);
    if (route === null || heldTarget) {
      return null;
    }
    return route.number === shown
      ? Object.freeze({ action: "tab", tab: route.tab })
      : Object.freeze({ action: "mount", number: route.number, tab: route.tab });
  }

  /**
   * The shell's host for the served pull request's page. It decides what a
   * `/pull/<n>[/files]` route does to the pane -- switch the shown page's tab, or claim
   * the pane and mount a page -- keeps the page's tab in the URL, and disposes a render
   * a later claim superseded. The shell supplies the pane and the history; nothing here
   * touches the DOM.
   *
   * *claim* claims the pane and returns its token; the shell's claim calls `dispose`, so
   * whatever claims the pane next replaces the page. *mount* loads and renders the page
   * for a claim and resolves to its handle, or to null when nothing was mounted (the
   * claim was superseded, or no plugin renders the page); the page gets `open` to move
   * to a tab or to another pull request's page.
   *
   * @template {{setTab?: (tab: string) => void, dispose?: () => void}} Handle
   * @param {{
   *   claim: () => number,
   *   isCurrent: (claim: number) => boolean,
   *   mount: (
   *     claim: number,
   *     route: Readonly<{number: number, tab: string}>,
   *     open: (route: {number: number, tab: string}) => Promise<{status: string}>,
   *   ) => Promise<Handle | null | undefined>,
   *   pathname: () => string,
   *   pushHref: (href: string) => void,
   * }} deps
   */
  function createPullPageHost(deps) {
    /** @type {{number: number, claim: number, handle: Handle | null} | null} */
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
     * Show a route's page, or switch its tab when that page is already shown.
     *
     * @param {Readonly<{number: number, tab: string}>} route
     * @returns {Promise<{status: "opened" | "cancelled"}>}
     */
    async function show(route) {
      const current = shown();
      if (current !== null && current.number === route.number) {
        current.handle?.setTab?.(route.tab);
        return { status: "opened" };
      }
      const claim = deps.claim();
      /** @type {NonNullable<typeof page>} */
      const mine = { number: route.number, claim, handle: null };
      page = mine;
      const handle = await deps.mount(claim, route, open);
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
     * Go to a page's tab or another pull request's page. A tab is a selection within
     * the page, so it owns the URL (Browser URL Grammar) and back and forward move
     * between tabs.
     *
     * @param {{number: number, tab: string}} route
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
        deps.pushHref(href);
      }
      return show(Object.freeze({ number, tab: route.tab }));
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
      }
      return landing;
    }

    return Object.freeze({
      dispose,
      onHistory,
      open,
      show,
      shown: () => shown()?.number ?? null,
    });
  }

  window.MetabrowserPullRoute = Object.freeze({
    createPullPageHost,
    parsePull,
    pullHistoryAction,
    pullHref,
  });
})();
