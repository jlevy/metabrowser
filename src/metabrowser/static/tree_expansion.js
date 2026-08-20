// File-tree disclosure state and initial expansion planner.
//
// The shell renders root folders in source order, but expands the cheapest
// eligible folders first so the initial navigation stays within one viewport.
// Explicit expansion state is always preserved and consumes the budget before
// optional defaults are considered.

(() => {
  /**
   * @typedef {object} TreeExpansionNode
   * @property {TreeExpansionNode[] | null} [children]
   * @property {boolean} [empty]
   * @property {boolean} [expanded]
   * @property {boolean} [gitignored]
   * @property {string} name
   * @property {string} path
   * @property {string} type
   */

  const SPECIAL_FOLDER_NAMES = new Set([".logs", ".state"]);

  /** @param {number} value @param {number} fallback */
  function positiveInteger(value, fallback) {
    return Number.isFinite(value) && value > 0 ? Math.max(1, Math.floor(value)) : fallback;
  }

  /** @param {TreeExpansionNode[]} nodes @param {number} pageSize */
  function visibleRowCount(nodes, pageSize) {
    const rowCount = Math.min(nodes.length, pageSize);
    return rowCount + (nodes.length > pageSize ? 1 : 0);
  }

  /**
   * Choose folders that may open on first paint without exceeding the row budget.
   *
   * @param {TreeExpansionNode[]} nodes
   * @param {number} maxVisibleRows
   * @param {number} pageSize
   * @returns {Set<string>}
   */
  function chooseDefaultExpandedPaths(nodes, maxVisibleRows, pageSize) {
    const safePageSize = positiveInteger(pageSize, 1);
    const rowBudget = positiveInteger(maxVisibleRows, 1);
    const expandedPaths = new Set();
    let visibleRows = visibleRowCount(nodes, safePageSize);
    let candidateOrder = 0;

    /** @type {Array<{cost: number, node: TreeExpansionNode, order: number}>} */
    const candidates = [];

    /** @param {TreeExpansionNode[]} visibleNodes @param {boolean} isRoot */
    function collectVisibleCandidates(visibleNodes, isRoot) {
      const visibleCount = Math.min(visibleNodes.length, safePageSize);
      for (let index = 0; index < visibleCount; index += 1) {
        const node = visibleNodes[index];
        if (node.type !== "dir" || !Array.isArray(node.children)) {
          continue;
        }
        if (node.expanded === true) {
          visibleRows += visibleRowCount(node.children, safePageSize);
          collectVisibleCandidates(node.children, false);
          continue;
        }
        if (
          typeof node.expanded === "boolean" ||
          node.gitignored ||
          node.empty ||
          node.children.length === 0 ||
          (!isRoot && !SPECIAL_FOLDER_NAMES.has(node.name))
        ) {
          continue;
        }
        candidates.push({
          cost: visibleRowCount(node.children, safePageSize),
          node,
          order: candidateOrder,
        });
        candidateOrder += 1;
      }
    }

    collectVisibleCandidates(nodes, true);
    while (candidates.length > 0) {
      candidates.sort((left, right) => left.cost - right.cost || left.order - right.order);
      const candidate = candidates.shift();
      if (!candidate || visibleRows + candidate.cost > rowBudget) {
        continue;
      }
      expandedPaths.add(candidate.node.path);
      visibleRows += candidate.cost;
      collectVisibleCandidates(candidate.node.children || [], false);
    }

    return expandedPaths;
  }

  /**
   * Convert the tree viewport height into an approximate visible-row budget.
   *
   * @param {number} viewportHeight
   * @param {number} rowHeight
   * @param {number} fallbackRows
   * @returns {number}
   */
  function visibleRowBudget(viewportHeight, rowHeight, fallbackRows) {
    const fallback = positiveInteger(fallbackRows, 1);
    if (!Number.isFinite(viewportHeight) || viewportHeight <= 0) {
      return fallback;
    }
    if (!Number.isFinite(rowHeight) || rowHeight <= 0) {
      return fallback;
    }
    return Math.max(1, Math.floor(viewportHeight / rowHeight));
  }

  /**
   * Apply one disclosure state to both halves of a rendered folder.
   *
   * @param {HTMLElement} row
   * @param {HTMLElement} children
   * @param {boolean} expanded
   */
  function setFolderExpanded(row, children, expanded) {
    // Class-driven so the stylesheet owns the travel (the shared
    // disclosure motion); inline display would jump-cut.
    children.classList.toggle("tree-children-collapsed", !expanded);
    row.classList.toggle("expanded", expanded);
    row.classList.toggle("collapsed", !expanded);
  }

  /**
   * Toggle a rendered folder and return its new expanded state.
   *
   * @param {HTMLElement} row
   * @param {HTMLElement} children
   * @returns {boolean}
   */
  function toggleFolderExpanded(row, children) {
    const expanded = children.classList.contains("tree-children-collapsed");
    setFolderExpanded(row, children, expanded);
    return expanded;
  }

  window.MetabrowserTreeExpansion = Object.freeze({
    chooseDefaultExpandedPaths,
    setFolderExpanded,
    toggleFolderExpanded,
    visibleRowBudget,
  });
})();
