// Deferred shell controller for the Files, Commits, and Pulls tabs.
(() => {
  const MAIN_TABS = [
    { id: "files", label: "Files", key: "1" },
    { id: "git", label: "Commits", key: "2" },
    { id: "pulls", label: "Pulls", key: "3" },
  ];

  /** @param {string} key @returns {Parameters<Window["MetabrowserKeyboardShortcuts"]["describeBindings"]>[0]} */
  function tabBindings(key) {
    return [{ key, modifiers: { meta: "require" } }, { key }];
  }
  /** @param {MetabrowserMainTabsDeps} deps */
  function create(deps) {
    const navBar = document.querySelector(".nav-tab-bar");
    /** @type {MetabrowserNavPanel[]} */
    let navPanels = [{ id: "files", label: "Files", onFirstShow: null }];
    /** @type {Set<string>} */
    const navPanelsShown = new Set(["files"]);
    /** The panel in front, and where each panel was scrolled to: they share one scroller. */
    let activeNavPanelId =
      navBar?.querySelector(".tab-btn.active")?.getAttribute("data-tab") ?? "files";
    /** @type {Map<string, number>} */
    const navPanelScroll = new Map();
    /** @type {Map<string, {href: string, state: unknown}>} */
    const mainTabDestinations = new Map();
    let keepFilesScrollOnLanding = false;
    let gitDiscoveryFinished = false;

    /** @param {string} panelId */
    function tabButton(panelId) {
      return /** @type {HTMLElement | null} */ (
        navBar?.querySelector(`.tab-btn[data-tab="${panelId}"]`) ?? null
      );
    }

    /** @param {ReturnType<Window["MetabrowserKeyboardShortcuts"]["create"]>} shortcuts */
    function bindShortcuts(shortcuts) {
      for (const { id, label, key } of MAIN_TABS) {
        const action = `Open ${label}`;
        const bindings = tabBindings(key);
        shortcuts.register({
          id: `main-tabs.${id}`,
          group: "main-tabs",
          scope: "global",
          order: Number(key),
          bindings,
          copy: { action, description: `Switch to the ${label} tab when available.`, hint: label },
          surfaces: { help: "always" },
          handler() {
            const button = tabButton(id);
            if (!button) {
              return false;
            }
            button.focus();
            openMainTab(id);
            return true;
          },
        });
        tabButton(id)?.setAttribute(
          "aria-keyshortcuts",
          shortcuts.describeBindings(bindings).ariaKeyshortcuts,
        );
      }
    }

    /** @param {MetabrowserNavPanel} panel */
    function registerNavPanel(panel) {
      if (navPanels.some((existing) => existing.id === panel.id)) {
        return;
      }
      navPanels.push(panel);
      ensureNavPanelElements(panel);
    }

    // Create the button and container for a panel that was not in the
    // server-rendered markup. Idempotent, so a re-registration after a root
    // change does not duplicate the tab.
    /** @param {MetabrowserNavPanel} panel */
    function ensureNavPanelElements(panel) {
      const content = document.getElementById("tree-content");
      if (!navBar || !content) {
        return;
      }
      if (!tabButton(panel.id)) {
        const btn = document.createElement("button");
        btn.className = "tab-btn";
        btn.type = "button";
        btn.setAttribute("role", "tab");
        btn.setAttribute("aria-selected", "false");
        btn.dataset.tab = panel.id;
        btn.textContent = panel.label;
        const shortcut = MAIN_TABS.find(({ id }) => id === panel.id);
        if (shortcut && window.MetabrowserKeyboardShortcuts) {
          const binding = window.MetabrowserKeyboardShortcuts.describeBindings(
            tabBindings(shortcut.key),
          );
          btn.setAttribute("aria-keyshortcuts", binding.ariaKeyshortcuts);
        }
        // Pulls can be present in the server shell before Git discovery finishes.
        navBar.insertBefore(btn, panel.id === "git" ? tabButton("pulls") : null);
      }
      if (!content.querySelector(`[data-tab-content="${panel.id}"]`)) {
        const container = document.createElement("div");
        container.id = `tab-${panel.id}`;
        container.dataset.tabContent = panel.id;
        container.style.display = "none";
        content.appendChild(container);
      }
    }

    /** @param {string} panelId */
    function removeNavPanel(panelId) {
      navPanels = navPanels.filter((panel) => panel.id !== panelId);
      navPanelsShown.delete(panelId);
      const button = tabButton(panelId);
      const container = document
        .getElementById("tree-content")
        ?.querySelector(`[data-tab-content="${panelId}"]`);
      const wasActive = button?.classList.contains("active");
      button?.remove();
      container?.remove();
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
      mainTabDestinations.delete("git");
      await deps.restore();
    }

    function mainTabAtAddress() {
      if (deps.isGitHistoryLanding()) {
        return "git";
      }
      const { pathname, search, hash } = window.location;
      const routes = window.MetabrowserNavigationRoute;
      if (routes.parse(pathname, search, hash)) {
        return "files";
      }
      if (routes.parseCommit(pathname)) {
        return "git";
      }
      return deps.isPullAddress(pathname) ? "pulls" : null;
    }

    function rememberMainTabAddress() {
      const panel = mainTabAtAddress();
      if (panel) {
        const { pathname, search, hash } = window.location;
        mainTabDestinations.set(panel, {
          href: `${pathname}${search}${hash}`,
          state: window.history.state,
        });
      }
    }

    /** @param {string} panelId The panel whose remembered route is landing. */
    function markMainTabLanding(panelId) {
      const scroll = navPanelScroll.get(panelId);
      keepFilesScrollOnLanding = panelId === "files" && scroll !== undefined;
      activateNavPanel(panelId);
      if (panelId === "pulls") {
        window.MetabrowserPullsNav?.routeChanged({ preserveScroll: scroll !== undefined });
        const scroller = document.getElementById("tree-content");
        if (scroller && scroll !== undefined) {
          // Marking the selected PR can reveal its row over the panel's saved scroll.
          scroller.scrollTop = scroll;
        }
      }
    }

    /** @param {string} panelId A click on one of the main navigation tabs. */
    function openMainTab(panelId) {
      if (panelId === activeNavPanelId) {
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
      // Git history has a neutral landing with no commit. Keep it in history without a new route.
      const state =
        panelId === "git"
          ? saved && href !== "/view/"
            ? { cachedCommit: true }
            : { gitLanding: true }
          : (saved?.state ?? null);
      deps.cancelPreview();
      window.history.pushState(state, "", href);
      rememberMainTabAddress();
      markMainTabLanding(panelId);
      if (panelId !== "pulls") {
        window.MetabrowserPullsNav?.routeChanged();
      }
      void deps.restore().catch((error) => {
        console.error("Could not restore main navigation tab", error);
      });
      if (panelId === "git" && !deps.isGitHistoryLanding()) {
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
      // filters on screen above content they cannot filter.
      const filterBar = document.getElementById("nav-filter-bar");
      if (filterBar) {
        filterBar.style.display = panelId === "files" ? "" : "none";
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

    function onHistory() {
      if (gitDiscoveryFinished && deps.isGitHistoryLanding() && !hasGitPanel()) {
        void restoreNeutralGitPanel().catch(console.error);
        return;
      }
      const panel = mainTabAtAddress();
      const switched = panel !== null && panel !== activeNavPanelId;
      if (switched) {
        deps.cancelPreview();
        markMainTabLanding(panel);
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
    return Object.freeze({
      active: () => activeNavPanelId,
      activate: activateNavPanel,
      bindShortcuts,
      finishGitDiscovery() {
        gitDiscoveryFinished = true;
        return restoreNeutralGitPanel();
      },
      onHistory,
      open: openMainTab,
      register: registerNavPanel,
      remember: rememberMainTabAddress,
      remove: removeNavPanel,
      fileLanding() {
        if (activeNavPanelId !== "files") {
          deps.cancelPreview();
          activateNavPanel("files");
        }
      },
      takeFilesScroll() {
        const preserve = keepFilesScrollOnLanding;
        keepFilesScrollOnLanding = false;
        return preserve;
      },
    });
  }

  window.MetabrowserMainTabs = Object.freeze({ create });
})();
