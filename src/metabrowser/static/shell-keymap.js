// The shell's own keys: the main pane's view tabs, the header's Up, a pin's branch
// switcher, and the numbers of the navigation pane's filters.
//
// Each command runs the activation path its control's click runs, which the shell
// injects, plus the focus a keyboard user needs next; none synthesizes a click. Each is
// targeted, so it is live only while the control it badges is on screen, and the
// registry reads that at dispatch. The filters are situational, so they take numbers
// through the registry's `attachNumbered()` rather than letters. The main tabs' letters
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
   * @param {{shortcuts: MetabrowserPublicShortcutRegistry, shell: ShellKeymapShell}} options
   */
  function createShellKeymap(options) {
    if (!options?.shortcuts || !options.shell) {
      throw new TypeError("The shell keymap requires a shortcut registry and the shell");
    }
    const { shortcuts, shell } = options;
    /** @type {Map<string, {label: string, order: number, release: () => void, target: MetabrowserPublicShortcutTarget}>} */
    const viewTabs = new Map();
    /** Commands registered only while their control exists: `W`.
     * @type {Map<string, ShellCommandSlot>} */
    const conditional = new Map();
    /** The filter triggers' numbers, each held while its trigger exists.
     * @type {Map<string, MetabrowserPublicShortcutTarget>} */
    const filterNumbers = new Map();
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
     * The committed header's control for Up: the folder header's Up button, which has
     * no parent to open at the root, or for a file the crumb of its folder.
     */
    function headerParent() {
      const header = committed().find((child) => child.classList.contains("file-header"));
      if (header?.classList.contains("folder-header")) {
        return /** @type {HTMLElement | null} */ (
          header.querySelector(".folder-up[data-nav-dir]:not([disabled])")
        );
      }
      if (!header) {
        return null;
      }
      return (
        Array.from(
          header.querySelectorAll(".folder-breadcrumb [data-nav-dir]"),
          (crumb) => /** @type {HTMLElement} */ (crumb),
        ).at(-1) ?? null
      );
    }

    /** @param {string} key A filter dropdown, `types` or `recency`. */
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

    /**
     * Read the main-pane header again: Up's target is the folder header's Up button or,
     * for a file, the crumb of its folder, and none at the root.
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
     * shell's, then focus its checked row, or else its first, so the menu's arrow keys
     * work next. The focus half lives here, on demand, rather than in app.js.
     *
     * @param {string} key `types` or `recency`
     */
    function openFilterMenu(key) {
      shell.toggleFilterMenu(key, true);
      const menu = filterBar()?.querySelector(
        `.chip-menu[data-chip-menu="${key}"] .chip-menu-panel`,
      );
      const row = /** @type {HTMLElement | null} */ (
        menu?.querySelector('.chip-menu-item[aria-checked="true"]') ??
          menu?.querySelector(".chip-menu-item") ??
          null
      );
      row?.focus();
      return true;
    }

    /**
     * Read the filter triggers again, after the filter bar rebuilds its markup. Each is a
     * situational control, numbered by its place on screen: a Git pin has no
     * modified-within filter, so the type filter is first there.
     */
    function syncFilters() {
      if (disposed) {
        return;
      }
      shortcuts.batch(() => {
        for (const key of ["recency", "types"]) {
          const trigger = filterTrigger(key);
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
      });
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
        parentTarget?.detach();
        parentTarget = null;
        releaseParent();
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
