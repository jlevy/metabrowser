// The Rendered view of a changed YAML or JSON file: the structured plugin's tree, drawn
// from the server's merged tree (`structured-diff-v1`, diff/structured_projection.py),
// with each row's change in the gutter Markdown blocks use. Rows are the tree view's own
// (`renderRowHtml` and `materializeRows` of structured/tree.js), so a value reads as it
// does in the file view; this module only decides which rows a merged tree has, which are
// open, and what each row's change is.

/** @typedef {"context" | "modified" | "added" | "removed"} Change */
/** @typedef {{
 *   key?: string, change: Change, value?: unknown,
 *   type?: "map" | "list", entries?: Entry[]
 * }} Entry */
/** @typedef {MetabrowserStructuredTreeRow} Row */
/** @typedef {Pick<MetabrowserStructuredBuiltins, "materializeRows" | "calculateOptimalExpansion" | "renderRowHtml">} TreeHelpers */

// The file view's own expansion (structured/index.js): a whole added or removed value
// opens as the file view would open it.
const MAX_LINES = 500;
const MAX_EXPAND_THRESHOLD = 200;
const INDENT_CHARS = 2;

/** @param {unknown} value @returns {value is {version: string, status: string, format: string, root: Entry[], source_only: boolean}} */
export function isStructuredProjection(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const answer = /** @type {Record<string, unknown>} */ (value);
  return (
    answer.version === "structured-diff-v1" &&
    answer.status === "ready" &&
    (answer.format === "yaml" || answer.format === "json") &&
    typeof answer.source_only === "boolean" &&
    Array.isArray(answer.root) &&
    answer.root.every(isEntry)
  );
}

/** @param {unknown} value @returns {value is Entry} */
function isEntry(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const entry = /** @type {Record<string, unknown>} */ (value);
  if (entry.key !== undefined && typeof entry.key !== "string") {
    return false;
  }
  if (entry.change === "modified") {
    return (
      (entry.type === "map" || entry.type === "list") &&
      Array.isArray(entry.entries) &&
      entry.entries.every(isEntry)
    );
  }
  return (
    (entry.change === "context" || entry.change === "added" || entry.change === "removed") &&
    "value" in entry
  );
}

/**
 * The new side's value of a modified entry, which its row previews while it is closed.
 * @param {Entry} entry
 * @returns {unknown}
 */
function newValue(entry) {
  if (entry.change !== "modified") {
    return entry.value;
  }
  const shown = (entry.entries ?? []).filter((child) => child.change !== "removed");
  if (entry.type === "list") {
    return shown.map(newValue);
  }
  return Object.fromEntries(shown.map((child) => [child.key ?? "", newValue(child)]));
}

/** @param {unknown} value */
function isContainer(value) {
  return value !== null && typeof value === "object";
}

/**
 * Each entry's place: a key's under its mapping, an item's by its position, and a removed
 * entry beside an added one of the same key apart from it.
 * @param {string} parent
 * @param {Entry[]} entries
 * @param {boolean} list
 * @returns {string[]}
 */
function childPaths(parent, entries, list) {
  /** @type {Set<string>} */
  const seen = new Set();
  return entries.map((entry, index) => {
    let path = list ? `${parent}[${index}]` : `${parent}.${entry.key ?? ""}`;
    if (seen.has(path)) {
      path += "~2";
    }
    seen.add(path);
    return path;
  });
}

/**
 * The paths a merged tree opens on its first draw: every modified mapping and list, and,
 * inside a whole added or removed value, what the file view would open. Unchanged values
 * stay closed, as a fold of unchanged blocks does in a Markdown file.
 * @param {Entry[]} root
 * @param {TreeHelpers} tree
 * @returns {Set<string>}
 */
