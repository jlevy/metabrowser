// The shell's own keys: the main pane's view tabs, the header's Up and Copy, the
// navigation pane's filters, and a pin's branch switcher.
//
// Each command runs an activation path the shell injects, the one its control's click
// runs, plus the focus a keyboard user needs next; none synthesizes a click. Each is
// targeted, so it is live only while the control it badges is on screen, and the
// registry reads that at dispatch. The main tabs' digits stay in static/main-tabs.js
// and the pull keys in static/pulls-nav.js, which own those controls.
//
// The registry arrives late, in the on-demand `shell-tools` bundle, and is rebuilt
// after a real `pagehide`, so whatever rendered before this keymap exists is read when
// it is created: the committed view tab bar, the header's controls, the filter
// triggers, and the selector. Render sites report later changes through the sync
// functions below, and only when a keymap exists.
// See docs/design-system.md, "Keyboard Commands and Help".

(() => {
  const VIEW_TAB_SELECTOR = ".tab-btn[data-view-key]";
  const BADGE_SELECTOR = ".kbd-badge";

  /** What the shell lends the keymap; see types.d.ts. @typedef {MetabrowserPublicShellKeymapShell} ShellKeymapShell */

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
    /** Commands registered only while their control exists: `X`, `A`, and `W`.
     * @type {Map<string, ShellCommandSlot>} */
    const conditional = new Map();
    let disposed = false;

    /** The main pane's own children, never what the inert stage holds. */
    const committed = () => Array.from(shell.pane()?.children ?? []);

    /** The view tab bar the main pane shows. */
    function committedBar() {
      return /** @type {HTMLElement | null} */ (
        committed().find((child) => child.classList.contains("tab-bar")) ?? null
      );
    }

    /**
     * The committed header's controls for Up and Copy. Up is the folder header's Up
     * button, which has no parent to open at the root, or for a file the crumb of its
     * folder; Copy is the file header's Copy path, or the commit view's Copy revision,
     * which the shell lends while that view is shown.
     */
    function headerControls() {
      const header = committed().find((child) => child.classList.contains("file-header"));
      /** @type {HTMLElement | null} */
      let parent = null;
      /** @type {HTMLElement | null} */
      let copy = null;
      if (header?.classList.contains("folder-header")) {
        parent = header.querySelector(".folder-up[data-nav-dir]:not([disabled])");
      } else if (header) {
        parent =
          Array.from(
            header.querySelectorAll(".folder-breadcrumb [data-nav-dir]"),
            (crumb) => /** @type {HTMLElement} */ (crumb),
          ).at(-1) ?? null;
        copy = header.querySelector(".file-header-copy");
      }
      const lent = shell.lentCopy();
      if (!copy && lent && shell.pane()?.contains(lent)) {
        copy = lent;
      }
      return { copy, parent };
    }

    /** @param {string} key A filter dropdown, `types` or `recency`. */
    const filterTrigger = (key) =>
      /** @type {HTMLElement | null} */ (
        shell.filterBar()?.querySelector(`[data-chip-menu-toggle="${key}"]`) ?? null
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

    // Up and Copy stay registered: Help lists them, and with no target, at the root
    // for Up and on a folder for Copy, they do nothing and leave the key alone.
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
    const releaseCopy = registerCommand({
      copy: {
        action: "Copy",
        description: "Copy the path of the current file, or the revision of the current commit.",
        hint: "Copy",
      },
      group: "controls",
      handler: (target) => shell.copyFromControl(target),
      id: "header.copy",
      key: "y",
      order: 20,
      surfaces: { help: "always", reveal: "always" },
    });
    /** @type {MetabrowserPublicShortcutTarget | null} */
    let parentTarget = null;
    /** @type {MetabrowserPublicShortcutTarget | null} */
    let copyTarget = null;

    /**
     * Point one of the header's commands at its control, or at none.
     *
     * @param {MetabrowserPublicShortcutTarget | null} slot
     * @param {string} commandId
     * @param {HTMLElement | null} element
     */
    function place(slot, commandId, element) {
      if (!element) {
        slot?.detach();
        return null;
      }
      if (slot) {
        slot.retarget(element);
        return slot;
      }
      // Up's and Copy's controls are icon buttons and crumbs in a clipping path row,
      // so their badges sit beside them, in the header that anchors them.
      return shortcuts.attachTarget(commandId, element, { placement: "beside" });
    }

    /**
     * Read the main-pane header again: Up's target is the folder header's Up button or,
     * for a file, the crumb of its folder, and none at the root; Copy's is the file
     * header's Copy path or the commit view's Copy revision, and none on a folder.
     */
    function syncHeader() {
      if (disposed) {
        return;
      }
      const controls = headerControls();
      shortcuts.batch(() => {
        parentTarget = place(parentTarget, "header.parent", controls.parent);
        copyTarget = place(copyTarget, "header.copy", controls.copy);
      });
    }

    /**
     * Hold a command while its control exists, and release it when the control goes:
     * a Git pin has no modified-within filter, and only a mirror's pin a branch switcher.
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
     * A filter key's activation: open the dropdown through its trigger's own path, the
     * shell's, then focus its checked row, or else its first, so the menu's arrow keys
     * work next. The focus half lives here, on demand, rather than in app.js.
     *
     * @param {string} key `types` or `recency`
     */
    function openFilterMenu(key) {
      shell.toggleFilterMenu(key, true);
      const menu = shell
        .filterBar()
        ?.querySelector(`.chip-menu[data-chip-menu="${key}"] .chip-menu-panel`);
      const row = /** @type {HTMLElement | null} */ (
        menu?.querySelector('.chip-menu-item[aria-checked="true"]') ??
          menu?.querySelector(".chip-menu-item") ??
          null
      );
      row?.focus();
      return true;
    }

    /** Read the filter triggers again, after the filter bar rebuilds its markup. */
    function syncFilters() {
      if (disposed) {
        return;
      }
      shortcuts.batch(() => {
        holdWhilePresent("filter.type", filterTrigger("types"), () =>
          registerCommand({
            copy: {
              action: "File type",
              description: "Open the file type filter.",
              hint: "File type",
            },
            group: "filters",
            handler: () => openFilterMenu("types"),
            id: "filter.type",
            key: "x",
            order: 10,
            surfaces: { help: "always" },
          }),
        );
        holdWhilePresent("filter.recency", filterTrigger("recency"), () =>
          registerCommand({
            copy: {
              action: "Modified within",
              description: "Open the modified-within filter.",
              hint: "Modified",
            },
            group: "filters",
            handler: () => openFilterMenu("recency"),
            id: "filter.recency",
            key: "a",
            order: 20,
            surfaces: { help: "always" },
          }),
        );
      });
    }

    /** Read the branch and tag selector again, once its on-demand bundle has mounted it. */
    function syncSource() {
      if (disposed) {
        return;
      }
      const selector = shell.sourceSelector();
      holdWhilePresent("source.switch-ref", selector?.button ?? null, () =>
        registerCommand({
          copy: {
            action: "Branch or tag",
            description: "Choose another branch or tag of the served repository.",
            hint: "Branch",
          },
          group: "controls",
          handler: () => {
            const current = shell.sourceSelector();
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
            // Below `global`, so the stack's P outranks a Preview tab's P only while a
            // pull request in a stack is open, and falls through to it otherwise.
            scope: "view-tabs",
            surfaces: { help: "always" },
            targeted: true,
          });
          viewTabs.set(key, { label, order, release, target: shortcuts.attachTarget(id, button) });
        }
      });
    }

    /**
     * The view tab letters follow the bar the main pane commits: release the outgoing
     * bar's letters, then hold the incoming bar's, in one publication. The shell calls
     * this inside view composition's `commit()` and never while a view is staged, so a
     * cancelled stage has registered nothing, and the bar still on screen keeps its keys.
     * Replacing the pane with something that has no bar passes `null`.
     *
     * @param {HTMLElement | null} previousBar
     * @param {HTMLElement | null} nextBar
     */
    function commitViewTabs(previousBar, nextBar) {
      if (disposed) {
        return;
      }
      shortcuts.batch(() => {
        for (const key of declaredTabs(previousBar).keys()) {
          releaseViewTab(key);
        }
        syncViewTabs(nextBar);
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
        parentTarget?.detach();
        copyTarget?.detach();
        parentTarget = null;
        copyTarget = null;
        releaseParent();
        releaseCopy();
      });
      disposed = true;
    }

    /** Follow whatever the main pane installed: its view tab letters and its header. */
    function syncPane() {
      shortcuts.batch(() => {
        syncViewTabs(committedBar());
        syncHeader();
      });
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
