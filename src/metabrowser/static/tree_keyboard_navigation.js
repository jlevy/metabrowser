// Accessible roving focus and command handling for Metabrowser file trees.

(() => {
  /**
   * @typedef {object} TreeMutationSnapshot
   * @property {string | null} anchor
   * @property {boolean} hadFocus
   * @property {string | null} parent
   * @property {string[]} siblings
   */

  /** @param {Element | null} element @param {string} role */
  function hasRole(element, role) {
    return element?.getAttribute("role") === role;
  }

  /** @param {HTMLElement} row */
  function rowIdentity(row) {
    if (row.dataset.treeId) {
      return row.dataset.treeId;
    }
    const kind = row.dataset.treeKind || "item";
    const value = row.dataset.path || row.dataset.pageId || "";
    return value ? `${kind}:${value}` : "";
  }

  /** @param {HTMLElement} row */
  function rowKind(row) {
    return row.dataset.treeKind || (row.classList.contains("tree-folder") ? "folder" : "file");
  }

  /** @param {HTMLElement} row */
  function isKnownEmptyFolder(row) {
    return (
      rowKind(row) === "folder" &&
      (row.classList.contains("tree-item-empty") ||
        row.dataset.treeEmpty === "true" ||
        !childGroup(row))
    );
  }

  /** @param {HTMLElement} row */
  function childGroup(row) {
    const sibling = /** @type {HTMLElement | null} */ (row.nextElementSibling);
    return hasRole(sibling, "group") ? sibling : null;
  }

  /** @param {HTMLElement} row */
  function parentRow(row) {
    const group = /** @type {HTMLElement | null} */ (row.parentElement);
    if (!group || !hasRole(group, "group")) {
      return null;
    }
    const owner = /** @type {HTMLElement | null} */ (group.previousElementSibling);
    return hasRole(owner, "treeitem") ? owner : null;
  }

  /**
   * A row is navigable only when it sits under a tree root and nothing between
   * it and the document root is hidden.
   *
   * The walk deliberately does not stop at the tree root. Panels, tab bodies,
   * and the navigation pane itself can all be hidden above it, and stopping
   * early would put rows inside a closed tab panel into the roving-focus order.
   *
   * @param {HTMLElement} row
   */
  function rowIsVisible(row) {
    if (row.hidden || row.classList.contains("tree-item-filter-hidden")) {
      return false;
    }
    let insideTree = false;
    let ancestor = /** @type {HTMLElement | null} */ (row.parentElement);
    while (ancestor) {
      if (ancestor.hidden || ancestor.style?.display === "none") {
        return false;
      }
      if (hasRole(ancestor, "tree")) {
        insideTree = true;
      }
      ancestor = /** @type {HTMLElement | null} */ (ancestor.parentElement);
    }
    return insideTree;
  }

  /** @param {HTMLElement} container */
  function readVisibleRows(container) {
    const rows = /** @type {HTMLElement[]} */ (
      Array.from(container.querySelectorAll('[role="treeitem"]'))
    );
    return rows.filter(rowIsVisible);
  }

  /** @param {HTMLElement} row */
  function firstChildRow(row) {
    const group = childGroup(row);
    if (!group || group.style.display === "none") {
      return null;
    }
    return readVisibleRows(group)[0] || null;
  }

  /** @param {HTMLElement} container @param {EventTarget | null} target */
  function treeRowFromTarget(container, target) {
    if (!target || typeof (/** @type {{closest?: unknown}} */ (target).closest) !== "function") {
      return null;
    }
    const row = /** @type {HTMLElement | null} */ (
      /** @type {Element} */ (target).closest('[role="treeitem"]')
    );
    return row && container.contains(row) ? row : null;
  }

  /** @param {HTMLElement} container @param {string} identity */
  function rowByIdentity(container, identity) {
    if (!identity) {
      return null;
    }
    return (
      /** @type {HTMLElement[]} */ (
        Array.from(container.querySelectorAll('[role="treeitem"]'))
      ).find((row) => rowIdentity(row) === identity) || null
    );
  }

  /** @param {HTMLElement} parent */
  function directTreeItems(parent) {
    return /** @type {HTMLElement[]} */ (
      Array.from(parent.children).filter((child) => hasRole(child, "treeitem"))
    );
  }

  /**
   * @param {{
   *   activate: (row: HTMLElement) => HTMLElement | null | undefined | Promise<HTMLElement | null | undefined>,
   *   container: HTMLElement,
   *   document?: Document,
   *   setFolderExpanded: (row: HTMLElement, expanded: boolean) => void | Promise<void>,
   *   shortcuts: ReturnType<Window["MetabrowserKeyboardShortcuts"]["create"]>,
   * }} options
   */
  function create(options) {
    if (
      !options?.container ||
      !options.shortcuts ||
      typeof options.activate !== "function" ||
      typeof options.setFolderExpanded !== "function"
    ) {
      throw new TypeError(
        "Tree keyboard navigation requires a container, shortcuts, activation, and folder actions",
      );
    }
    const hostDocument = options.document || window.document;
    const container = options.container;
    /** @type {HTMLElement[]} */
    let visible = [];
    /** @type {string | null} */
    let anchorIdentity = null;
    /** @type {string | null} */
    let selectedPath = null;
    /** @type {(() => void) | null} */
    let deactivateScope = null;
    /** @type {TreeMutationSnapshot | null} */
    let mutation = null;
    let disposed = false;

    function activateTreeScope() {
      if (!deactivateScope) {
        deactivateScope = options.shortcuts.activateScope("tree");
      }
    }

    function deactivateTreeScope() {
      deactivateScope?.();
      deactivateScope = null;
    }

    /** @param {HTMLElement} row @param {boolean} [focus] */
    function setAnchor(row, focus = false) {
      if (!container.contains(row) || !hasRole(row, "treeitem")) {
        return null;
      }
      anchorIdentity = rowIdentity(row);
      const allRows = /** @type {HTMLElement[]} */ (
        Array.from(container.querySelectorAll('[role="treeitem"]'))
      );
      for (const candidate of allRows) {
        candidate.setAttribute("tabindex", candidate === row ? "0" : "-1");
      }
      if (focus) {
        row.focus();
        activateTreeScope();
      }
      return row;
    }

    /** @param {HTMLElement} parent @param {number} level */
    function synchronizeBranch(parent, level) {
      const rows = directTreeItems(parent);
      for (let index = 0; index < rows.length; index += 1) {
        const row = rows[index];
        row.setAttribute("aria-level", row.dataset.treeLevel || String(level));
        row.setAttribute("aria-posinset", row.dataset.treePosition || String(index + 1));
        row.setAttribute("aria-setsize", row.dataset.treeSetSize || String(rows.length));
        const kind = rowKind(row);
        if (kind === "file" || kind === "symlink") {
          const selected = selectedPath
            ? row.dataset.path === selectedPath
            : row.classList.contains("selected");
          row.setAttribute("aria-selected", String(selected));
        } else {
          row.removeAttribute("aria-selected");
        }

        const group = childGroup(row);
        if (kind === "folder" && group && !isKnownEmptyFolder(row)) {
          row.setAttribute("aria-owns", group.id);
          const expanded = group.style.display !== "none" && !group.hidden;
          row.setAttribute("aria-expanded", String(expanded));
          synchronizeBranch(group, level + 1);
        } else if (kind === "folder") {
          row.removeAttribute("aria-owns");
          if (isKnownEmptyFolder(row)) {
            row.removeAttribute("aria-expanded");
          }
        } else {
          row.removeAttribute("aria-expanded");
          row.removeAttribute("aria-owns");
        }
      }
    }

    function prepareForMutation() {
      if (mutation) {
        return mutation;
      }
      const anchor = focusedRow();
      const parent = anchor ? parentRow(anchor) : null;
      const siblings = anchor?.parentElement ? directTreeItems(anchor.parentElement) : [];
      const index = anchor ? siblings.indexOf(anchor) : -1;
      const fallback = [];
      for (let distance = 1; index >= 0 && fallback.length < siblings.length - 1; distance += 1) {
        const next = siblings[index + distance];
        const previous = siblings[index - distance];
        if (next) {
          fallback.push(rowIdentity(next));
        }
        if (previous) {
          fallback.push(rowIdentity(previous));
        }
      }
      mutation = {
        anchor: anchorIdentity,
        hadFocus: Boolean(anchor && hostDocument.activeElement === anchor),
        parent: parent ? rowIdentity(parent) : null,
        siblings: fallback,
      };
      return mutation;
    }

    function fallbackFromPreviousSnapshot() {
      const previous = visible;
      const index = previous.findIndex((row) => rowIdentity(row) === anchorIdentity);
      if (index < 0) {
        return { parent: null, siblings: [] };
      }
      const anchor = previous[index];
      const parent = parentRow(anchor);
      const siblingIdentities = [];
      for (let distance = 1; siblingIdentities.length < previous.length - 1; distance += 1) {
        let added = false;
        for (const candidate of [previous[index + distance], previous[index - distance]]) {
          if (candidate && parentRow(candidate) === parent) {
            siblingIdentities.push(rowIdentity(candidate));
            added = true;
          }
        }
        if (!added && index + distance >= previous.length && index - distance < 0) {
          break;
        }
      }
      return { parent: parent ? rowIdentity(parent) : null, siblings: siblingIdentities };
    }

    /**
     * Preserve the durable anchor, then use its sibling and parent lineage before
     * falling back to the selected or first visible row.
     * @param {{parent: string | null, siblings: string[]}} previousFallback
     * @param {boolean} hadFocusedRow
     * @param {TreeMutationSnapshot | null} mutationSnapshot
     */
    function repairAnchor(previousFallback, hadFocusedRow, mutationSnapshot) {
      let anchor = anchorIdentity ? rowByIdentity(container, anchorIdentity) : null;
      if (!anchor || !visible.includes(anchor)) {
        const candidates = mutationSnapshot?.siblings || previousFallback.siblings;
        anchor =
          candidates
            .map((identity) => rowByIdentity(container, identity))
            .find((row) => (row ? visible.includes(row) : false)) || null;
        const parentIdentity = mutationSnapshot?.parent || previousFallback.parent;
        anchor = anchor || (parentIdentity ? rowByIdentity(container, parentIdentity) : null);
        if (anchor && !visible.includes(anchor)) {
          anchor = null;
        }
        anchor =
          anchor ||
          visible.find(
            (row) =>
              (selectedPath && row.dataset.path === selectedPath) ||
              (!selectedPath && row.classList.contains("selected")),
          ) ||
          visible[0] ||
          null;
      }
      if (anchor) {
        const shouldRepairFocus = Boolean(mutationSnapshot?.hadFocus || hadFocusedRow);
        setAnchor(anchor, shouldRepairFocus && hostDocument.activeElement !== anchor);
      } else {
        anchorIdentity = null;
      }
      return anchor;
    }

    /** @param {TreeMutationSnapshot | null} [mutationSnapshot] */
    function synchronize(mutationSnapshot = mutation) {
      const roots = /** @type {HTMLElement[]} */ (
        Array.from(container.querySelectorAll('[role="tree"]'))
      );
      for (const root of roots) {
        synchronizeBranch(root, 1);
      }
      const previousFallback = fallbackFromPreviousSnapshot();
      const hadFocusedRow = Boolean(treeRowFromTarget(container, hostDocument.activeElement));
      visible = readVisibleRows(container);
      repairAnchor(previousFallback, hadFocusedRow, mutationSnapshot);
      if (mutation === mutationSnapshot) {
        mutation = null;
      }
      return visible.slice();
    }

    function focusedRow() {
      return (
        treeRowFromTarget(container, hostDocument.activeElement) ||
        (anchorIdentity ? rowByIdentity(container, anchorIdentity) : null)
      );
    }

    function ensureVisibleRows() {
      const current = readVisibleRows(container);
      if (
        current.length !== visible.length ||
        current.some((row, index) => row !== visible[index])
      ) {
        synchronize();
      }
      return visible;
    }

    /** @param {number} index */
    function focusIndex(index) {
      const rows = ensureVisibleRows();
      if (rows.length === 0) {
        return false;
      }
      const bounded = Math.max(0, Math.min(index, rows.length - 1));
      setAnchor(rows[bounded], true);
      return true;
    }

    /** @param {number} delta */
    function move(delta) {
      const rows = ensureVisibleRows();
      const current = focusedRow();
      const index = current ? rows.indexOf(current) : -1;
      return focusIndex(index < 0 ? (delta > 0 ? 0 : rows.length - 1) : index + delta);
    }

    /** @param {HTMLElement} row @param {boolean} expanded */
    function changeFolder(row, expanded) {
      const result = options.setFolderExpanded(row, expanded);
      synchronize();
      if (result && typeof result.then === "function") {
        void result.then(() => synchronize());
      }
    }

    function parentOrCollapse() {
      const row = focusedRow();
      if (!row) {
        return false;
      }
      if (rowKind(row) === "folder" && row.getAttribute("aria-expanded") === "true") {
        changeFolder(row, false);
        return true;
      }
      const parent = parentRow(row);
      if (parent) {
        setAnchor(parent, true);
      }
      return true;
    }

    function childOrExpand() {
      const row = focusedRow();
      if (!row) {
        return false;
      }
      if (rowKind(row) !== "folder" || isKnownEmptyFolder(row)) {
        return true;
      }
      if (row.getAttribute("aria-expanded") !== "true") {
        changeFolder(row, true);
        return true;
      }
      const child = firstChildRow(row);
      if (child) {
        setAnchor(child, true);
      }
      return true;
    }

    function activateFocused() {
      const row = focusedRow();
      if (!row) {
        return false;
      }
      const result = options.activate(row);
      if (result && typeof (/** @type {PromiseLike<unknown>} */ (result).then) === "function") {
        void Promise.resolve(result).then((target) => {
          synchronize();
          if (
            target &&
            typeof (/** @type {{focus?: unknown}} */ (target).focus) === "function" &&
            container.contains(/** @type {HTMLElement} */ (target))
          ) {
            setAnchor(/** @type {HTMLElement} */ (target), true);
          }
        });
      } else {
        synchronize();
        const target = /** @type {HTMLElement | null | undefined} */ (result);
        if (target && container.contains(target)) {
          setAnchor(target, true);
        }
      }
      return true;
    }

    function registerCommands() {
      return [
        options.shortcuts.register({
          bindings: [{ key: "ArrowUp" }],
          copy: {
            action: "Previous item",
            description: "Move focus to the previous visible item in the file tree.",
            hint: "Move",
          },
          group: "navigation",
          handler: () => move(-1),
          id: "tree.previous",
          order: 10,
          repeat: true,
          scope: "tree",
          surfaces: { help: "always", nav: "active" },
        }),
        options.shortcuts.register({
          bindings: [{ key: "ArrowDown" }],
          copy: {
            action: "Next item",
            description: "Move focus to the next visible item in the file tree.",
            hint: "Move",
          },
          group: "navigation",
          handler: () => move(1),
          id: "tree.next",
          order: 20,
          repeat: true,
          scope: "tree",
          surfaces: { help: "always", nav: "active" },
        }),
        options.shortcuts.register({
          bindings: [{ key: "ArrowLeft" }],
          copy: {
            action: "Parent or collapse",
            description: "Collapse the focused folder or move focus to its parent item.",
            hint: "Navigate folders",
          },
          group: "navigation",
          handler: parentOrCollapse,
          id: "tree.parent-or-collapse",
          order: 30,
          repeat: true,
          scope: "tree",
          surfaces: { help: "always", nav: "active" },
        }),
        options.shortcuts.register({
          bindings: [{ key: "ArrowRight" }],
          copy: {
            action: "Child or expand",
            description: "Expand the focused folder or move focus to its first visible child.",
            hint: "Navigate folders",
          },
          group: "navigation",
          handler: childOrExpand,
          id: "tree.child-or-expand",
          order: 40,
          repeat: true,
          scope: "tree",
          surfaces: { help: "always", nav: "active" },
        }),
        options.shortcuts.register({
          bindings: [{ key: "Home" }],
          copy: {
            action: "First item",
            description: "Move focus to the first visible item in the file tree.",
            hint: "First",
          },
          group: "navigation",
          handler: () => focusIndex(0),
          id: "tree.first",
          order: 50,
          repeat: true,
          scope: "tree",
          surfaces: { help: "always" },
        }),
        options.shortcuts.register({
          bindings: [{ key: "End" }],
          copy: {
            action: "Last item",
            description: "Move focus to the last visible item in the file tree.",
            hint: "Last",
          },
          group: "navigation",
          handler: () => focusIndex(ensureVisibleRows().length - 1),
          id: "tree.last",
          order: 60,
          repeat: true,
          scope: "tree",
          surfaces: { help: "always" },
        }),
        options.shortcuts.register({
          bindings: [{ key: "Enter" }, { key: " " }],
          copy: {
            action: "Open or toggle",
            description: "Open the focused file, toggle the focused folder, or show the next page.",
            hint: "Open or toggle",
          },
          group: "navigation",
          handler: activateFocused,
          id: "tree.activate",
          order: 70,
          scope: "tree",
          surfaces: { help: "always", nav: "active" },
        }),
      ];
    }

    /** @param {FocusEvent} event */
    function handleFocusIn(event) {
      const row = treeRowFromTarget(container, event.target);
      if (row) {
        setAnchor(row);
        activateTreeScope();
      }
    }

    /** @param {FocusEvent} event */
    function handleFocusOut(event) {
      if (!treeRowFromTarget(container, event.relatedTarget)) {
        deactivateTreeScope();
      }
    }

    /** @param {MouseEvent} event */
    function handleClick(event) {
      const row = treeRowFromTarget(container, event.target);
      if (row) {
        setAnchor(row);
      }
    }

    const unregisterCommands = registerCommands();
    container.addEventListener("focusin", handleFocusIn);
    container.addEventListener("focusout", handleFocusOut);
    container.addEventListener("click", handleClick);
    synchronize();

    /** @param {string | null | undefined} path */
    function setSelectedPath(path) {
      selectedPath = path || null;
      synchronize();
    }

    function dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      deactivateTreeScope();
      container.removeEventListener("focusin", handleFocusIn);
      container.removeEventListener("focusout", handleFocusOut);
      container.removeEventListener("click", handleClick);
      for (const unregister of unregisterCommands) {
        unregister();
      }
      visible = [];
      mutation = null;
    }

    return Object.freeze({
      dispose,
      focusedRow,
      prepareForMutation,
      setAnchor,
      setSelectedPath,
      synchronize,
      visibleRows: () => visible.slice(),
    });
  }

  window.MetabrowserTreeKeyboardNavigation = Object.freeze({
    create,
    firstChildRow,
    parentRow,
    readVisibleRows,
    rowIdentity,
  });
})();
