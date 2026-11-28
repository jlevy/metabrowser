// The shell's own keys: Home, hiding the navigation pane, the main pane's view tabs, the
// header's Up, a pin's branch switcher, the numbers of the navigation's Refresh and of the
// navigation pane's filters, and the letters of their menus' rows.
//
// Each command runs the activation path its control's click runs, which the shell
// injects, plus the focus a keyboard user needs next; none synthesizes a click. Each is
// targeted, so it is live only while the control it badges is on screen, and the
// registry reads that at dispatch. The filters are situational, so they take numbers
// through the registry's `attachNumbered()` rather than letters; a menu's rows take the
// letters they declare, in the menu's own scope, live only while it is open and has
// focus (docs/design-system.md, "Keys in a Menu"). The main tabs' letters
// stay in static/main-tabs.js and the pull keys in static/pulls-nav.js, which own those
// controls. Copying a path or a revision is ancillary and has no key.
//
// The registry arrives late, in the on-demand `shell-tools` bundle, and is rebuilt
// after a real `pagehide`, so whatever rendered before this keymap exists is read when
// it is created: the committed view tab bar, the header's Up, the filter triggers, and
// the selector. Render sites report later changes through the sync functions below, and
// only when a keymap exists.
// See docs/design-system.md, "Keyboard Shortcuts".

