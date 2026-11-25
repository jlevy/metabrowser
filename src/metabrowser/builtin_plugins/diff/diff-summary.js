// The Diff summary's tree: a multi-file diff's changed files, by folder, under its header.
//
// A multi-file diff opens with its Diff summary, collapsed: the header diff-view.js draws in
// the toolbar ("35 files changed · 2 A, 3 D, 30 M · +1,234 −3,423"), which is the disclosure
// toggle. Opening it the first time imports this module and mounts the tree,
// so nothing of the tree exists until a reader asks for it; the header's hover or focus asks
// for the module first, since a press follows either by far longer than a local import.
//
// The tree is the one the Pulls tab draws under a pull request's row, on the same model, the
// shell's changed-files tree (static/changed-files-tree.js): folders that toggle, a chain of
// single folders drawn as one row, files with their change letter and `+A −D`, and every
// folder with the counts of the files under it rolled up, open or closed, as a Files folder
// keeps its size whichever way it is turned. Its rows are the comparison's files
// (`changeSummaryRow` in diff-model.js), so every row is one the diff holds.
//
// `createSummaryTree` is every decision without a DOM: which folders are open, the rows a
// reader sees, the row that takes Tab, and what a key or a press does; activating a file
// jumps the diff to it. tests/dom/diff-summary-session.js runs it from the command line.
// `mountSummaryTree` is the paint: the nav panel's tree rows adapted to the page, on the
// same rows, the shell's `.changed-file-row` class set (static/styles.css). Open, the tree
// has no scroll bar of its own: it is as tall as its rows and grows in the page's flow, and
// it draws only the rows in the window's view of it, and the overscan, as the Pulls tab's
// tree draws the rows in the panel's view (see SUMMARY_ROWS_OVERSCAN).
//
// The arrow keys move along the rows and never move the diff: the tree sits above the
// files, so a jump on every step would scroll it out of the reader's sight. Enter, Space,
// or a press on a file jumps; on a folder they toggle it. A host with an address for a file
// takes the jump (diff-view.js `openFile`): a pull request's page, whose header holds the
// summary on every tab, opens `/pull/<n>/files/<path>`, as the Pulls tab's tree does, and
// its diff follows the address.
//
// A path is text whoever made the change wrote: it is painted with textContent and reaches
// no class, style, or markup, and what is painted is its display, the server's rule
// (`displayPath`), with control, format, and invisible characters as U+FFFD. The only
// markup parsed is the shell's own chevron.
//
// Measured 2026-11-15 in headless Chrome 152 at 1280×900, medians of 7 loads, on this
// repository's pull request #260 as a patch (596 files, 649 rows) and on a synthetic patch of
// 2,000 files four folders deep (3,221 rows), at a load average of 12 to 39, while the opened
// tree still scrolled in a box at most 60vh tall, so the rows drawn are that box's view and
// the overscan (SUMMARY_ROWS_OVERSCAN gives the window's): the header paints in the frame
// the first file bar does, no later than the count line it replaced; a press after a hover
// drew 61 rows in 4.9 and 12.2 ms of script and showed them 16.4 and 46.8 ms after the
// press (at most 19 and 65.7), with no long task; a press with no hover, which imports this
// module itself, took 15.7 to 16.9 and 39.4 to 43.1 ms; a folder three and four levels deep
// closed and opened in 9.4 to 26.3 ms. No spinner is drawn: nothing waits long enough to
// need one. diff.summary-paint in docs/project/architecture/arch-views-models-routes.md
// records the run.

/**
 * Folders start open up to this many files, as the Pulls tab's do (`AUTO_EXPAND_FILES` in
 * builtin_plugins/github/pulls-panel.js), measured there with the same windowed paint and
 * again here: every folder of 2,000 files open opened in the times above. A comparison lists
 * at most 2,000 files (`MAX_MANIFEST_FILES` in diff/adapters/git.py), so every folder of a
 * comparison starts open.
 */
export const SUMMARY_AUTO_EXPAND_FILES = 3000;

