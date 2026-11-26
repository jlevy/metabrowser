// Deferred shell controller for the Files, Pulls, and Commits tabs, and for going home
// from the folder's name above them, or by `0`.
(() => {
  // In tab order, each with its letter: F for Files, P for Pulls, H for commit History.
  // The letters name what each tab holds and mean the same wherever they are pressed
  // (docs/design-system.md, "Keyboard Shortcuts").
  const MAIN_TABS = [
    { id: "files", label: "Files", key: "f" },
    { id: "pulls", label: "Pulls", key: "p" },
    { id: "git", label: "Commits", key: "h" },
  ];

  // The bare letter alone, as every shortcut is: Shift changes nothing.
  /** @param {string} key @returns {Parameters<Window["MetabrowserKeyboardShortcuts"]["describeBindings"]>[0]} */
  function tabBindings(key) {
    return [{ key }];
  }

  // How the reader reached what the address names (docs/design-system.md, "Navigation
  // Reveals the Item"): an open in the page (Quick Search, a link, a key, the address
  // bar's crumbs), the page loading at an address, Back or Forward, a row of the
  // navigation itself, a tab's button or letter returning to the tab's destination, or a
  // step within the item shown, such as a fragment.
  /** @type {readonly MetabrowserRevealRoute[]} */
  const REVEAL_ROUTES = Object.freeze(["open", "address", "history", "nav", "tab", "step"]);

  /**
   * The main tab that holds what an address names: Files for a file or folder, Commits
   * for a commit or the neutral Commits entry, Pulls for a pull request or the list; null
   * for an address no tab holds.
   *
   * @param {{pathname: string, search: string, hash: string}} address
   * @param {{routes: Window["MetabrowserNavigationRoute"], isPullAddress: (pathname: string) => boolean, gitLanding: boolean}} how
   * @returns {string | null}
   */
  function tabAtAddress(address, how) {
    if (how.gitLanding) {
      return "git";
    }
    const { pathname, search, hash } = address;
    if (how.routes.parse(pathname, search, hash)) {
      return "files";
    }
    if (how.routes.parseCommit(pathname)) {
      return "git";
    }
    return how.isPullAddress(pathname) ? "pulls" : null;
  }

  /**
   * The one rule for showing what an address names in the navigation pane: its tab comes
   * to the front, and its panel opens the folders or stack that hold it, selects it, and
   * scrolls it into view. Two routes differ. A tab's button or letter returns to the
   * tab's destination with the panel as the reader left it, so its scroll is kept. A step
   * within the item shown reveals nothing. No route moves focus: the panel selects, and
   * focus stays where the reader is reading.
   *
   * @param {string | null} tab The tab that holds the item, `tabAtAddress`.
   * @param {MetabrowserRevealRoute} route
   * @param {string} active The tab in front.
   * @returns {Readonly<{tab: string | null, switches: boolean, reveal: boolean, scroll: "nearest" | "keep"}>}
   */
  function revealPlan(tab, route, active) {
    if (!REVEAL_ROUTES.includes(route)) {
      throw new TypeError(`unknown reveal route: ${route}`);
    }
    if (tab === null) {
      return Object.freeze({ tab: null, switches: false, reveal: false, scroll: "keep" });
    }
    const keeps = route === "tab" || route === "step";
    return Object.freeze({
      tab,
      switches: tab !== active,
      reveal: route !== "step",
      scroll: keeps ? "keep" : "nearest",
    });
  }

  /**
   * The route of a Files landing the navigation controller applies, from its source and
   * the landing a tab switch or a history step began, if one did. An open in the page is
   * the reader's own, whatever landing came before it.
   *
   * @param {"startup" | "user" | "popstate"} source
   * @param {MetabrowserRevealRoute | null} pending
   * @returns {MetabrowserRevealRoute}
   */
  function landingRouteFor(source, pending) {
    if (source === "user") {
      return "open";
    }
    return pending ?? (source === "startup" ? "address" : "history");
  }

  /** @param {MetabrowserMainTabsDeps} deps */
  function create(deps) {
    const navBar = document.querySelector(".nav-tab-bar");
    /** @type {MetabrowserNavPanel[]} */
    let navPanels = [
      // Files is the server-rendered panel, so its focus hook is the shell's tree.
      {
        id: "files",
        label: "Files",
        focusRow: () => deps.focusFilesRow(),
        onFirstShow: null,
        onShow: () => deps.filesShown(),
        onHide: () => deps.filesHidden(),
        reveal: (how) => deps.revealFile(how),
        home: () => deps.resetFiles(),
      },
    ];
    /** @type {Set<string>} */
    const navPanelsShown = new Set(["files"]);
    /** The panel in front, and where each panel was scrolled to: they share one scroller. */
    let activeNavPanelId =
      navBar?.querySelector(".tab-btn.active")?.getAttribute("data-tab") ?? "files";
    /** @type {Map<string, number>} */
    const navPanelScroll = new Map();
    /** @type {Map<string, {href: string, state: unknown}>} */
    const mainTabDestinations = new Map();
    // The route of a Files landing a tab switch or a history step began: the navigation
    // controller applies it a task later, and reads it then (`landingRouteFor`).
    /** @type {MetabrowserRevealRoute | null} */
    let filesLandingRoute = null;
    let gitDiscoveryFinished = false;

    /** @param {string} panelId */
    function tabButton(panelId) {
      return /** @type {HTMLElement | null} */ (
        navBar?.querySelector(`.tab-btn[data-tab="${panelId}"]`) ?? null
      );
    }

    /** The registry the letters are bound to, and each present tab button's target in it.
     * None between a real `pagehide`, which disposes the registry, and the `pageshow`
     * that builds the next one, so a panel registered then gets its tab and no target.
     * @type {ReturnType<Window["MetabrowserKeyboardShortcuts"]["create"]> | null} */
    let boundShortcuts = null;
    /** @type {Map<string, ReturnType<ReturnType<Window["MetabrowserKeyboardShortcuts"]["create"]>["attachTarget"]>>} */
    const tabTargets = new Map();

    /**
     * Make a tab button its letter's target, which gives it the letter's
     * `aria-keyshortcuts` and, while Shift is held, its badge. A tab that is absent has
     * no target, so its letter stays reserved and does nothing.
     *
     * @param {string} panelId
     */
    function attachTabTarget(panelId) {
      const button = tabButton(panelId);
      if (!boundShortcuts || !button || !MAIN_TABS.some(({ id }) => id === panelId)) {
        return;
      }
      const attached = tabTargets.get(panelId);
      if (attached) {
        attached.retarget(button);
      } else {
        tabTargets.set(panelId, boundShortcuts.attachTarget(`main-tabs.${panelId}`, button));
      }
    }

    /**
     * Bind the letters to `shortcuts`, or to none: the shell passes `null` as it disposes
     * the registry, so nothing attaches to a disposed one.
     *
     * @param {ReturnType<Window["MetabrowserKeyboardShortcuts"]["create"]> | null} shortcuts
     */
    function bindShortcuts(shortcuts) {
      // A rebuilt registry starts with no targets; the old handles belonged to the one
      // a real pagehide disposed.
      boundShortcuts = shortcuts;
      tabTargets.clear();
      if (!shortcuts) {
        return;
      }
      for (const [index, { id, label, key }] of MAIN_TABS.entries()) {
        const action = `Open ${label}`;
        const bindings = tabBindings(key);
        shortcuts.register({
          id: `main-tabs.${id}`,
          group: "main-tabs",
          scope: "global",
          order: index + 1,
          bindings,
          copy: { action, description: `Switch to the ${label} tab when available.`, hint: label },
          surfaces: { help: "always", reveal: "always" },
          targeted: true,
          handler() {
            // The tab's own path, then its panel's row, so `F` then `↓` walks the tree;
            // the tab button keeps focus while the panel has no rows yet. A letter for
            // the tab already shown only moves focus.
            openMainTab(id);
            const panel = navPanels.find((candidate) => candidate.id === id);
            if (!panel?.focusRow?.()) {
              tabButton(id)?.focus();
            }
            return true;
          },
        });
        attachTabTarget(id);
      }
    }

    // Commits, asked for before Git discovery registered it: the server draws the tab at
    // first paint, about 50 to 100 ms before discovery, and a click or its shortcut there
    // did nothing. It opens on registration, unless discovery removes it.
    let gitOpenPending = false;

    /** @param {MetabrowserNavPanel} panel */
    function registerNavPanel(panel) {
      if (navPanels.some((existing) => existing.id === panel.id)) {
        return;
      }
      navPanels.push(panel);
      ensureNavPanelElements(panel);
      if (panel.id === "git" && gitOpenPending) {
        gitOpenPending = false;
        // After the panel's own registration has finished wiring it.
        void Promise.resolve().then(() => openMainTab("git"));
      }
    }

    // Create the button and container for a panel that was not in the
    // server-rendered markup, then make the button its letter's target. Idempotent, so
    // a re-registration after a root change does not duplicate the tab. Both elements
    // exist before the registry is reached, so the tab works whether or not one is bound.
    /** @param {MetabrowserNavPanel} panel */
    function ensureNavPanelElements(panel) {
      const content = document.getElementById("tree-content");
      if (!navBar || !content) {
        return;
      }
      const created = !tabButton(panel.id);
      if (created) {
        const btn = document.createElement("button");
        btn.className = "tab-btn";
        btn.type = "button";
        btn.setAttribute("role", "tab");
        btn.setAttribute("aria-selected", "false");
        btn.dataset.tab = panel.id;
        btn.textContent = panel.label;
        // In MAIN_TABS order, before the first later tab already drawn: the server shell
        // draws Pulls at first paint, and Commits arrives after it, once Git discovery
        // finishes.
        const at = MAIN_TABS.findIndex(({ id }) => id === panel.id);
        const later = at < 0 ? [] : MAIN_TABS.slice(at + 1);
        navBar.insertBefore(btn, later.map(({ id }) => tabButton(id)).find(Boolean) ?? null);
      }
      // A panel the server did not draw gets its toolbar too, empty until it fills it.
      if (!document.querySelector(`[data-nav-toolbar="${panel.id}"]`)) {
        const toolbar = document.createElement("div");
        toolbar.className = "nav-toolbar";
        toolbar.id = `nav-toolbar-${panel.id}`;
        toolbar.dataset.navToolbar = panel.id;
        toolbar.hidden = true;
        content.before(toolbar);
      }
      if (!content.querySelector(`[data-tab-content="${panel.id}"]`)) {
        const container = document.createElement("div");
        container.id = `tab-${panel.id}`;
        container.dataset.tabContent = panel.id;
        container.style.display = "none";
        content.appendChild(container);
      }
      if (created) {
        attachTabTarget(panel.id);
      }
    }

    /** @param {string} panelId */
    function removeNavPanel(panelId) {
      navPanels = navPanels.filter((panel) => panel.id !== panelId);
      navPanelsShown.delete(panelId);
      if (panelId === "git") {
        gitOpenPending = false;
      }
      const button = tabButton(panelId);
      const container = document
        .getElementById("tree-content")
        ?.querySelector(`[data-tab-content="${panelId}"]`);
      const wasActive = button?.classList.contains("active");
      tabTargets.get(panelId)?.detach();
      tabTargets.delete(panelId);
      button?.remove();
      container?.remove();
      // Its toolbar goes with it, or the hidden slot keeps the last tally.
      document.getElementById(`nav-toolbar-${panelId}`)?.remove();
      // Never leave the nav with no active tab: if the panel being removed
      // was the visible one, fall back to Files.
      if (wasActive) {
        activateNavPanel("files");
        if (panelId === "git" && deps.isGitHistoryLanding()) {
          void restoreNeutralGitPanel().catch((error) => {
            console.error("Could not restore Files after Git discovery failed", error);
          });
        }
      }
    }

    function hasGitPanel() {
      return navPanels.some((panel) => panel.id === "git");
    }

    async function restoreNeutralGitPanel() {
      if (!deps.isGitHistoryLanding()) {
        return;
      }
      if (hasGitPanel()) {
        activateNavPanel("git");
        return;
      }
      // Git discovery can fail between saving a history entry and reloading it.
      const state = { ...window.history.state };
      delete state.gitLanding;
      window.history.replaceState(state, "", "/view/");
      await deps.restore();
    }

    function mainTabAtAddress() {
      return tabAtAddress(window.location, {
        routes: window.MetabrowserNavigationRoute,
        isPullAddress: deps.isPullAddress,
        gitLanding: deps.isGitHistoryLanding(),
      });
    }

    // Files and Pulls return to what they last showed. Commits keeps no destination: a
    // switch to it always lands on the newest commit (openMainTab).
    function rememberMainTabAddress() {
      const panel = mainTabAtAddress();
      if (panel && panel !== "git") {
        const { pathname, search, hash } = window.location;
        mainTabDestinations.set(panel, {
          href: `${pathname}${search}${hash}`,
          state: window.history.state,
        });
      }
    }

    /**
     * A tab switch or a history step lands on *panelId*. A tab's own landing keeps the
     * panel's saved scroll; Back and Forward reveal the item the address names, as any
     * other route does (`revealPlan`).
     *
     * @param {string} panelId The panel whose route is landing.
     * @param {"tab" | "history"} route
     */
    function markMainTabLanding(panelId, route) {
      const scroll = navPanelScroll.get(panelId);
      const keep = revealPlan(panelId, route, activeNavPanelId).scroll === "keep";
      const keepSaved = keep && scroll !== undefined;
      // A first visit has no scroll to keep: it opens the tab's default destination.
      filesLandingRoute =
        panelId === "files" ? (keepSaved ? "tab" : route === "tab" ? "open" : route) : null;
      activateNavPanel(panelId);
      if (panelId === "pulls") {
        const scroller = document.getElementById("tree-content");
        const shown = scroller?.scrollTop;
        window.MetabrowserPullsNav?.routeChanged({ preserveScroll: keepSaved });
        if (scroller && keepSaved && scroller.scrollTop !== shown) {
          // Marking the selected PR can reveal its row over the panel's saved scroll, so a
          // scroll the marking moved is put back. One it did not move is left alone: the
          // saved scroll is already back (`activateNavPanel`), and the panel, shown, has kept
          // the row a reveal placed in view from it (pulls-panel.js, `keptPlace`). Set again
          // over that, it moved the list from under the row wherever the rows stood at other
          // heights than when it was saved, as stacks read while the reader was away regroup
          // them, and the panel, taking it for the reader's scroll, let the row go out of view.
          scroller.scrollTop = /** @type {number} */ (scroll);
        }
      }
    }

    /** @param {string} panelId A click on one of the main navigation tabs. */
    function openMainTab(panelId) {
      // A press on another tab replaces a pending Commits press.
      if (panelId !== "git") {
        gitOpenPending = false;
      }
      if (panelId === activeNavPanelId) {
        return;
      }
      // The server draws Commits for a repository before Git discovery registers it.
      if (panelId === "git" && !hasGitPanel()) {
        gitOpenPending = true;
        return;
      }
      deps.flushPull();
      rememberMainTabAddress();
      const saved = mainTabDestinations.get(panelId);
      if (panelId === mainTabAtAddress()) {
        activateNavPanel(panelId);
        return;
      }
      const href = saved?.href ?? (panelId === "pulls" ? "/pulls" : "/view/");
      // A switch to Commits names no commit, so it pushes the neutral history entry, which
      // has no route of its own, and the Git panel selects the newest commit there,
      // replacing the entry with that commit's address (git-panel.js, landOnNewestCommit).
      // The newest commit is the top row, so the panel starts from its top.
      const state = panelId === "git" ? { gitLanding: true } : (saved?.state ?? null);
      if (panelId === "git") {
        navPanelScroll.delete("git");
      }
      land(panelId, href, state, () => markMainTabLanding(panelId, "tab"));
    }

    /**
     * Open an address that Pulls or Commits holds, in place, as a link in a text names it
     * (the SDK's `navigation.openRoute`): a pull request's page, one of its tabs or changed
     * files, a stack's page, the list, or a commit. It is the reader's open of that address,
     * so it pushes an entry, its tab comes to the front and its panel reveals the item, as
     * any open does (`revealPlan`), and the pane shows it as it shows a tab's destination
     * (`openMainTab`). A pull request's page that holds the pane writes its place into its
     * own entry first.
     *
     * It answers whether it opened the address, and opens nothing for an address it cannot
     * show in place: a file's, which `navigation.open` opens; one on another origin, or no
     * tab's; a pull request's that the routes do not read, or before they have loaded; and
     * a commit before the Commits tab is here. The browser then follows the link.
     *
     * @param {string} href
     * @returns {boolean}
     */
    function openRoute(href) {
      const routes = window.MetabrowserNavigationRoute;
      const pulls = window.MetabrowserPullRoute;
      let address;
      try {
        const here = new URL(window.location.href);
        address = new URL(href, here);
        if (address.origin !== here.origin) {
          return false;
        }
      } catch {
        return false;
      }
      const { pathname, search, hash } = address;
      const panelId = tabAtAddress(address, {
        routes,
        isPullAddress: deps.isPullAddress,
        gitLanding: false,
      });
      // An address in the pull requests' space that names a page or the list, as the pane
      // shows them (app.js, applyNavigationTarget); a stack's page is in that space too.
      const pullPage =
        pulls !== undefined &&
        (pulls.parsePull(pathname) ?? pulls.parseStack(pathname) ?? pulls.parsePulls(pathname)) !==
          null;
      const opens = panelId === "git" ? hasGitPanel() : panelId === "pulls" && pullPage;
      if (panelId === null || !opens || !tabButton(panelId)) {
        return false;
      }
      gitOpenPending = false;
      deps.flushPull();
      rememberMainTabAddress();
      land(panelId, `${pathname}${search}${hash}`, null, () => {
        void revealAtAddress("open").catch((error) => {
          console.error("Could not reveal the opened address", error);
        });
      });
      return true;
    }

    /**
     * Push *href*, an address *panelId* holds, and apply it: *show* brings the panel to the
     * front, the shell shows what the address names in the pane, and the Commits panel
     * selects the commit it names. A switch of tab takes the pane from what the tab it
     * leaves showed, as Back's does (`onHistory`); within one tab, what the address names
     * claims the pane as it shows, so a pull request's page shown lands on another of its
     * tabs in place.
     *
     * @param {string} panelId
     * @param {string} href
     * @param {unknown} state
     * @param {() => void} show
     */
    function land(panelId, href, state, show) {
      if (panelId !== activeNavPanelId) {
        deps.cancelPreview();
      }
      window.history.pushState(state, "", href);
      rememberMainTabAddress();
      show();
      if (panelId !== "pulls") {
        window.MetabrowserPullsNav?.routeChanged();
      }
      void deps.restore().catch((error) => {
        console.error("Could not restore main navigation tab", error);
      });
      if (panelId === "git") {
        void window.MetabrowserGitPanel?.restoreCommitLanding();
      }
    }

    /** @param {string} panelId */
    function activateNavPanel(panelId) {
      if (
        !navBar ||
        !tabButton(panelId) ||
        (panelId === activeNavPanelId && navPanelsShown.has(panelId))
      ) {
        return;
      }
      // Mark the panel and restore its scroll. The route's producer owns the preview.
      var leaving = activeNavPanelId;
      var scroller = document.getElementById("tree-content");
      if (leaving !== panelId && scroller) {
        navPanelScroll.set(leaving, scroller.scrollTop);
      }
      activeNavPanelId = panelId;
      navBar.querySelectorAll(".tab-btn").forEach((element) => {
        const btn = /** @type {HTMLElement} */ (element);
        const selected = btn.dataset.tab === panelId;
        btn.classList.toggle("active", selected);
        btn.setAttribute("aria-selected", selected ? "true" : "false");
      });
      scroller?.querySelectorAll("[data-tab-content]").forEach((element) => {
        const panel = /** @type {HTMLElement} */ (element);
        panel.style.display = panel.dataset.tabContent === panelId ? "" : "none";
      });
      // The filter bar is chrome for the file tree, and it sits outside the
      // tab containers on purpose — a tree reload replaces #tab-files
      // wholesale, and the bar has to survive that and stay put while the
      // tree scrolls. Being outside means the loop above does not reach it,
      // so a panel that is not Files would otherwise keep a bar of file
      // filters on screen above content they cannot filter. The bar is the
      // Files tab's toolbar in one slot every tab fills with its own, at one
      // height while each is one line, so the panel below starts at one y on
      // every tab. A toolbar its pane is too narrow for wraps instead of
      // scrolling (docs/design-system.md, "Navigation Toolbars Wrap").
      for (const toolbar of document.querySelectorAll("[data-nav-toolbar]")) {
        const slot = /** @type {HTMLElement} */ (toolbar);
        slot.hidden = slot.dataset.navToolbar !== panelId;
      }
      // The served revision's row heads the two tabs that show it, Files and Commits, and
      // hides under Pulls, which has its own scope. It is one row with one chooser, so a
      // choice made under either tab is what both show (docs/design-system.md, "The Ref
      // Selector"). Its list closes on a switch, as each tab's own menus do.
      const sourceRow = document.getElementById("nav-source-ref");
      if (sourceRow) {
        sourceRow.hidden = panelId !== "files" && panelId !== "git";
      }
      if (leaving !== panelId) {
        window.MetabrowserSourceRefSelector?.mounted()?.close();
      }
      if (leaving !== panelId && scroller) {
        scroller.scrollTop = navPanelScroll.get(panelId) ?? 0;
        navPanels.find((candidate) => candidate.id === leaving)?.onHide?.();
      }
      // Hiding or restoring the bar changes which chrome the scroll shadow
      // belongs to, and no scroll event fires on a tab switch.
      deps.scrollShadow();

      const panel = navPanels.find((candidate) => candidate.id === panelId);
      if (panel && !navPanelsShown.has(panelId)) {
        navPanelsShown.add(panelId);
        panel?.onFirstShow?.();
      }
      panel?.onShow?.();
    }

    /**
     * Home: the served folder's home view, as a fresh load of `/view/` shows it
     * (docs/design-system.md, "Home"). The folder's name at the top of the nav and `0` come
     * here, from whichever tab is in front. Every tab forgets where it was, as a page that
     * has just loaded knows nowhere: Files and Pulls their destinations, and every panel
     * its scroll, so Files shows the top of its panel, Pulls next opens its list, a pull
     * request opened from it opens on Conversation, and Commits lands on its newest commit
     * as it always does. Every panel then puts back what a fresh load draws in it, by its
     * own `home`: Files its filters and tree, and Pulls its stacks, its rows' changed
     * files, and its Tab stop. The shell then opens the root at its default view.
     *
     * It is the reader's own open of `/view/`, so it pushes one history entry, none when
     * Files already shows the root at `/view/`, and Back returns to where the reader was:
     * a pull request's page writes its place into its entry first.
     *
     * @returns {Promise<unknown>}
     */
    function goHome() {
      deps.flushPull();
      gitOpenPending = false;
      mainTabDestinations.clear();
      navPanelScroll.clear();
      for (const panel of navPanels) {
        panel.home?.();
      }
      // The panels share one scroller, and the switch to Files keeps the offset of the
      // panel it leaves: at its top, that panel keeps none of the reader's either.
      const scroller = document.getElementById("tree-content");
      if (scroller) {
        scroller.scrollTop = 0;
      }
      return deps.openHome();
    }

    /**
     * Show what the address names in the navigation pane, by the one rule (`revealPlan`):
     * bring its tab to the front and have that tab's panel reveal it. Every route to an
     * item comes here: a file's landing (app.js, applyNavigationTarget), a pull request's
     * open and its rows' skim (app.js, revealPullAddress), and Quick Search. A commit's
     * address is the Git panel's own landing (git-panel.js, restoreCommitLanding), which
     * pages its history before it can reveal the row.
     *
     * *again* says the reader opened the item already shown again, as Quick Search for the
     * file or pull request shown does. It belongs to this call, and nothing keeps it: the
     * panel reveals the item although the address names what it already shows, where a
     * step within that item reveals nothing.
     *
     * @param {MetabrowserRevealRoute} route
     * @param {{isCurrent?: () => boolean, again?: boolean}} [how]
     * @returns {Promise<void>}
     */
    async function revealAtAddress(route, how = {}) {
      const plan = revealPlan(mainTabAtAddress(), route, activeNavPanelId);
      if (plan.tab === null) {
        return;
      }
      if (plan.switches) {
        // A file claims the pane itself; what another tab showed there goes now, as a
        // tab click's does. A pull request's page claims it as it opens.
        if (plan.tab === "files") {
          deps.cancelPreview();
        }
        activateNavPanel(plan.tab);
      }
      const panel = navPanels.find((candidate) => candidate.id === plan.tab);
      if (!plan.reveal || !panel?.reveal) {
        return;
      }
      await panel.reveal({
        scroll: plan.scroll,
        isCurrent: how.isCurrent ?? (() => true),
        again: how.again === true,
      });
    }

    function onHistory() {
      if (gitDiscoveryFinished && deps.isGitHistoryLanding() && !hasGitPanel()) {
        void restoreNeutralGitPanel().catch(console.error);
        return;
      }
      const panel = mainTabAtAddress();
      const switched = panel !== null && panel !== activeNavPanelId;
      if (switched) {
        deps.cancelPreview();
        markMainTabLanding(panel, "history");
      }
      rememberMainTabAddress();
      // The Files root and neutral Git history share a path.
      if (deps.isGitHistoryLanding() || (switched && panel === "files")) {
        void deps.restore().catch(console.error);
      }
    }

    rememberMainTabAddress();
    const initial = mainTabAtAddress();
    if (initial !== null && !deps.isGitHistoryLanding()) {
      activateNavPanel(initial);
    }
    const controller = Object.freeze({
      active: () => activeNavPanelId,
      activate: activateNavPanel,
      bindShortcuts,
      finishGitDiscovery() {
        gitDiscoveryFinished = true;
        // A Commits tab the server drew that discovery did not confirm goes.
        if (!hasGitPanel() && tabButton("git")) {
          removeNavPanel("git");
        }
        return restoreNeutralGitPanel();
      },
      home: goHome,
      /**
       * The route of the Files landing being applied (`landingRouteFor`). Read once: a
       * landing a tab switch or a history step began is taken by its own application.
       *
       * @param {"startup" | "user" | "popstate"} source
       */
      landingRoute(source) {
        const pending = filesLandingRoute;
        filesLandingRoute = null;
        return landingRouteFor(source, pending);
      },
      onHistory,
      open: openMainTab,
      openRoute,
      register: registerNavPanel,
      remember: rememberMainTabAddress,
      remove: removeNavPanel,
      reveal: revealAtAddress,
    });
    shellController = controller;
    return controller;
  }

  /**
   * The controller the shell made, which it makes once, for the SDK's
   * `navigation.openRoute`, which a startup script defines and which cannot reach the
   * shell's own copy. Null until the shell tools have loaded.
   *
   * @type {MetabrowserMainTabsController | null}
   */
  let shellController = null;

  /**
   * The shell's controller's `openRoute`, or false before the shell has made one, so the
   * browser follows the link.
   *
   * @param {string} href
   * @returns {boolean}
   */
  function openShellRoute(href) {
    return shellController?.openRoute(href) ?? false;
  }

  window.MetabrowserMainTabs = Object.freeze({
    create,
    openRoute: openShellRoute,
    REVEAL_ROUTES,
    landingRoute: landingRouteFor,
    revealPlan,
    tabAtAddress,
  });
})();
