// The navigation's one Refresh: the icon button the server draws, glyph and all, at the top
// of the navigation on every page (server.py, `nav_refresh`), and its number, 1 on every
// tab (static/shell-keymap.js). One press refreshes every part of the page that can be read
// again, in one order: the parts on screen first, then the parts behind other tabs, so a
// tab the reader turns to next is already fresh (docs/design-system.md, "Refresh, Retry,
// and Reload Page"). Each part refreshes through the path it already had; this module adds
// no route and no refresh of its own:
//
// - `source`: the mirror or origin the page reads, through its freshness row's controller
//   (static/source-freshness.js, `refreshNow`), which asks `/api/source/refresh` and
//   settles once nothing is fetching. A page with no fetchable store has no such part.
// - `page`: the pull request's page in the main pane, its own refresh (pull-page.js).
// - `files`: the tree and the file or folder the pane holds, read again (app.js,
//   `rereadFiles`, as when a revision's file ages land).
// - `pulls`: the Pulls tab's list (pulls-panel.js), once it is mounted.
// - `git`: the Commits tab's history, read again from the routes that follow the served
//   revision (git-panel.js, `refresh`), once the tab has read it.
//
// A press runs the parts one at a time, awaiting each, so what reads the mirror reads what
// its fetch brought. The button waits, `aria-disabled` and dimmed in its place, while the
// parts on screen refresh, and only then; each part shows its own busy state while it runs.
// A press while the button waits does nothing, as the click of any waiting control does. A
// part that fails says so where it is drawn, and the rest still run.
(() => {
  /**
   * Every part a press refreshes, in the order it runs them within each half: the source
   * first, since every other part reads what its fetch brings; then the main pane's pull
   * request page; then the tabs, in tab order (static/main-tabs.js, `MAIN_TABS`).
   *
   * @type {readonly MetabrowserRefreshPart[]}
   */
  const PARTS = Object.freeze(["source", "page", "files", "pulls", "git"]);

  /**
   * Whether a part is on screen, from the tab in front and what holds the main pane
   * (`data-preview-owner`, app.js `claimPreview`). The source's freshness row is at the
   * foot of the navigation on every tab. The Files and Commits parts are on screen while
   * their tab is in front, and also while the pane shows a file or folder, or a commit.
   *
   * @param {MetabrowserRefreshPart} id
   * @param {{front: string, owner: string}} view
   * @returns {boolean}
   */
  function isShown(id, view) {
    switch (id) {
      case "source":
        return true;
      case "page":
        return view.owner === "pull-request";
      case "files":
        return view.front === "files" || view.owner === "file";
      case "pulls":
        return view.front === "pulls";
      case "git":
        return view.front === "git" || view.owner === "git";
    }
  }

  /**
   * The one order of a press: the parts on screen, then the rest, each half in `PARTS`
   * order.
   *
   * @param {readonly MetabrowserRefreshPart[]} ids The parts that can refresh now.
   * @param {(id: MetabrowserRefreshPart) => boolean} shown
   * @returns {{visible: MetabrowserRefreshPart[], hidden: MetabrowserRefreshPart[]}}
   */
  function inVisibilityOrder(ids, shown) {
    const present = PARTS.filter((id) => ids.includes(id));
    return {
      visible: present.filter((id) => shown(id)),
      hidden: present.filter((id) => !shown(id)),
    };
  }

  /**
   * The plan: which parts can refresh, and a press that runs them in order.
   *
   * *deps.shown* says whether a part is on screen, read once per press. *deps.waiting* is
   * told when the parts on screen start and when they have all settled. *deps.failed* is
   * told of a part whose refresh threw, which the part has already said where it is drawn.
   *
   * @param {{
   *   shown(id: MetabrowserRefreshPart): boolean,
   *   waiting(on: boolean): void,
   *   failed?(id: MetabrowserRefreshPart, error: unknown): void,
   * }} deps
   */
  function createPlan(deps) {
    /** @type {Map<MetabrowserRefreshPart, () => unknown>} */
    const parts = new Map();
    let waiting = false;
    // A later press supersedes what an earlier one has not reached behind other tabs, since
    // it refreshes them itself.
    let presses = 0;

    /**
     * A part that can refresh until the returned release is called; a later provide of the
     * same part replaces it.
     *
     * @param {MetabrowserRefreshPart} id
     * @param {() => unknown} refresh
     * @returns {() => void}
     */
    function provide(id, refresh) {
      if (!PARTS.includes(id)) {
        throw new TypeError(`Unknown refresh part: ${id}`);
      }
      parts.set(id, refresh);
      return () => {
        if (parts.get(id) === refresh) {
          parts.delete(id);
        }
      };
    }

    /** @param {MetabrowserRefreshPart} id */
    async function run(id) {
      const refresh = parts.get(id);
      if (refresh === undefined) {
        return;
      }
      try {
        await refresh();
      } catch (error) {
        deps.failed?.(id, error);
      }
    }

    /**
     * One press: the parts on screen while the button waits, then the rest. Answers false
     * for a press while the button waits, which does nothing.
     *
     * @returns {Promise<boolean>}
     */
    async function press() {
      if (waiting) {
        return false;
      }
      const mine = ++presses;
      const order = inVisibilityOrder(Array.from(parts.keys()), (id) => deps.shown(id));
      waiting = true;
      deps.waiting(true);
      try {
        for (const id of order.visible) {
          await run(id);
        }
      } finally {
        waiting = false;
        deps.waiting(false);
      }
      for (const id of order.hidden) {
        if (mine !== presses) {
          break;
        }
        await run(id);
      }
      return true;
    }

    return Object.freeze({
      provide,
      press,
      waiting: () => waiting,
      /** The parts that can refresh now, in `PARTS` order. */
      parts: () => PARTS.filter((id) => parts.has(id)),
    });
  }

  /** @type {ReturnType<typeof createPlan> | null} */
  let mounted = null;

  /**
   * The page's plan, on the server's button: its click, its waiting state, and the shell's
   * own parts. Browser only; the pull request's parts are provided by the Pulls tab's list
   * once it mounts (pulls-nav.js, `refreshParts`).
   */
  function mount() {
    const button = document.getElementById("nav-refresh");
    if (mounted !== null || !(button instanceof HTMLElement)) {
      return mounted;
    }
    const preview = document.getElementById("preview-pane");
    const view = () => ({
      front:
        document.querySelector(".nav-tab-bar .tab-btn.active")?.getAttribute("data-tab") ?? "files",
      owner: preview?.dataset.previewOwner ?? "",
    });
    const plan = createPlan({
      shown: (id) => isShown(id, view()),
      waiting(on) {
        if (on) {
          button.setAttribute("aria-disabled", "true");
        } else {
          button.removeAttribute("aria-disabled");
        }
      },
      failed: (id, error) => console.error(`Refresh of ${id} failed`, error),
    });
    const shell = window.MetabrowserShell;
    if (shell) {
      plan.provide("files", () => shell.rereadFiles());
      void shell.sourceFreshness().then((controller) => {
        if (controller) {
          plan.provide("source", () => controller.refreshNow());
        }
      });
    }
    plan.provide("git", () => window.MetabrowserGitPanel?.refresh());
    button.addEventListener("click", () => void plan.press());
    mounted = plan;
    return plan;
  }

  window.MetabrowserRefreshPlan = Object.freeze({
    PARTS,
    createPlan,
    inVisibilityOrder,
    isShown,
    mount,
    /** The page's plan, or null before `mount` or on a page with no Refresh. */
    plan: () => mounted,
  });
  // The shell-tools bundle runs after the first usable tree, and the button was drawn
  // before then, so the plan mounts as this script evaluates.
  if (typeof document !== "undefined") {
    mount();
  }
})();