/**
 * Rows drawn past the window's view of the tree each way, as the Pulls tab's tree draws them.
 *
 * An open tree has no bound on its length of its own and no scroll bar: it is as tall as its
 * rows, one --ui-row-height each, in the page's flow, and the document holds only the rows in
 * the window's view and this many each way. Its length is bounded by the comparison's, at
 * most 2,000 files (`MAX_MANIFEST_FILES`), a few thousand rows, tens of thousands of pixels,
 * where a browser lays out 33,554,428 (docs/large-content-rendering.md). Measured 2026-11-15
 * in headless Chrome 152 at 1280×900, at a load average of 16, five loads each, a press after
 * a hover, on synthetic patches of 106 files (133 rows, 3,197 px), 600 files (968 rows,
 * 23,237 px), and 2,000 files four folders deep (2,290 rows, 54,965 px): the rows showed 8.4
 * to 16.3, 16.2 to 19.8, and 48.3 to 57.4 ms after the press; the document held at most 116
 * rows; scrolling the page through the whole tree, 400 px and two frames a step, took the
 * two frames, 33.3 ms, at the median, and at most 33.9, 40.6, and 63.3 ms, one frame late;
 * and no task ran long.
 */
export const SUMMARY_ROWS_OVERSCAN = 40;

/**
 * @typedef {MetabrowserChangedFilesRow} SummaryRow
 * @typedef {{kind: "none"} | {kind: "moved"} | {kind: "toggled"} | {kind: "jump", path: string}} SummaryAction
 */

/**
 * One diff's summary tree, without a DOM.
 *
 * `press(id)` is a pointer's press on a row and `key(name)` a key on the tree, each answering
 * what it did: `toggled` (the rows changed), `moved` (only the row that takes Tab did),
 * `jump` (a file to show), or `none`. `focused(id)` is focus reaching a row, which takes Tab
 * and changes nothing else.
 *
 * @param {MetabrowserChangedFilesTree} tree
 * @param {ReadonlyArray<MetabrowserChangedFileRow>} files
 * @param {{autoExpandFiles?: number}} [options]
 */
export function createSummaryTree(tree, files, options = {}) {
  const built = tree.buildFileTree(files);
  let expansion = tree.expansionFor(
    built.files,
    options.autoExpandFiles ?? SUMMARY_AUTO_EXPAND_FILES,
  );
  /** @type {SummaryRow[]} */
  let rows = [];
  /** @type {Map<string, number>} */
  let index = new Map();
  let version = 0;
  /** The row that takes Tab. @type {string | null} */
  let anchor = null;

  /** The rows from the folders open; the anchor stays on its row or the folder now holding it. */
  function restate() {
    rows = tree.visibleRows(built, expansion);
    index = new Map(rows.map((row, at) => [row.id, at]));
    version += 1;
    if (anchor !== null && !index.has(anchor)) {
      const segments = anchor.replace(/\/$/, "").split("/");
      let held = null;
      for (let end = segments.length - 1; end > 0 && held === null; end -= 1) {
        const folder = `${segments.slice(0, end).join("/")}/`;
        held = index.has(folder) ? folder : null;
      }
      anchor = held;
    }
    anchor ??= rows[0]?.id ?? null;
  }
  restate();

  /** @param {SummaryRow} row @returns {SummaryAction} */
  function toggle(row) {
    if (row.kind !== "folder") {
      return { kind: "none" };
    }
    expansion = tree.toggleFolder(expansion, row);
    restate();
    return { kind: "toggled" };
  }

  /** @param {SummaryRow} row @returns {SummaryAction} */
  function activateRow(row) {
    return row.kind === "folder" ? toggle(row) : { kind: "jump", path: row.path };
  }

  /** @param {number} at @returns {SummaryAction} */
  function moveTo(at) {
    const row = rows[Math.max(0, Math.min(rows.length - 1, at))];
    if (row === undefined || row.id === anchor) {
      return { kind: "none" };
    }
    anchor = row.id;
    return { kind: "moved" };
  }

  return Object.freeze({
    rows: () => rows,
    version: () => version,
    anchor: () => anchor,
    files: () => built.files,
    /** @param {string} id */
    indexOf: (id) => index.get(id),
    /** @param {string} id */
    focused(id) {
      if (index.has(id)) {
        anchor = id;
      }
    },
    /**
     * A pointer pressed a row: a folder toggles and a file is jumped to.
     *
     * @param {string} id
     * @returns {SummaryAction}
     */
    press(id) {
      const at = index.get(id);
      if (at === undefined) {
        return { kind: "none" };
      }
      anchor = id;
      return activateRow(rows[at]);
    },
    /**
     * A key on the tree, by its `KeyboardEvent.key`; a key held with Command, Control, or
     * Option never reaches here (the paint's guard).
     *
     * @param {string} key
     * @returns {SummaryAction | null} Null for a key the tree does not take.
     */
    key(key) {
      const at = anchor === null ? undefined : index.get(anchor);
      if (at === undefined) {
        return null;
      }
      const row = rows[at];
      switch (key) {
        case "ArrowDown":
          return moveTo(at + 1);
        case "ArrowUp":
          return moveTo(at - 1);
        case "Home":
          return moveTo(0);
        case "End":
          return moveTo(rows.length - 1);
        case "ArrowRight": {
          // A closed folder opens; an open one goes to its first row.
          if (row.kind !== "folder") {
            return { kind: "none" };
          }
          if (!row.expanded) {
            return toggle(row);
          }
          const child = rows[at + 1];
          return child !== undefined && child.depth > row.depth ? moveTo(at + 1) : { kind: "none" };
        }
        case "ArrowLeft": {
          // An open folder closes; anything else goes to the folder that holds it.
          if (row.kind === "folder" && row.expanded) {
            return toggle(row);
          }
          const parent = tree.parentIndex(rows, at);
          return parent === null ? { kind: "none" } : moveTo(parent);
        }
        case "Enter":
        case " ":
          return activateRow(row);
        default:
          return null;
      }
    },
    snapshot: () => ({ rows: rows.length, anchor, version }),
  });
}

