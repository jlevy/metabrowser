// The Rendered view of a changed YAML or JSON file: the structured plugin's tree, drawn
// from the server's merged tree (`structured-diff-v1`, diff/structured_projection.py),
// with each row's change in the gutter Markdown blocks use. Rows are the tree view's own
// (`renderRowHtml` and `materializeRows` of static/structured-tree.js), so a value reads as it
// does in the file view; this module only decides which rows a merged tree has, which are
// open, and what each row's change is.
//
// Paths are positional, as tree.js's are: the root's entries are "$", "$~2", and so on,
// and each child appends "/" and its position among its parent's merged entries. A
// removed key and the added key of the same name have two paths, and a path is as long
// as the tree is deep, whatever its keys hold (mb-8274 review B1 and A14).
//
// One difference from the file view (review D7): a mapping or list that is an item of a
// modified list reads `- `, where the file view gives its index (`0: `). The two sides
// number a changed list's items differently, so neither side's index names the item.
// Inside a whole added or removed value there is one side, and its items keep their
// indexes as the file view draws them.
//
// What this module reads of tree.js (`materializeRows`, `renderRowHtml`, a row's
// `change`, `text`, `hidden` and `changed`, and the "more" row) is internal to
// Metabrowser and changes with it; `renderInlineTree` stays the stable embedding contract.

/** @typedef {"context" | "modified" | "added" | "removed"} Change */
/** @typedef {{
 *   key?: string, change: Change, value?: unknown, text?: string,
 *   type?: "map" | "list", entries?: Entry[]
 * }} Entry */
/** @typedef {MetabrowserStructuredTreeRow} Row */
/** @typedef {Pick<MetabrowserStructuredExports, "materializeRows" | "calculateOptimalExpansion" | "renderRowHtml" | "expansion">} TreeHelpers */
/** @typedef {{open: Set<string>, shown: Map<string, number>, tree: TreeHelpers, current: boolean, excerpt: boolean}} View
 *   *current*: the new version alone, every removed entry left out (`diffRows`). */