export function initialExpansion(root, tree) {
  /** @type {Set<string>} */
  const open = new Set();
  /** @param {Entry[]} entries @param {string[]} paths */
  const visit = (entries, paths) => {
    entries.forEach((entry, index) => {
      const path = paths[index];
      if (entry.change === "modified") {
        open.add(path);
        const children = entry.entries ?? [];
        visit(children, childPaths(path, children, entry.type === "list"));
      } else if (entry.change !== "context" && isContainer(entry.value)) {
        for (const inner of tree.calculateOptimalExpansion(entry.value, {
          maxLines: MAX_LINES,
          maxExpandThreshold: MAX_EXPAND_THRESHOLD,
          indentChars: INDENT_CHARS,
        })) {
          open.add(path + inner.slice(1));
        }
      }
    });
  };
  visit(root, rootPaths(root));
  return open;
}

/** @param {Entry[]} root */
function rootPaths(root) {
  return root.map((_, index) => (index === 0 ? "$" : `$~${index + 1}`));
}

/**
 * The rows a merged tree draws with *open* paths open, in document order, each with its
 * change. A whole value's rows come from the tree view's own `materializeRows`.
 * @param {Entry[]} root
 * @param {Set<string>} open
 * @param {TreeHelpers} tree
 * @returns {Row[]}
 */
export function diffRows(root, open, tree) {
  /** @type {Row[]} */
  const rows = [];
  /**
   * @param {Entry} entry
   * @param {string} path
   * @param {number} level
   * @param {boolean} item
   */
  const walk = (entry, path, level, item) => {
    const key = entry.key ?? null;
    if (entry.change === "modified") {
      const children = entry.entries ?? [];
      const list = entry.type === "list";
      const expanded = open.has(path);
      rows.push({
        path,
        level,
        kind: "open",
        key,
        isArrayIndex: item,
        isArray: list,
        childCount: children.filter((child) => child.change !== "removed").length,
        expanded,
        ...(expanded ? {} : { value: newValue(entry) }),
        change: "modified",
      });
      if (expanded) {
        const paths = childPaths(path, children, list);
        children.forEach((child, index) => {
          walk(child, paths[index], level + 1, list);
        });
      }
      return;
    }
    /** @type {Set<string>} */
    const inside = new Set();
    for (const each of open) {
      if (each === path || each.startsWith(`${path}.`) || each.startsWith(`${path}[`)) {
        inside.add(`$${each.slice(path.length)}`);
      }
    }
    const value = tree.materializeRows(entry.value, inside);
    value.forEach((row, index) => {
      const first = index === 0;
      rows.push({
        ...row,
        path: path + row.path.slice(1),
        level: row.level + level,
        ...(first
          ? {
              key,
              isArrayIndex: item,
              kind: row.kind === "kv" && item ? "item" : row.kind,
            }
          : {}),
        change: entry.change,
      });
    });
  };
  const paths = rootPaths(root);
  root.forEach((entry, index) => {
    walk(entry, paths[index], 0, false);
  });
  return rows;
}

/**
 * Draw a merged tree into *container*, which the caller has emptied; a closed row opens
 * on a click, as in the file view.
 * @param {HTMLElement} container
 * @param {Entry[]} root
 * @param {TreeHelpers} tree
 * @returns {{dispose: () => void}}
 */
export function mountStructuredDiff(container, root, tree) {
  const open = initialExpansion(root, tree);
  const viewport = document.createElement("div");
  viewport.className = "tree-viewport tree-viewport-flat";
  const draw = () => {
    viewport.innerHTML = diffRows(root, open, tree)
      .map((row) => tree.renderRowHtml(row, INDENT_CHARS))
      .join("");
  };
  /** @param {Event} event */
  const onClick = (event) => {
    const origin = /** @type {{closest?: (selector: string) => Element | null}} */ (event.target);
    const row = origin?.closest?.(".srow-container");
    const path = row?.getAttribute("data-path");
    if (!path || !viewport.contains(row ?? null)) {
      return;
    }
    if (open.has(path)) {
      open.delete(path);
    } else {
      open.add(path);
    }
    draw();
  };
  viewport.addEventListener("click", onClick);
  container.classList.add("structured-tree");
  container.replaceChildren(viewport);
  draw();
  return {
    dispose() {
      viewport.removeEventListener("click", onClick);
    },
  };
}