/** An `overflow` that makes a box cut what is inside it from view. */
const CLIPS = /^(?:auto|scroll|hidden|clip|overlay)$/;

/**
 * Which rows of a windowed tree are in the document, in their order: those *range* holds,
 * the rows in the window's view and its overscan (`windowRange` of the shared tree), and the
 * row that takes Tab wherever it is, so focus never leaves with a scroll. Pure.
 *
 * @param {{start: number, end: number}} range
 * @param {number | undefined} anchorAt The row that takes Tab, by index.
 * @returns {number[]}
 */
export function rowsToDraw(range, anchorAt) {
  /** @type {number[]} */
  const wanted = [];
  if (anchorAt !== undefined && anchorAt < range.start) {
    wanted.push(anchorAt);
  }
  for (let at = range.start; at < range.end; at += 1) {
    wanted.push(at);
  }
  if (anchorAt !== undefined && anchorAt >= range.end) {
    wanted.push(anchorAt);
  }
  return wanted;
}

/**
 * @param {string} tag
 * @param {Record<string, string>} attributes
 * @param {Array<Node | string>} [children]
 */
function h(tag, attributes, children = []) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    element.setAttribute(name, value);
  }
  element.append(...children);
  return element;
}

/**
 * Mount one diff's summary tree, collapsed, for its header to open. Its box is the
 * header's to place, right after the toolbar.
 *
 * @param {{
 *   tree: MetabrowserChangedFilesTree,
 *   files: ReadonlyArray<MetabrowserChangedFileRow>,
 *   id: string,
 *   formatCount: (count: number) => string,
 *   chevron: () => Node | null,
 *   jump: (path: string) => void,
 *   marks?: (path: string) => Node[],
 * }} host
 */