(() => {
  const VIEW_TAB_SELECTOR = ".tab-btn[data-view-key]";
  const BADGE_SELECTOR = ".kbd-badge";

  /** What the shell lends the keymap; see types.d.ts. @typedef {MetabrowserPublicShellKeymapShell} ShellKeymapShell */

  /** The mounted branch and tag selector of a served mirror's pin, once its bundle has
   * mounted it; see static/source-ref-selector.js. */
  const sourceSelector = () => window.MetabrowserSourceRefSelector?.mounted() ?? null;

  /**
   * One command the keymap may hold, and the slot of the one target it badges.
   *
   * @typedef {object} ShellCommandSlot
   * @property {() => void} release
   * @property {MetabrowserPublicShortcutTarget | null} target
   */

  /**
   * A tab's label as the reader sees it, without a badge mounted inside it.
   *
   * @param {HTMLElement} button
   */
  function tabLabel(button) {
    return Array.from(button.childNodes)
      .filter(
        (node) =>
          !(
            typeof (/** @type {Element} */ (node).matches) === "function" &&
            /** @type {Element} */ (node).matches(BADGE_SELECTOR)
          ),
      )
      .map((node) => node.textContent || "")
      .join("")
      .trim();
  }

  /**
   * The letters a view tab bar declares, in tab order. The first tab keeps a letter
   * two tabs declare, as the server's own check does.
   *
   * @param {HTMLElement | null} bar
   * @returns {Map<string, HTMLElement>}
   */
  function declaredTabs(bar) {
    /** @type {Map<string, HTMLElement>} */
    const declared = new Map();
    if (!bar) {
      return declared;
    }
    for (const element of bar.querySelectorAll(VIEW_TAB_SELECTOR)) {
      const button = /** @type {HTMLElement} */ (element);
      const key = (button.dataset.viewKey || "").toLowerCase();
      if (/^[a-z]$/.test(key) && !declared.has(key) && button.dataset.tab) {
        declared.set(key, button);
      }
    }
    return declared;
  }

  /**
   * The native shell traverses the embedded web view's history. Its availability and the
   * web page's Shift reveal both cross the bridge here, with the keymap's lifetime.
   * @param {MetabrowserPublicShortcutRegistry} shortcuts
   */
  function bindNativeHistory(shortcuts) {
    const host = /** @type {Window & {
     *   metabrowserHost?: {actions?: readonly string[]},
     *   webkit?: {messageHandlers?: {metabrowserNavigation?: {postMessage(message: unknown): void}}},
     *   MetabrowserNativeNavigation?: {setState(state: {back: boolean, forward: boolean}): void},
     * }} */ (window);
    const handler = host.webkit?.messageHandlers?.metabrowserNavigation;
    if (!handler || !host.metabrowserHost?.actions?.includes("navigation-history")) {
      return () => {};
    }

    const available = { back: false, forward: false };
    const bridge = Object.freeze({
      /** @param {{back: boolean, forward: boolean}} state */
      setState(state) {
        available.back = state?.back === true;
        available.forward = state?.forward === true;
      },
    });
    host.MetabrowserNativeNavigation = bridge;

    /** @param {{kind: "state"} | {kind: "history", direction: "back" | "forward"} | {kind: "reveal", visible: boolean}} message */
    const post = (message) => {
      if (host.MetabrowserNativeNavigation !== bridge) {
        return false;
      }
      try {
        handler.postMessage({ ...message, url: window.location.href });
        return true;
      } catch {
        // The host can tear down the message handler while the web view is unloading.
        return false;
      }
    };

    /** @param {"back" | "forward"} direction @param {string} key @param {number} order */
    function register(direction, key, order) {
      const action = direction === "back" ? "Go back" : "Go forward";
      return shortcuts.register({
        available: () => available[direction],
        bindings: [{ key }],
        copy: {
          action,
          description:
            direction === "back"
              ? "Return to the previous page."
              : "Open the next page in history.",
          hint: action,
        },
        group: "anywhere",
        handler: ({ event }) => Boolean(event) && post({ kind: "history", direction }),
        id: `shell.history-${direction}`,
        order,
        scope: "global",
        surfaces: { help: "always" },
      });
    }
    const releaseBack = register("back", "[", 41);
    const releaseForward = register("forward", "]", 42);

    let revealed = false;
    const unsubscribe = shortcuts.subscribe(() => {
      const visible = shortcuts.isRevealed();
      if (visible !== revealed && post({ kind: "reveal", visible })) {
        revealed = visible;
      }
    });
    post({ kind: "state" });

    return () => {
      unsubscribe();
      releaseBack();
      releaseForward();
      if (host.MetabrowserNativeNavigation === bridge) {
        if (revealed) {
          post({ kind: "reveal", visible: false });
        }
        delete host.MetabrowserNativeNavigation;
      }
    };
  }

  /**
   * @param {{shortcuts: MetabrowserPublicShortcutRegistry, shell: ShellKeymapShell}} options
   */
  function createShellKeymap(options) {
    if (!options?.shortcuts || !options.shell) {
      throw new TypeError("The shell keymap requires a shortcut registry and the shell");
    }
    const { shortcuts, shell } = options;
    const releaseNativeHistory = bindNativeHistory(shortcuts);
    /** @type {Map<string, {label: string, order: number, release: () => void, target: MetabrowserPublicShortcutTarget}>} */
    const viewTabs = new Map();
    /** Commands registered only while their control exists: `W`.
     * @type {Map<string, ShellCommandSlot>} */
    const conditional = new Map();
    /** The filter triggers' numbers, each held while its trigger exists.
     * @type {Map<string, MetabrowserPublicShortcutTarget>} */
    const filterNumbers = new Map();
    /** The filter menus' row letters, by command id, each held while its row exists.
     * @type {Map<string, {signature: string, release: () => void, target: MetabrowserPublicShortcutTarget}>} */
    const menuLetters = new Map();
    /** The scope of the open menu whose rows have letters, while it is open.
     * @type {{key: string, release: () => void} | null} */
    let menuScope = null;
    let disposed = false;

    // The main pane and the navigation pane's filter bar, by the ids the server's shell
    // gives them, read here rather than lent, so app.js eagerly carries none of this.
    const pane = () => document.getElementById("preview-pane");
    const filterBar = () => document.getElementById("nav-filter-bar");

    /** The main pane's own children, never what the inert stage holds. */
    const committed = () => Array.from(pane()?.children ?? []);

    /** The view tab bar the main pane shows. */
    function committedBar() {
      return /** @type {HTMLElement | null} */ (
        committed().find((child) => child.classList.contains("tab-bar")) ?? null
      );
    }

    /**
     * The committed view header's control for Up: the Up button in its eyebrow, a file's
     * and a folder's alike, which has no parent to open at the served root.
     */
    function headerParent() {
      const header = committed().find((child) => child.classList.contains("file-header"));
      return /** @type {HTMLElement | null} */ (
        header?.querySelector(".folder-up[data-nav-dir]:not([disabled])") ?? null
      );
    }

    /** @param {string} key A filter dropdown: `group`, `recency`, or `types`. */
    const filterTrigger = (key) =>
      /** @type {HTMLElement | null} */ (
        filterBar()?.querySelector(`[data-chip-menu-toggle="${key}"]`) ?? null
      );

    /** @param {Record<string, unknown>} context */
    const targetOf = (context) =>
      context.target && typeof context.target === "object"
        ? /** @type {HTMLElement} */ (context.target)
        : null;

    /**
     * Register one of the shell's targeted commands.
     *
     * @param {{id: string, key: string, group: string, order: number,
     *          copy: {action: string, description: string, hint: string},
     *          surfaces: Record<string, "active" | "always">,
     *          handler: (target: HTMLElement) => boolean}} spec
     */
    function registerCommand(spec) {
      return shortcuts.register({
        bindings: [{ key: spec.key }],
        copy: spec.copy,
        group: spec.group,
        handler: (context) => {
          const target = targetOf(context);
          return target !== null && spec.handler(target);
        },
        id: spec.id,
        order: spec.order,
        scope: "global",
        surfaces: spec.surfaces,
        targeted: true,
      });
    }

    // Up stays registered: Help lists it, and with no target, at the root, it does
    // nothing and leaves the key alone.
    const releaseParent = registerCommand({
      copy: {
        action: "Parent folder",
        description: "Open the folder that contains the current file or folder.",
        hint: "Up",
      },
      group: "controls",
      handler: (target) => {
        const dir = target.dataset.navDir;
        if (dir === undefined) {
          return false;
        }
        shell.openFolder(dir);
        return true;
      },
      id: "header.parent",
      key: "u",
      order: 10,
      surfaces: { help: "always", reveal: "always" },
    });
    /** @type {MetabrowserPublicShortcutTarget | null} */
    let parentTarget = null;

    // `0` is Home, the one digit with a fixed meaning: the numbers stop at 9, so it never
    // reaches a numbered control, and Shift-0, which types `)` on a US keyboard, is `0` by
    // the registry's digit-row match. It runs the folder's name's own click path, and the
    // name, which the nav's header always shows, is its target. Its badge sits beside the
    // name, in the header that anchors it, since the name clips.
    const releaseHome = registerCommand({
      copy: {
        action: "Home",
        description:
          "Show the served folder's home view, with every tab at its first, as a fresh load does.",
        hint: "Home",
      },
      group: "anywhere",
      handler: () => {
        shell.goHome();
        return true;
      },
      id: "shell.home",
      key: "0",
      order: 30,
      surfaces: { help: "always", reveal: "always" },
    });
    const homeHeading = /** @type {HTMLElement | null} */ (document.querySelector(".header-path"));
    /** @type {MetabrowserPublicShortcutTarget | null} */
    let homeTarget = homeHeading
      ? shortcuts.attachTarget("shell.home", homeHeading, { placement: "beside" })
      : null;

    // `\` hides the navigation pane and shows it again; Shift+\, `|` on a US keyboard, is
    // the same key. Its target is the chevron on the main page's left edge, which stays on
    // screen while the pane is hidden, so the key is live either way, and its badge sits
    // beside the icon button (docs/design-system.md, "Hiding the Navigation Pane").
    const releaseNavToggle = registerCommand({
      copy: {
        action: "Hide or show navigation",
        description: "Hide the navigation pane so the page fills the window, or show it again.",
        hint: "Navigation",
      },
      group: "anywhere",
      handler: () => {
        shell.toggleNav();
        return true;
      },
      id: "shell.nav-toggle",
      key: "\\",
      order: 40,
      // Not on the revealed strip, whose seven items are measured (REVEAL_STRIP_MAX_ITEMS
      // in keyboard-help.js): Shift badges the chevron itself, so the key is shown where
      // it acts, and the strip keeps its room for keys that have no badge.
      surfaces: { help: "always" },
    });
    const navToggle = shell.navToggle();
    /** @type {MetabrowserPublicShortcutTarget | null} */
    let navToggleTarget = navToggle
      ? shortcuts.attachTarget("shell.nav-toggle", navToggle, { placement: "beside" })
      : null;

    // The navigation's one Refresh (static/refresh-plan.js), the icon button the server draws
    // at the top of the navigation on every page. It is situational, as the filters are, so
    // it takes a number, and as the first numbered control in reading order it is 1 under
    // every tab. Its number runs what its click runs; while it waits, `aria-disabled`, it
    // keeps its number and a press does nothing, as a click does. Its badge sits beside the
    // icon, as the chevron's does.
    const navRefresh = document.getElementById("nav-refresh");
    /** @type {MetabrowserPublicShortcutTarget | null} */
    let refreshNumber = navRefresh
      ? shortcuts.attachNumbered(navRefresh, {
          activate() {
            void window.MetabrowserRefreshPlan?.plan()?.press();
            return true;
          },
          placement: "beside",
        })
      : null;

    /**
     * Read the main-pane header again: Up's target is the view header's Up button, a
     * file's and a folder's alike, and none at the root.
     */
    function syncHeader() {
      if (disposed) {
        return;
      }
      const parent = headerParent();
      if (!parent) {
        parentTarget?.detach();
        parentTarget = null;
      } else if (parentTarget) {
        parentTarget.retarget(parent);
      } else {
        // Up's control is an icon button or a crumb in a clipping path row, so its badge
        // sits beside it, in the header that anchors it.
        parentTarget = shortcuts.attachTarget("header.parent", parent, { placement: "beside" });
      }
    }

    /**
     * Hold a command while its control exists, and release it when the control goes:
     * only a mirror's pin has a branch switcher.
     *
     * @param {string} id
     * @param {HTMLElement | null} element
     * @param {() => () => void} register
     */
    function holdWhilePresent(id, element, register) {
      const slot = conditional.get(id);
      if (!element) {
        if (slot) {
          slot.target?.detach();
          slot.release();
          conditional.delete(id);
        }
        return;
      }
      if (slot) {
        slot.target?.retarget(element);
        return;
      }
      const release = register();
      conditional.set(id, { release, target: shortcuts.attachTarget(id, element) });
    }

    /**
     * A filter number's activation: open the dropdown through its trigger's own path, the
     * shell's, then focus its checked row, or else its first, through the filter controls'
     * one path for every way a dropdown opens (`filterControls.focusMenu`), so the menu's
     * arrow keys, Enter, Escape, and its rows' letters work next
     * (docs/design-system.md, "Keys in a Menu").
     *
     * @param {string} key `group`, `recency`, or `types`
     */
    function openFilterMenu(key) {
      shell.toggleFilterMenu(key, true);
      const bar = filterBar();
      if (bar) {
        window.metabrowser?.filterControls?.focusMenu(bar, key);
      }
      return true;
    }

    /**
     * Read the filter triggers again, after the filter bar rebuilds its markup. Each is a
     * situational control, numbered by its place: Group by on the bar's row, then
     * Modified within and File type, on their triggers while the drawer that holds them
     * is open and on their stand-ins beside the chevron while it is closed. A Git pin
     * has no modified-within filter.
     */
    function syncFilters() {
      if (disposed) {
        return;
      }
      // A closed drawer is inert, so its filters are numbered on their stand-ins beside the
      // chevron (app.js, filterKeySlotsHtml) and keep their places whether or not it is open.
      const drawerOpen =
        filterBar()?.querySelector("#filter-drawer")?.getAttribute("data-open") === "true";
      shortcuts.batch(() => {
        for (const key of ["group", "recency", "types"]) {
          const control = filterTrigger(key);
          const trigger =
            control && key !== "group" && !drawerOpen
              ? /** @type {HTMLElement | null} */ (
                  filterBar()?.querySelector(`[data-filter-key-slot="${key}"]`) ?? control
                )
              : control;
          const held = filterNumbers.get(key);
          if (!trigger) {
            held?.detach();
            filterNumbers.delete(key);
          } else if (held) {
            held.retarget(trigger);
          } else {
            filterNumbers.set(
              key,
              shortcuts.attachNumbered(trigger, { activate: () => openFilterMenu(key) }),
            );
          }
        }
        syncMenuLetters();
      });
    }

    /** @param {string} key A filter dropdown. */
    const filterMenu = (key) =>
      /** @type {HTMLElement | null} */ (
        filterBar()?.querySelector(`.chip-menu[data-chip-menu="${key}"]`) ?? null
      );

    /** @param {string} key Whether focus is in that dropdown: on its trigger or a row. */
    function menuHasFocus(key) {
      const active = document.activeElement;
      return Boolean(active && filterMenu(key)?.contains(active));
    }

    /**
     * Release one row letter's command and its target.
     *
     * @param {string} id
     */
    function releaseMenuLetter(id) {
      const held = menuLetters.get(id);
      if (held) {
        held.target.detach();
        held.release();
        menuLetters.delete(id);
      }
    }

    /**
     * Read the filter menus' row letters again (docs/design-system.md, "Keys in a Menu").
     * A row that declares one, `data-menu-key`, holds a command in its menu's own scope,
     * targeted on the row, whose handler runs the row's click path
     * (`filterControls.activateMenuRow`); its Help copy names the row and the menu. A
     * letter two rows of one menu declare stays the first's. The scope is active while
     * that menu is open, so the letters outrank the shell's only then, and each command
     * also waits for focus to be in the menu, so a letter pressed elsewhere is the shell's.
     * Registered while the rows exist, closed or open, so Help lists them.
     */
    function syncMenuLetters() {
      const bar = filterBar();
      /** @type {Set<string>} */
      const seen = new Set();
      for (const element of bar?.querySelectorAll(".chip-menu[data-chip-menu]") ?? []) {
        const menu = /** @type {HTMLElement} */ (element);
        const key = menu.dataset.chipMenu || "";
        const name =
          menu.querySelector("[data-chip-menu-toggle]")?.getAttribute("aria-label") || key;
        /** @type {Set<string>} */
        const letters = new Set();
        for (const rowElement of menu.querySelectorAll(".chip-menu-item[data-menu-key]")) {
          const row = /** @type {HTMLElement} */ (rowElement);
          const letter = row.dataset.menuKey || "";
          if (!/^[a-z]$/.test(letter) || letters.has(letter)) {
            continue;
          }
          letters.add(letter);
          // One command per letter of a menu, as a view tab bar has one per letter.
          const id = `menu.${key}.${letter}`;
          const label = row.querySelector(".menu-item-label")?.textContent?.trim() || letter;
          const order = letters.size;
          const signature = [letter, label, name, order].join("\n");
          seen.add(id);
          const held = menuLetters.get(id);
          if (held?.signature === signature) {
            held.target.retarget(row);
            continue;
          }
          // A command's copy is fixed at registration, so a row whose label or letter
          // changed is registered again.
          releaseMenuLetter(id);
          const release = shortcuts.register({
            available: () => menuHasFocus(key),
            bindings: [{ key: letter }],
            copy: {
              action: label,
              description: `Choose ${label} in the ${name} menu.`,
              hint: label,
            },
            group: "menus",
            handler: (context) => {
              const target = targetOf(context);
              return Boolean(target && window.metabrowser?.filterControls?.activateMenuRow(target));
            },
            id,
            order,
            scope: `menu:${key}`,
            surfaces: { help: "always", reveal: "always" },
            targeted: true,
          });
          menuLetters.set(id, { release, signature, target: shortcuts.attachTarget(id, row) });
        }
      }
      for (const id of Array.from(menuLetters.keys())) {
        if (!seen.has(id)) {
          releaseMenuLetter(id);
        }
      }
      const open = /** @type {HTMLElement | null} */ (
        bar?.querySelector('.chip-menu[aria-expanded="true"]') ?? null
      );
      const openKey =
        open?.querySelector(".chip-menu-item[data-menu-key]") && open.dataset.chipMenu
          ? open.dataset.chipMenu
          : null;
      if (menuScope && menuScope.key !== openKey) {
        menuScope.release();
        menuScope = null;
      }
      if (openKey && !menuScope) {
        menuScope = { key: openKey, release: shortcuts.activateScope(`menu:${openKey}`) };
      }
    }

    /** Read the branch and tag selector again, once its on-demand bundle has mounted it. */
    function syncSource() {
      if (disposed) {
        return;
      }
      const selector = sourceSelector();
      holdWhilePresent("source.switch-ref", selector?.button ?? null, () =>
        registerCommand({
          copy: {
            action: "Branch or tag",
            description: "Choose another branch or tag of the served repository.",
            hint: "Branch",
          },
          group: "controls",
          handler: () => {
            const current = sourceSelector();
            if (!current) {
              return false;
            }
            void current.activate();
            return true;
          },
          id: "source.switch-ref",
          key: "w",
          order: 30,
          surfaces: { help: "always", reveal: "always" },
        }),
      );
    }

    /** @param {string} key */
    function releaseViewTab(key) {
      const held = viewTabs.get(key);
      if (held) {
        held.target.detach();
        held.release();
        viewTabs.delete(key);
      }
    }

    /**
     * Make the registry's view tab letters the ones `bar` declares: register each
     * letter not yet held, retarget each one held under the same label, re-register one
     * whose label changed, since a command's copy is fixed at registration, and release
     * each letter the bar no longer declares. Idempotent, and one publication.
     *
     * @param {HTMLElement | null} bar
     */
    function syncViewTabs(bar) {
      if (disposed) {
        return;
      }
      shortcuts.batch(() => {
        const declared = declaredTabs(bar);
        for (const key of Array.from(viewTabs.keys())) {
          if (!declared.has(key)) {
            releaseViewTab(key);
          }
        }
        let order = 0;
        for (const [key, button] of declared) {
          order += 1;
          const label = tabLabel(button);
          const held = viewTabs.get(key);
          if (held && held.label === label && held.order === order) {
            held.target.retarget(button);
            continue;
          }
          releaseViewTab(key);
          const id = `view-tabs.${key}`;
          const release = shortcuts.register({
            bindings: [{ key }],
            copy: {
              action: label,
              description: `Show the ${label} view of the current file in the main pane.`,
              hint: label,
            },
            group: "view-tabs",
            handler: (context) => {
              const target = targetOf(context);
              const tabBar = /** @type {HTMLElement | null} */ (target?.parentElement ?? null);
              return Boolean(
                target?.dataset.tab && tabBar && shell.selectPreviewTab(tabBar, target.dataset.tab),
              );
            },
            id,
            order,
            // Below `global`, so a shell letter always outranks a view tab's; the keymap
            // check keeps the two apart (src/metabrowser/keymap.py).
            scope: "view-tabs",
            surfaces: { help: "always" },
            targeted: true,
          });
          viewTabs.set(key, { label, order, release, target: shortcuts.attachTarget(id, button) });
        }
      });
    }

    /**
     * The view tab letters, and the header committed with them, follow the bar the main
     * pane commits, in one publication. The letters held are the outgoing bar's, so
     * `syncViewTabs()` diffs them against the incoming bar's: a letter both declare under
     * the same label keeps its command and moves its target, and only a letter that
     * comes, goes, or changes label publishes a `registration`. A move between two files
     * of one kind therefore registers nothing. The shell calls this inside view
     * composition's `commit()` and never while a view is staged, so a cancelled stage
     * has registered nothing, and the bar still on screen keeps its keys. Replacing the
     * pane with something that has no bar passes `null`.
     *
     * @param {HTMLElement | null} nextBar
     */
    function commitViewTabs(nextBar) {
      if (disposed) {
        return;
      }
      shortcuts.batch(() => {
        syncViewTabs(nextBar);
        syncHeader();
      });
    }

    function dispose() {
      if (disposed) {
        return;
      }
      shortcuts.batch(() => {
        releaseNativeHistory();
        for (const key of Array.from(viewTabs.keys())) {
          releaseViewTab(key);
        }
        for (const slot of conditional.values()) {
          slot.target?.detach();
          slot.release();
        }
        conditional.clear();
        for (const held of filterNumbers.values()) {
          held.detach();
        }
        filterNumbers.clear();
        for (const id of Array.from(menuLetters.keys())) {
          releaseMenuLetter(id);
        }
        menuScope?.release();
        menuScope = null;
        parentTarget?.detach();
        parentTarget = null;
        releaseParent();
        homeTarget?.detach();
        homeTarget = null;
        releaseHome();
        navToggleTarget?.detach();
        navToggleTarget = null;
        releaseNavToggle();
        refreshNumber?.detach();
        refreshNumber = null;
      });
      disposed = true;
    }

    /**
     * Follow whatever the main pane installed: its view tab letters and its header.
     * After `commitViewTabs()` in the same commit, every target is already in place, so
     * this moves nothing and publishes nothing.
     */
    function syncPane() {
      commitViewTabs(committedBar());
    }

    // Replay what rendered before the registry existed, on first build and on rebuild.
    shortcuts.batch(() => {
      syncViewTabs(committedBar());
      syncHeader();
      syncFilters();
      syncSource();
    });

    return Object.freeze({
      commitViewTabs,
      committedBar,
      dispose,
      syncFilters,
      syncHeader,
      syncPane,
      syncSource,
      syncViewTabs,
    });
  }

  window.MetabrowserShellKeymap = Object.freeze({ createShellKeymap });
})();