// Rows the first draw mounts. In document order, a modified mapping or list opens while
// its page of rows fits, and a whole added or removed value opens as the file view would
// open it (tree.js `EXPANSION`) while its rows fit; what does not fit stays closed, with
// its change and a preview. These counts are of rows at the first draw. The 582 ready
// answers of this repository's history (explorations/structured-diff/measure.py's pairs),
// opened by initialExpansion as if the budget were unbounded, draw p50 75, p90 432 and
// p99 741 rows; all but two fit, and those two, which would draw 1,452 and 1,568 rows,
// open their first 1,000 (2026-11-18, mb-8274 review E4). Round 1 opened every change
// whole, and its largest real answer drew 2,077 rows (review C). Drawing N rows
// in headless Chrome 152 to the next frame (Apple M1 Pro, 10 cores, load average 115 to
// 117, 2026-11-18; medians of 3, `STRUCTURED_SWEEP=1` in tests/dom/diff-structured-chrome.mjs):
// 1,000 rows of numbers, strings or open records took 24 to 30 ms, and of closed records,
// each drawing its preview, 80 ms; 2,000 rows took 52 to 61 ms and 161 ms. Review A5's
// answer of 39,962 rows took 1.6 s to mount and again on every click.
export const ROW_BUDGET = 1_000;
// Children an open container draws at a time. A "more" row stands for the rest and
// draws the next page on a click; in a modified mapping or list it counts the changed
// entries it holds. Measured with ROW_BUDGET: 500 rows took 20 to 21 ms to the next
// frame, and 42 ms as closed records, whether mounted or inserted below a row as a click
// inserts them.
export const PAGE = 500;

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
  if (entry.text !== undefined && typeof entry.text !== "string") {
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

/** @param {unknown} value @returns {value is object} */
function isContainer(value) {
  return value !== null && typeof value === "object";
}

/** @param {object} value */
function childCount(value) {
  return Array.isArray(value) ? value.length : Object.keys(value).length;
}

/** @param {Entry[]} root */
function rootPaths(root) {
  return root.map((_, index) => (index === 0 ? "$" : `$~${index + 1}`));
}

/**
 * The paths a merged tree opens on its first draw, within `ROW_BUDGET` rows: modified
 * mappings and lists, and inside a whole added or removed value what the file view would
 * open. Unchanged values stay closed, as a fold of unchanged blocks does in a Markdown
 * file, and so does a whole value whose root holds more than the file view opens.
 * @param {Entry[]} root
 * @param {TreeHelpers} tree
 * @returns {Set<string>}
 */
export function initialExpansion(root, tree) {
  const { maxLines, maxExpandThreshold } = tree.expansion;
  /** @type {Set<string>} */
  const open = new Set();
  let rows = root.length;
  /** @param {Entry} entry @param {string} path */
  const visit = (entry, path) => {
    if (entry.change === "modified") {
      const children = entry.entries ?? [];
      const drawn = Math.min(children.length, PAGE);
      const cost = drawn + (drawn < children.length ? 1 : 0);
      if (rows + cost > ROW_BUDGET) {
        return;
      }
      open.add(path);
      rows += cost;
      for (let index = 0; index < drawn; index++) {
        visit(children[index], `${path}/${index}`);
      }
      return;
    }
    if (entry.change === "context" || !isContainer(entry.value)) {
      return;
    }
    const remaining = Math.min(maxLines, ROW_BUDGET - rows);
    const count = childCount(entry.value);
    if (count === 0 || count > maxExpandThreshold || count > remaining) {
      return;
    }
    const inner = tree.calculateOptimalExpansion(entry.value, {
      maxLines: remaining,
      maxExpandThreshold,
    });
    const cost = tree.materializeRows(entry.value, inner, { limit: PAGE }).length - 1;
    if (cost > remaining) {
      return;
    }
    rows += cost;
    for (const each of inner) {
      open.add(path + each.slice(1));
    }
  };
  rootPaths(root).forEach((path, index) => {
    visit(root[index], path);
  });
  return open;
}

/**
 * An entry's rows at *path*, with its view's open paths open and its pages drawn. In
 * Current a removed entry has none, and a page counts the entries Current draws.
 * @param {Entry} entry
 * @param {string} path
 * @param {number} level
 * @param {boolean} item
 * @param {View} view
 * @param {Row[]} rows
 */
function entryRows(entry, path, level, item, view, rows) {
  if (!drawsEntry(entry, view)) {
    return;
  }
  const key = entry.key ?? null;
  if (view.excerpt && entry.change === "removed") {
    rows.push({ path, level, key, isArrayIndex: item, kind: "removed", change: "removed" });
    return;
  }
  if (entry.change === "modified") {
    const children = entry.entries ?? [];
    const list = entry.type === "list";
    const expanded = view.open.has(path);
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
    if (!expanded) {
      return;
    }
    // Positions stay the merged tree's, so a path names the same entry in Diff and Current.
    /** @param {Entry} child */
    const drawsIn = (child) => drawsEntry(child, view);
    const limit = view.shown.get(path) ?? PAGE;
    let index = 0;
    for (let drawn = 0; index < children.length && drawn < limit; index++) {
      if (drawsIn(children[index])) {
        entryRows(children[index], `${path}/${index}`, level + 1, list, view, rows);
        drawn++;
      }
    }
    let hidden = 0;
    let changed = 0;
    for (; index < children.length; index++) {
      if (drawsIn(children[index])) {
        hidden++;
        changed += children[index].change === "context" ? 0 : 1;
      }
    }
    if (hidden > 0) {
      rows.push({
        path: `${path}/+`,
        level: level + 1,
        kind: "more",
        key: null,
        isArrayIndex: false,
        hidden,
        changed,
        ...(changed ? { change: "modified" } : {}),
      });
    }
    return;
  }
  const value = view.tree.materializeRows(entry.value, view.open, {
    path,
    level,
    key,
    isArrayIndex: item,
    limit: PAGE,
    shown: view.shown,
  });
  for (const row of value) {
    rows.push({ ...row, change: entry.change });
  }
  if (typeof entry.text === "string" && !isContainer(entry.value)) {
    rows[rows.length - 1].text = entry.text;
  }
}

/** @param {Entry} entry @param {View} view */
function drawsEntry(entry, view) {
  return view.excerpt ? entry.change !== "context" : !view.current || entry.change !== "removed";
}

/**
 * Draw the merged tree with each open container's children paged. Excerpt keeps only
 * changes and their ancestors and represents a removed entry with a marker.
 * @param {Entry[]} root
 * @param {Set<string>} open
 * @param {TreeHelpers} tree
 * @param {Map<string, number>} [shown]
 * @param {boolean} [current]
 * @param {boolean} [excerpt]
 * @returns {Row[]}
 */
export function diffRows(root, open, tree, shown = new Map(), current = false, excerpt = false) {
  /** @type {View} */
  const view = { open, shown, tree, current, excerpt };
  /** @type {Row[]} */
  const rows = [];
  rootPaths(root).forEach((path, index) => {
    entryRows(root[index], path, 0, false, view, rows);
  });
  return rows;
}

/**
 * The rows of the container drawn as *anchor*, the anchor's own row first: an entry of
 * the merged tree, or a mapping or list inside a whole value.
 * @param {Entry[]} root
 * @param {Row} anchor
 * @param {View} view
 * @returns {Row[]}
 */
function subtreeRows(root, anchor, view) {
  const [head, ...steps] = anchor.path.split("/");
  let entry = root[head === "$" ? 0 : Number(head.slice(2)) - 1];
  /** @type {unknown} */
  let value;
  let inside = false;
  for (const step of steps) {
    const position = Number(step);
    if (!inside && entry.change === "modified") {
      entry = (entry.entries ?? [])[position];
      continue;
    }
    if (!inside) {
      value = entry.value;
      inside = true;
    }
    const node = /** @type {Record<string, unknown>} */ (value);
    value = Array.isArray(node) ? node[position] : node[Object.keys(node)[position]];
  }
  /** @type {Row[]} */
  const rows = [];
  if (!inside) {
    entryRows(entry, anchor.path, anchor.level, anchor.isArrayIndex, view, rows);
    return rows;
  }
  for (const row of view.tree.materializeRows(value, view.open, {
    path: anchor.path,
    level: anchor.level,
    key: anchor.key,
    isArrayIndex: anchor.isArrayIndex,
    limit: PAGE,
    shown: view.shown,
  })) {
    rows.push({ ...row, change: entry.change });
  }
  return rows;
}

/** @param {Row} a @param {Row} b */
function sameRow(a, b) {
  return (
    a.path === b.path && a.kind === b.kind && a.expanded === b.expanded && a.hidden === b.hidden
  );
}

/**
 * Draw a merged tree into *container*, which the caller has emptied. A closed row opens on
 * a click, as in the file view, and a "more" row draws the next page; either replaces
 * only the rows below the container it changes.
 * @param {HTMLElement} container
 * @param {Entry[]} root
 * @param {TreeHelpers} tree
 * @param {{sourceOnly?: boolean, current?: boolean, excerpt?: boolean}} [options] *sourceOnly*: the answer's
 *   `source_only`, said in one line above the tree: that the tree shows no change, or,
 *   beside changes it draws, that Source shows one it draws as unchanged, or, for an added
 *   or a deleted file, that Source shows a value a key written again hides. *current*: the
 *   tree opens showing the new version alone (`setCurrent`).
 * @returns {{dispose: () => void, setCurrent: (next: boolean, excerpt?: boolean) => void}}
 */
export function mountStructuredDiff(container, root, tree, options = {}) {
  /** @type {View} */
  const view = {
    open: initialExpansion(root, tree),
    shown: new Map(),
    tree,
    current: options.current === true,
    excerpt: options.excerpt === true,
  };
  const indent = tree.expansion.indentChars;
  /** @param {Row[]} rows */
  const html = (rows) => rows.map((row) => tree.renderRowHtml(row, indent)).join("");
  const viewport = document.createElement("div");
  viewport.className = "tree-viewport tree-viewport-flat";
  let rows = diffRows(root, view.open, tree, view.shown, view.current, view.excerpt);
  viewport.innerHTML = html(rows);

  /**
   * Redraw the container drawn at rows[at], replacing only the rows that differ.
   * @param {number} at
   */
  const redraw = (at) => {
    const anchor = rows[at];
    let end = at + 1;
    while (end < rows.length && rows[end].level > anchor.level) {
      end++;
    }
    const fresh = subtreeRows(root, anchor, view);
    let same = 0;
    while (at + same < end && same < fresh.length && sameRow(rows[at + same], fresh[same])) {
      same++;
    }
    const start = at + same;
    /** @type {Element | null} */
    let node = viewport.children[start] ?? null;
    /** @type {Element[]} */
    const stale = [];
    for (let index = start; index < end && node; index++) {
      stale.push(node);
      node = node.nextElementSibling;
    }
    const added = html(fresh.slice(same));
    if (node) {
      node.insertAdjacentHTML("beforebegin", added);
    } else {
      viewport.insertAdjacentHTML("beforeend", added);
    }
    for (const each of stale) {
      each.remove();
    }
    rows = rows.slice(0, start).concat(fresh.slice(same), rows.slice(end));
  };

  /** @param {Event} event */
  const onClick = (event) => {
    const origin = /** @type {{closest?: (selector: string) => Element | null}} */ (event.target);
    const element = origin?.closest?.(".srow");
    const path = element?.getAttribute("data-path");
    if (!element || !path || !viewport.contains(element)) {
      return;
    }
    let at = rows.findIndex((row) => row.path === path);
    const row = rows[at];
    if (row?.kind === "more") {
      const parent = path.slice(0, -2);
      while (at >= 0 && rows[at].path !== parent) {
        at--;
      }
      if (at < 0) {
        return;
      }
      view.shown.set(parent, (view.shown.get(parent) ?? PAGE) + PAGE);
    } else if (row?.kind === "open") {
      if (view.open.has(path)) {
        view.open.delete(path);
      } else {
        view.open.add(path);
      }
    } else {
      return;
    }
    redraw(at);
  };
  viewport.addEventListener("click", onClick);
  container.classList.add("structured-tree");
  if (options.sourceOnly) {
    const note = document.createElement("p");
    note.className = "diff-structured-note";
    // An added or a deleted file is flagged only for a value a later one under the same
    // key hides, which its tree draws nowhere. Beside changes the tree draws, a value
    // whose type alone changed (a date that became a string, the key 1 that became "1")
    // is drawn unchanged.
    const whole = root.length === 1 && (root[0].change === "added" || root[0].change === "removed");
    note.textContent = whole
      ? "Source shows a value the tree does not draw: a later one under the same key hides it."
      : root.some((entry) => entry.change !== "context")
        ? "Source shows a change the tree draws as unchanged."
        : "The tree shows no change. Source shows what changed in the text.";
    container.replaceChildren(note, viewport);
  } else {
    container.replaceChildren(viewport);
  }
  return {
    dispose() {
      viewport.removeEventListener("click", onClick);
    },
    /**
     * Draw the new version alone, or the merged tree (*next* false), with what the reader
     * opened and paged still open: paths are the merged tree's in both.
     * @param {boolean} next
     */
    setCurrent(next, excerpt = false) {
      if (next === view.current && excerpt === view.excerpt) {
        return;
      }
      view.current = next;
      view.excerpt = excerpt;
      rows = diffRows(root, view.open, tree, view.shown, view.current, view.excerpt);
      viewport.innerHTML = html(rows);
    },
  };
}
