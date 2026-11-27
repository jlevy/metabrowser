// The navigation's one Refresh: the icon button the server draws, glyph and all, at the top
// of the navigation on every page (server.py, `nav_refresh`), and its number, 1 on every
// tab (static/shell-keymap.js). One press refreshes every part of the page that can be read
// again, in one order: the parts on screen first, then the parts behind other tabs, so a
// tab the reader turns to next is already fresh (docs/design-system.md, "Refresh, Retry,
// and Reload Page"). Each part refreshes through the path it already had; this module adds
// no route and no refresh of its own:
//
// - `source`: the mirror or origin a pinned revision's page reads, through its freshness
//   row's controller (static/source-freshness.js, `refreshNow`), which asks
//   `/api/source/refresh` and settles once nothing is fetching. A page with no fetchable
//   store has no such part, and neither has a checkout's working tree's, which reads the
//   disk and has no freshness row: its fetch is `origin`, below.
// - `refs`: the branch and tag chooser's list, read again in place while it is open, with
//   its scroll and focus kept (static/source-ref-selector.js, `reread`). It is on screen
//   only then, and after the source, so it lists what the fetch brought.
// - `page`: the pull request's page in the main pane, its own refresh (pull-page.js).
// - `files`: the tree and the file or folder the pane holds, read again (app.js,
//   `rereadFiles`, as when a revision's file ages land).
// - `pulls`: the Pulls tab's list (pulls-panel.js), once it is mounted.
// - `git`: the Commits tab's history, read again from the routes that follow the served
//   revision (git-panel.js, `refresh`), once the tab has read it.
// - `origin`: on a checkout's working tree's page, the fetch of the store Metabrowser
//   keeps of the checkout's origin, which its Remotes and Tags are listed from
//   (static/source-ref-selector.js, `fetchOrigin`). Nothing the page shows waits for it:
//   the files are on disk and the history is the checkout's own. So it is never on screen
//   and runs last, after the disk and the history are read again and the button is
//   offered again, and an open chooser list then follows the fetch to its end.
//
// A press runs the parts one at a time, awaiting each, so what reads the mirror reads what
// its fetch brought. The button keeps its place and spins while the parts on screen refresh.
// A quick press shows the spinner briefly, including when no part needs an update.
// A press while the button waits does nothing, as the click of any waiting control does. A
// part that fails says so where it is drawn, and the rest still run.
(() => {
  // Keep a quick press visible for part of a spinner turn.
  const FEEDBACK_MS = 240;

  /**
   * Every part a press refreshes, in the order it runs them within each half: the source
   * first, since every other part reads what its fetch brings, and the chooser's list
   * straight after it; then the main pane's pull request page; then the tabs, in tab
   * order (static/main-tabs.js, `MAIN_TABS`); and last a working tree's fetch of its
   * origin, which no other part reads.
   *
   * @type {readonly MetabrowserRefreshPart[]}
   */
  const PARTS = Object.freeze(["source", "refs", "page", "files", "pulls", "git", "origin"]);

  /**
   * Whether a part is on screen, from the tab in front and what holds the main pane
   * (`data-preview-owner`, app.js `claimPreview`). The source's freshness row is at the
   * foot of the navigation on every tab. The Files and Commits parts are on screen while
   * their tab is in front, and also while the pane shows a file or folder, or a commit.
   * The chooser's list is on screen while it is open (*view.chooser*). A working tree's
   * fetch of its origin never is: it changes nothing the page shows but that list.
   *
   * @param {MetabrowserRefreshPart} id
   * @param {{front: string, owner: string, chooser?: boolean}} view
   * @returns {boolean}
   */
  function isShown(id, view) {
    switch (id) {
      case "source":
        return true;
      case "refs":
        return view.chooser === true;
      case "origin":
        return false;
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

  /** @param {string | MetabrowserRefreshTooltipTiming | null | undefined} timing */
  function timingText(timing) {
    if (timing == null || typeof timing === "string") {
      return timing ?? null;
    }
    const at = Date.parse(timing.finished_at);
    if (!Number.isFinite(at) || at <= 0) {
      return null;
    }
    const format = window.MetabrowserFormatters;
    const age = format.age(at / 1000, { style: "relative" }).label;
    if (!age) {
      return null;
    }
    const summary = `${timing.label ?? "Refreshed"} ${age}`;
    const ms = timing.duration_ms;
    const duration =
      typeof ms !== "number" || !Number.isFinite(ms) || ms < 0
        ? null
        : ms < 1000
          ? `${Math.round(ms)}ms`
          : `${Math.round(ms / 100) / 10}s`;
    if (timing.provider !== "github_cli") {
      return duration === null ? summary : `${summary} in ${duration}`;
    }
    const requests = timing.request_count;
    const bytes = timing.response_body_bytes;
    const detail = [
      typeof requests === "number" && Number.isSafeInteger(requests) && requests >= 0
        ? `${format.formatInteger(requests)} ${requests === 1 ? "request" : "requests"}`
        : null,
      typeof bytes === "number" && Number.isSafeInteger(bytes) && bytes >= 0
        ? format.formatBytes(bytes)
        : null,
      duration,
      "GitHub CLI",
    ];
    return `${summary}\n${detail.filter(Boolean).join(" · ")}`;
  }

  /**
   * The page's plan, on the server's button: its click, its waiting state, and the shell's
   * own parts. Browser only; the pull request's parts are provided by the Pulls tab's list
   * once it mounts (pulls-nav.js, `refreshParts`).
   */
  function mount() {
    const element = document.getElementById("nav-refresh");
    if (mounted !== null || !(element instanceof HTMLElement)) {
      return mounted;
    }
    const button = element;
    const preview = document.getElementById("preview-pane");
    const view = () => ({
      front:
        document.querySelector(".nav-tab-bar .tab-btn.active")?.getAttribute("data-tab") ?? "files",
      owner: preview?.dataset.previewOwner ?? "",
      // The chooser's root says whether its list is open (source-ref-selector.js, `paint`).
      chooser: document.getElementById("source-ref-selector")?.dataset.open === "true",
    });
    /** @type {Map<string, () => string | MetabrowserRefreshTooltipTiming | null>} */
    const tips = new Map();
    function paintTooltip() {
      const { front, owner } = view();
      const source = document.getElementById("source-ref-selector")?.dataset;
      const workingTree = source?.sourceMode === "working-tree";
      const detail =
        (owner === "pull-request" ? timingText(tips.get("page")?.()) : null) ??
        timingText(tips.get(front)?.()) ??
        timingText(
          workingTree
            ? { finished_at: source.sourceObservedAt ?? "", label: "Checkout state read" }
            : {
                finished_at:
                  document.getElementById("source-freshness")?.dataset.lastFetchAt ||
                  source?.sourceSyncedAt ||
                  "",
                label: "Last fetched",
              },
        );
      const text = detail ?? "Refresh";
      if (button.dataset.tipText !== text) {
        button.dataset.tipText = text;
        window.MetabrowserTooltip?.updateText?.(button);
      }
      const description = detail?.replace("\n", ". ") ?? null;
      if (button.getAttribute("aria-description") !== description) {
        if (description === null) {
          button.removeAttribute("aria-description");
        } else {
          button.setAttribute("aria-description", description);
        }
      }
    }

    /** @param {string} tab @param {() => string | MetabrowserRefreshTooltipTiming | null} tip */
    function provideTooltip(tab, tip) {
      tips.set(tab, tip);
      paintTooltip();
      return () => {
        if (tips.get(tab) === tip) {
          tips.delete(tab);
          paintTooltip();
        }
      };
    }

    // Pointerover precedes the delegated mouseenter that reads data-tip-text.
    button.addEventListener("pointerover", paintTooltip);
    button.addEventListener("focus", paintTooltip);

    let preparing = false;
    let feedbackStarted = 0;
    /** @type {number | null} */
    let feedbackTimer = null;
    function finishFeedback() {
      function stop() {
        delete button.dataset.refreshing;
        feedbackTimer = null;
      }
      const remaining = FEEDBACK_MS - (window.performance.now() - feedbackStarted);
      if (remaining > 0) {
        feedbackTimer = window.setTimeout(stop, remaining);
      } else {
        stop();
      }
    }

    const plan = createPlan({
      shown: (id) => isShown(id, view()),
      waiting(on) {
        if (!on) {
          button.removeAttribute("aria-disabled");
          finishFeedback();
          paintTooltip();
        }
      },
      failed: (id, error) => console.error(`Refresh of ${id} failed`, error),
    });
    const shell = window.MetabrowserShell;
    /** @type {Promise<void> | null} */
    let sourceAsked = null;
    // The freshness row lends its part once its script has run. A row whose script failed
    // to load is asked for again on the next press, as app.js `sourceFreshness` then
    // starts it afresh, and a press waits for the answer, so its fetch still comes first.
    const askSource = () => {
      if (shell) {
        sourceAsked ??= shell.sourceFreshness().then(
          (controller) => {
            if (controller) {
              plan.provide("source", () => controller.refreshNow());
            }
          },
          (error) => {
            sourceAsked = null;
            console.error("Refresh could not start the freshness row", error);
          },
        );
      }
      return sourceAsked;
    };
    if (shell) {
      plan.provide("files", () => shell.rereadFiles());
    }
    void askSource();
    plan.provide("git", () => window.MetabrowserGitPanel?.refresh());
    // The chooser mounts after the first tree, so its parts ask for it at each press.
    const chooser = () => window.MetabrowserSourceRefSelector?.mounted() ?? null;
    if (document.getElementById("source-ref-selector") !== null) {
      plan.provide("refs", () => chooser()?.reread({ filesCovered: Boolean(shell) }));
      if (window.METABROWSER_SOURCE_CHECKOUT?.working_tree === true) {
        plan.provide("origin", () => chooser()?.fetchOrigin());
      }
    }
    const press = async () => {
      if (preparing || plan.waiting()) {
        return false;
      }
      preparing = true;
      button.setAttribute("aria-disabled", "true");
      if (feedbackTimer !== null) {
        window.clearTimeout(feedbackTimer);
        feedbackTimer = null;
      }
      feedbackStarted = window.performance.now();
      button.dataset.refreshing = "true";
      window.MetabrowserTooltip?.hide(button);
      try {
        await askSource();
      } catch (error) {
        button.removeAttribute("aria-disabled");
        finishFeedback();
        throw error;
      } finally {
        preparing = false;
      }
      return plan.press();
    };
    button.addEventListener("click", () => void press());
    mounted = Object.freeze({ ...plan, press, provideTooltip, updateTooltip: paintTooltip });
    return mounted;
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