export function mountSummaryTree(host) {
  const model = createSummaryTree(host.tree, host.files);
  const list = h("div", { class: "diff-summary-rows" });
  const body = h(
    "div",
    {
      class: "diff-summary-body diff-summary-body-collapsed",
      id: host.id,
      role: "tree",
      "aria-label": "Changed files",
    },
    [list],
  );
  /** @type {Map<string, {element: HTMLElement, content: string}>} */
  const drawn = new Map();
  let rowHeight = 0;
  let open = false;
  let disposed = false;
  let drawnVersion = -1;

  function heightOfRow() {
    if (rowHeight <= 0) {
      const token = Number.parseFloat(getComputedStyle(list).getPropertyValue("--ui-row-height"));
      rowHeight = Number.isFinite(token) && token > 0 ? token : 0;
    }
    return rowHeight;
  }

  /** @param {SummaryRow} row */
  const contentOf = (row) =>
    JSON.stringify(
      row.kind === "folder"
        ? [row.name, row.expanded, row.additions, row.deletions]
        : [row.name, row.badge, row.additions, row.deletions],
    );

  /** @param {SummaryRow} row @returns {Node[]} */
  function statsOf(row) {
    const stats = host.tree.changeStats(row, host.formatCount);
    return stats === null
      ? []
      : [
          h("span", { class: "changed-file-stats", "aria-hidden": "true" }, [
            h("span", { class: "diff-stat-add" }, [stats.additions]),
            h("span", { class: "diff-stat-del" }, [stats.deletions]),
          ]),
        ];
  }

  /** @param {SummaryRow} row @returns {Node[]} */
  function partsOf(row) {
    const name = h("span", { class: "changed-file-name" }, [row.name]);
    if (row.kind === "folder") {
      const chevron = host.chevron();
      return [
        h(
          "span",
          { class: "changed-file-toggle", "aria-hidden": "true" },
          chevron === null ? [] : [chevron],
        ),
        name,
        ...statsOf(row),
      ];
    }
    const badge = h(
      "span",
      {
        class: "tree-container-badge file-change-status",
        "data-file-status": row.status,
        "aria-hidden": "true",
      },
      [row.badge],
    );
    return [badge, name, ...statsOf(row), ...(host.marks?.(row.path) ?? [])];
  }

  /**
   * @param {HTMLElement} element
   * @param {SummaryRow} row
   * @param {number} at
   */
  function place(element, row, at) {
    element.style.top = `${at * heightOfRow()}px`;
    element.style.setProperty("--diff-summary-depth", String(row.depth));
    element.setAttribute("tabindex", row.id === model.anchor() ? "0" : "-1");
    element.setAttribute("aria-level", String(row.depth + 1));
    element.setAttribute("aria-posinset", String(row.position));
    element.setAttribute("aria-setsize", String(row.setSize));
    element.setAttribute("aria-label", host.tree.rowLabel(row, host.formatCount));
    if (row.kind === "folder") {
      element.classList.toggle("expanded", row.expanded);
      element.classList.toggle("collapsed", !row.expanded);
      element.setAttribute("aria-expanded", String(row.expanded));
      // The tooltip says what the folder's sums leave out, the counts alone, as its
      // accessible name does, and nothing when they leave nothing out: its name is on the row
      // already (docs/design-system.md, "Tooltips Add Information").
      const missing = host.tree.missingCounts(row, host.formatCount);
      if (missing === "") {
        delete element.dataset.tipText;
      } else {
        element.dataset.tipText = missing;
      }
    } else {
      element.dataset.tipText =
        row.previousName === null ? row.display : `${row.display}, from ${row.previousName}`;
    }
  }

  /** @param {SummaryRow} row @param {number} at */
  function build(row, at) {
    const element = h(
      "div",
      {
        class:
          row.kind === "folder"
            ? "changed-file-row diff-summary-row diff-summary-folder disclosure-toggle"
            : "changed-file-row diff-summary-row diff-summary-file",
        role: "treeitem",
      },
      partsOf(row),
    );
    element.dataset.id = row.id;
    place(element, row, at);
    return { element, content: contentOf(row) };
  }

  /**
   * The part of the window the tree can be seen through, in client coordinates: the window,
   * cut by every box above the tree that scrolls or clips, such as the pane the page scrolls.
   * @returns {{top: number, bottom: number}}
   */
  function viewOf() {
    let top = 0;
    let bottom =
      typeof window.innerHeight === "number" ? window.innerHeight : Number.POSITIVE_INFINITY;
    for (let node = body.parentElement; node; node = node.parentElement) {
      if (CLIPS.test(getComputedStyle(node).overflowY ?? "")) {
        const box = node.getBoundingClientRect();
        top = Math.max(top, box.top);
        bottom = Math.min(bottom, box.bottom);
      }
    }
    return { top, bottom };
  }

  /** The window last drawn, so a scroll that moves no row draws nothing again. */
  let drawnWindow = "";

  /** Draw the rows in the window's view, and the anchor's, in order; leave the rest out. */
  function paintWindow() {
    if (disposed || !open) {
      return;
    }
    const rows = model.rows();
    const height = heightOfRow();
    list.style.height = `${rows.length * height}px`;
    if (height <= 0) {
      return;
    }
    const view = viewOf();
    const { start, end } = host.tree.windowRange({
      count: rows.length,
      rowHeight: height,
      viewTop: view.top,
      viewBottom: view.bottom,
      listTop: list.getBoundingClientRect().top,
      overscan: SUMMARY_ROWS_OVERSCAN,
    });
    const anchor = model.anchor();
    const anchorAt = anchor === null ? undefined : model.indexOf(anchor);
    const shown = `${model.version()} ${start} ${end} ${anchorAt}`;
    if (shown === drawnWindow) {
      return;
    }
    drawnWindow = shown;
    const wanted = rowsToDraw({ start, end }, anchorAt);
    const keep = new Set(wanted.map((at) => rows[at].id));
    for (const [id, entry] of drawn) {
      if (!keep.has(id)) {
        entry.element.remove();
        drawn.delete(id);
      }
    }
    let cursor = /** @type {HTMLElement | null} */ (list.firstElementChild);
    for (const at of wanted) {
      const row = rows[at];
      let entry = drawn.get(row.id);
      if (entry === undefined) {
        entry = build(row, at);
        drawn.set(row.id, entry);
        list.insertBefore(entry.element, cursor);
        continue;
      }
      const content = contentOf(row);
      if (entry.content !== content) {
        entry.element.replaceChildren(...partsOf(row));
        entry.content = content;
      }
      place(entry.element, row, at);
      if (entry.element === cursor) {
        cursor = /** @type {HTMLElement | null} */ (cursor.nextElementSibling);
      }
    }
    drawnVersion = model.version();
  }

  /** Focus the row that takes Tab, drawn, and in the window's view. */
  function focusAnchor() {
    const anchor = model.anchor();
    const element = anchor === null ? null : (drawn.get(anchor)?.element ?? null);
    element?.focus({ preventScroll: true });
    element?.scrollIntoView({ block: "nearest" });
  }

  /** @param {SummaryAction | null} action @returns {boolean} Whether it did anything. */
  function follow(action) {
    if (action === null) {
      return false;
    }
    if (action.kind === "jump") {
      host.jump(action.path);
    } else if (action.kind === "toggled" || action.kind === "moved") {
      paintWindow();
    }
    return true;
  }

  const listening = new AbortController();
  const { signal } = listening;
  /** @param {EventTarget | null} target */
  const rowOf = (target) =>
    target instanceof Element
      ? /** @type {HTMLElement | null} */ (target.closest(".diff-summary-row"))
      : null;
  list.addEventListener(
    "click",
    (event) => {
      const row = rowOf(event.target);
      if (row?.dataset.id !== undefined) {
        follow(model.press(row.dataset.id));
        if (model.anchor() === row.dataset.id) {
          drawn.get(row.dataset.id)?.element.focus({ preventScroll: true });
        }
      }
    },
    { signal },
  );
  list.addEventListener(
    "focusin",
    (event) => {
      const row = rowOf(event.target);
      if (row?.dataset.id !== undefined && model.anchor() !== row.dataset.id) {
        const previous = model.anchor();
        model.focused(row.dataset.id);
        if (previous !== null) {
          drawn.get(previous)?.element.setAttribute("tabindex", "-1");
        }
        row.setAttribute("tabindex", "0");
      }
    },
    { signal },
  );
  list.addEventListener(
    "keydown",
    (event) => {
      if (event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      const action = model.key(event.key);
      if (follow(action)) {
        event.preventDefault();
        if (action?.kind !== "jump") {
          focusAnchor();
        }
      }
    },
    { signal },
  );
  /** @type {number | null} */
  let frame = null;
  const onScroll = () => {
    if (frame === null) {
      frame = window.requestAnimationFrame(() => {
        frame = null;
        paintWindow();
      });
    }
  };
  // The tree has no scroll of its own: the window's view of it moves when the page, or any
  // box above it, scrolls, which a listener on the document hears in its capture phase, and
  // when the window or the tree changes size. A scroll of a box that does not hold the tree,
  // a Split diff's code or the navigation pane, cannot move that view, so it draws nothing.
  /** @param {Event} event */
  const onPageScroll = (event) => {
    const target = event.target;
    if (target === document || (target instanceof Node && target.contains(body))) {
      onScroll();
    }
  };
  document.addEventListener("scroll", onPageScroll, { capture: true, passive: true, signal });
  window.addEventListener("resize", onScroll, { passive: true, signal });
  const sized = typeof ResizeObserver === "function" ? new ResizeObserver(onScroll) : null;
  sized?.observe(body);

  return Object.freeze({
    body,
    model,
    /**
     * Open or close the tree. It opens at its height in one travel, its first rows drawn
     * before it does, and closing keeps what it drew.
     *
     * @param {boolean} next
     */
    setOpen(next) {
      if (disposed || next === open) {
        return;
      }
      open = next;
      if (open) {
        paintWindow();
        // The box travels from its collapsed height, as every disclosure does.
        void body.offsetHeight;
      }
      body.classList.toggle("diff-summary-body-collapsed", !open);
    },
    isOpen: () => open,
    /** The rows drawn, for a check that the window holds. */
    drawnRows: () => drawn.size,
    drawnVersion: () => drawnVersion,
    dispose() {
      disposed = true;
      listening.abort();
      sized?.disconnect();
      if (frame !== null) {
        window.cancelAnimationFrame(frame);
      }
      drawn.clear();
      body.remove();
    },
  });
}
