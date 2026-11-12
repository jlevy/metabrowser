// A pull request's changed files under its row in the Pulls tab: the paint. Browser only.
//
// Every decision is pull-files-tree.js's, which tests/dom/github-pull-files-tree-session.js runs
// from the command line; this builds the rows it describes, draws only those near the view,
// and hands back what a reader does to them.
//
// The group follows the Files tree's row contract (docs/design-system.md, "Container Rows"):
// one `.tree-children[role="group"]` after the pull request's row, folders that lead with the
// registry's chevron in the 16 px box and file rows with the change letter a patch's children
// carry in place of an icon, the tree's indent and row height, and the inline change stats. It
// takes none of `.tree-item`, `[data-tree-id]`, or the Files tree's keyboard, which the shell
// keeps for the Files tab: these rows are the plugin's, and their keys come from the Pulls
// tab's host.
//
// The rows are one flat list in the group, each with its level, place, and set size, as a
// tree drawn a window at a time is: a list at GitHub's cap is 3,346 rows, and only those in
// the view and FILE_ROWS_OVERSCAN more each way are in the document, positioned by their index.
// The row that holds the anchor is always drawn, so focus never leaves with a scroll.
//
// A path is GitHub's users' text. Its name is painted with textContent, it reaches an address
// only through the route's encoder, and no value from GitHub reaches a class, a style, or
// markup; the only markup parsed is the shell's own chevron.
//
// A list with rows is never covered by a spinner: while its refresh is asked for or runs, the
// group carries `.mb-refreshing-group`, and the folder and file names, which are the rows'
// primary ink, breathe together (docs/design-system.md, "Refreshing Content"). The rows stay
// usable, so nothing marks them busy; the live region says what changed. The spinner is only
// for a list with no rows yet.

import { createFileTreeController, LISTING_FILES, windowRange } from "./pull-files-tree.js";
import { alignRefreshing, h, isPlainClick } from "./pull-page.js";

// Rows drawn past the view each way. Chrome 152, 2026-11-03, with a 700px nav pane:
// 67 DOM rows at the top and 111 mid-list, including the anchored row, for 1,503 real
// rows and 4,539 stress rows. Across 120 key steps, median work was 0.6 ms at both
// sizes and the maxima 4.1 and 1.4 ms. These measure navigation paint, not diff loading.
export const FILE_ROWS_OVERSCAN = 40;

/**
 * @typedef {import("./pull-files-tree.js").TreeRow} TreeRow
 * @typedef {import("./pull-files-tree.js").FileTreeModel} FileTreeModel
 * @typedef {import("./pull-files-tree.js").FilePage} FilePage
 */

/**
 * @typedef {{
 *   element: HTMLElement,
 *   at: number,
 *   content: string,
 *   folder: boolean,
 * }} DrawnRow
 */

/**
 * Mount one pull request's tree. It is attached under the row by `attach`, and survives the
 * row being built again: the list keys its rows by what they show.
 *
 * @param {{
 *   number: number,
 *   autoExpandFiles: number,
 *   current: string | null,
 *   shown: boolean,
 *   scrollRoot: HTMLElement | null,
 *   chevron: () => Node | null,
 *   href: (path: string) => string | null,
 *   request: import("./pull-files-tree.js").FileTreeDependencies["request"],
 *   formatTime: (iso: string) => string,
 *   decorateExternalLink: MetabrowserPublicSdk["decorateExternalLink"],
 *   page: () => FilePage | null,
 *   open: (route: {file: string, replace: boolean, jumped: boolean}) => void,
 *   leave: () => void,
 *   focusedIn: () => void,
 *   lastInput?: () => number | null,
 *   held?: (hold: "opening" | "lateRows", heldMs: number, outcome: string) => void,
 * }} host
 */
export function mountFileTree(host) {
  const id = `github-pull-files-${host.number}`;
  const group = h("div", {
    class: "tree-children tree-children-collapsed github-pull-files",
    role: "group",
    id,
  });
  const spinner = h("span", { class: "mb-delayed-loading", "aria-hidden": "true" }, [
    h("span", { class: "spinner spinner-sm" }),
  ]);
  const lineText = h("span");
  // Rows that came with no recent input, offered at no cost in height (LATE_ROWS_MS): on the
  // line when it is shown, and over the tree's top, floating, when it is not.
  const offer = h("button", { type: "button", class: "github-pull-text-action", hidden: "" });
  /** Whether the offer was last pressed from the keyboard, which scrolls to where focus goes. */
  let offerByKey = false;
  const line = h("p", { class: "github-pull-files-line" }, [spinner, lineText, offer]);
  const notice = h("div", { class: "github-pull-files-notice-host" });
  const list = h("div", { class: "github-pull-files-rows" });
  const live = h("span", { class: "sr-only", "aria-live": "polite" });
  group.replaceChildren(line, notice, list, live);

  /** @type {HTMLAnchorElement | null} */
  let owner = null;
  /** @type {FileTreeModel | null} */
  let model = null;
  /** @type {Map<string, DrawnRow>} */
  const drawn = new Map();
  /** @type {Map<string, number>} */
  let index = new Map();
  // Anchor settlement can remove an offscreen focused row before replacement paint.
  /** @type {HTMLElement | null} */
  let removedFocus = null;
  /** @type {HTMLElement | null} */
  let retryButton = null;
  let rowHeight = 0;
  let disposed = false;

  /** The row height the stylesheet gives every row, read once it is in the document. */
  function heightOfRow() {
    if (rowHeight <= 0) {
      const token = Number.parseFloat(getComputedStyle(list).getPropertyValue("--ui-row-height"));
      rowHeight = Number.isFinite(token) && token > 0 ? token : 0;
    }
    return rowHeight;
  }

  /** @param {TreeRow} row */
  function contentOf(row) {
    return row.kind === "folder"
      ? row.name
      : JSON.stringify([
          row.name,
          row.badge,
          row.status,
          row.additions,
          row.deletions,
          row.previousName,
        ]);
  }

  /**
   * A row's parts, which are only text and the shell's chevron.
   *
   * @param {TreeRow} row
   * @returns {Node[]}
   */
  function partsOf(row) {
    const name = h("span", { class: "github-pull-file-name mb-refreshing-text" }, [row.name]);
    if (row.kind === "folder") {
      return [
        h("span", { class: "github-pull-files-toggle", "aria-hidden": "true" }, [host.chevron()]),
        name,
      ];
    }
    const badge = h(
      "span",
      {
        class: "tree-container-badge github-pull-file-badge file-change-status",
        "data-file-status": row.status,
        "aria-hidden": "true",
      },
      [row.badge],
    );
    const parts = [badge, name];
    if (row.additions !== null || row.deletions !== null) {
      parts.push(
        h("span", { class: "github-pull-file-stats", "aria-hidden": "true" }, [
          h("span", { class: "diff-stat-add" }, [`+${row.additions ?? "?"}`]),
          h("span", { class: "diff-stat-del" }, [`−${row.deletions ?? "?"}`]),
        ]),
      );
    }
    return parts;
  }

  /**
   * What a file row is called, for a screen reader: its name, its change, and its lines.
   *
   * @param {TreeRow & {kind: "file"}} row
   */
  function nameOf(row) {
    const lines =
      row.additions === null && row.deletions === null
        ? ""
        : `, ${row.additions ?? "unknown"} added, ${row.deletions ?? "unknown"} deleted`;
    const from = row.previousName === null ? "" : `, from ${row.previousName}`;
    return `${row.name}, ${row.statusLabel.toLowerCase()}${from}${lines}`;
  }

  /**
   * The parts of a row that change while it is drawn: its place, its state, its marks.
   *
   * @param {HTMLElement} element
   * @param {TreeRow} row
   * @param {number} at
   */
  function place(element, row, at) {
    element.style.top = `${at * heightOfRow()}px`;
    element.style.setProperty("--github-pull-file-depth", String(row.depth + 1));
    element.setAttribute("tabindex", row.id === controller.anchor() ? "0" : "-1");
    element.setAttribute("aria-level", String(row.depth + 2));
    element.setAttribute("aria-posinset", String(row.position));
    element.setAttribute("aria-setsize", String(row.setSize));
    if (row.kind === "folder") {
      element.classList.toggle("expanded", row.expanded);
      element.classList.toggle("collapsed", !row.expanded);
      element.setAttribute("aria-expanded", String(row.expanded));
    } else {
      const current = row.id === controller.current();
      element.classList.toggle("selected", current);
      element.setAttribute("aria-selected", String(current));
      const muted = controller.isMuted(row.id);
      element.classList.toggle("github-pull-file-muted", muted);
      const tip = muted ? `${row.display}: not in this comparison` : row.display;
      element.dataset.tipText =
        row.previousName === null ? tip : `${tip}, from ${row.previousName}`;
    }
  }

  /**
   * @param {TreeRow} row
   * @param {number} at
   * @returns {DrawnRow}
   */
  function build(row, at) {
    const href = row.kind === "file" ? host.href(row.path) : null;
    const element = /** @type {HTMLElement} */ (
      h(
        row.kind === "file" && href !== null ? "a" : "div",
        {
          class: row.kind === "folder" ? "github-pull-folder-row" : "github-pull-file-row",
          role: "treeitem",
          tabindex: "-1",
          ...(href === null ? {} : { href }),
        },
        partsOf(row),
      )
    );
    element.dataset.id = row.id;
    if (row.kind === "file") {
      element.setAttribute("aria-label", nameOf(row));
    } else {
      element.dataset.tipText = row.name;
    }
    place(element, row, at);
    return { element, at, content: contentOf(row), folder: row.kind === "folder" };
  }

  /**
   * Draw the rows near the view, and the anchor's, in their order; leave the rest out.
   * A drawn row keeps its element, so focus on it stays.
   */
  function paintWindow() {
    if (disposed || model === null || owner === null) {
      return;
    }
    const rows = model.rows;
    // A closed tree keeps what it drew, so it opens again as it was.
    if (!model.expanded || model.opening) {
      return;
    }
    const height = host.scrollRoot === null ? 0 : heightOfRow();
    list.style.height = `${rows.length * height}px`;
    if (rows.length === 0 || height <= 0 || host.scrollRoot === null) {
      for (const entry of drawn.values()) {
        entry.element.remove();
      }
      drawn.clear();
      return;
    }
    const view = host.scrollRoot.getBoundingClientRect();
    const top = list.getBoundingClientRect().top;
    const { start, end } = windowRange({
      count: rows.length,
      rowHeight: height,
      viewTop: view.top,
      viewBottom: view.bottom,
      listTop: top,
      overscan: FILE_ROWS_OVERSCAN,
    });
    const anchorAt = (() => {
      const anchor = controller.anchor();
      return anchor === null ? undefined : index.get(anchor);
    })();
    /** @type {number[]} */
    const wanted = [];
    if (anchorAt !== undefined && anchorAt < start) {
      wanted.push(anchorAt);
    }
    for (let at = start; at < end; at += 1) {
      wanted.push(at);
    }
    if (anchorAt !== undefined && anchorAt >= end) {
      wanted.push(anchorAt);
    }
    const keep = new Set(wanted.map((at) => rows[at].id));
    for (const [rowId, entry] of drawn) {
      if (!keep.has(rowId)) {
        entry.element.remove();
        drawn.delete(rowId);
      }
    }
    // What is drawn is in the rows' order, which a change of rows keeps: a new row goes before
    // the first drawn one after it, and none that is drawn moves.
    let cursor = /** @type {HTMLElement | null} */ (list.firstElementChild);
    let built = 0;
    for (const at of wanted) {
      const row = rows[at];
      let entry = drawn.get(row.id);
      if (entry !== undefined && entry.folder !== (row.kind === "folder")) {
        entry.element.remove();
        drawn.delete(row.id);
        entry = undefined;
      }
      if (entry === undefined) {
        entry = build(row, at);
        drawn.set(row.id, entry);
        list.insertBefore(entry.element, cursor);
        built += 1;
        continue;
      }
      const content = contentOf(row);
      if (entry.content !== content) {
        entry.element.replaceChildren(...partsOf(row));
        if (row.kind === "file") {
          entry.element.setAttribute("aria-label", nameOf(row));
        }
        entry.content = content;
        built += 1;
      }
      entry.at = at;
      place(entry.element, row, at);
      if (entry.element === cursor) {
        cursor = /** @type {HTMLElement | null} */ (cursor.nextElementSibling);
      }
    }
    // A name drawn into a refreshing list joins the others' breath rather than starting its own.
    if (built > 0 && model.refreshing) {
      alignRefreshing(list);
    }
  }

  /** @param {FileTreeModel} next */
  function paint(next) {
    const focusedRetry = retryButton !== null && retryButton === document.activeElement;
    const focusedOffer = offer === document.activeElement;
    const focused =
      removedFocus ??
      (focusedRetry ? retryButton : null) ??
      [...drawn.values()].find((entry) => entry.element === document.activeElement)?.element ??
      null;
    removedFocus = null;
    const changedRows = model === null || model.rowsVersion !== next.rowsVersion;
    model = next;
    if (changedRows) {
      index = new Map(next.rows.map((row, at) => [row.id, at]));
    }
    // An opening tree stays closed for its first read, so it opens once, at its height.
    group.classList.toggle("tree-children-collapsed", !next.expanded || next.opening);
    group.setAttribute("aria-label", next.label);
    if (owner !== null) {
      owner.setAttribute("aria-expanded", String(next.expanded));
      owner.classList.toggle("expanded", next.expanded);
      owner.classList.toggle("collapsed", !next.expanded);
    }
    lineText.textContent = next.line ?? (next.loading ? LISTING_FILES : "");
    offer.textContent = next.offer ?? "";
    offer.hidden = next.offer === null;
    offer.classList.toggle("github-pull-files-offer-floating", next.offerFloats);
    const offerHome = next.offerFloats ? group : line;
    if (offer.parentNode !== offerHome) {
      offerHome.append(offer);
    }
    line.hidden = next.line === null && !next.loading && (next.offer === null || next.offerFloats);
    spinner.hidden = !next.loading;
    // The names breathe as paint; the rows stay fully usable, so the group is not marked busy.
    group.classList.toggle("mb-refreshing-group", next.refreshing);
    retryButton = null;
    if (next.notice === null) {
      notice.replaceChildren();
    } else {
      const box = h(
        "div",
        {
          class: "notice github-pull-files-notice",
          ...(next.notice.severity === null ? {} : { "data-severity": next.notice.severity }),
        },
        [h("span", {}, [next.notice.text])],
      );
      if (next.notice.help !== undefined) {
        box.append(
          host.decorateExternalLink(
            h(
              "a",
              { href: "https://cli.github.com/", target: "_blank", rel: "noopener noreferrer" },
              [next.notice.help === "install" ? "Install GitHub CLI" : "Update GitHub CLI"],
            ),
          ),
        );
      }
      if (next.notice.action !== null) {
        const press = h("button", { type: "button", class: "btn" }, ["Retry"]);
        retryButton = press;
        press.addEventListener("click", () => void controller.retry());
        box.append(press);
      }
      notice.replaceChildren(box);
    }
    if (live.textContent !== next.live) {
      live.textContent = next.live;
    }
    paintWindow();
    // A pressed offer goes as its rows are drawn: focus moves to the tree's anchor, as Right
    // takes it, and to the pull request's row when the tree has none.
    if (focusedOffer && offer.hidden) {
      const anchor = controller.anchor();
      const arriving = anchor === null ? null : drawnElement(anchor);
      if (arriving === null) {
        host.leave();
      } else {
        arriving.focus({ preventScroll: true });
        // A pointer pressed the offer where it is; only a key may have moved the reader away.
        if (offerByKey) {
          arriving.scrollIntoView({ block: "nearest" });
        }
      }
    }
    // Transfer only focus this replacement removed; an unrelated control keeps its focus.
    // The settled anchor is drawn even when it was outside the previous row window.
    if (focused !== null && !focused.isConnected && document.activeElement === document.body) {
      const anchor = controller.anchor();
      const arriving =
        (focusedRetry ? retryButton : null) ?? (anchor === null ? null : drawnElement(anchor));
      if (arriving === null) {
        host.leave();
      } else {
        arriving.focus({ preventScroll: true });
        arriving.scrollIntoView({ block: "nearest" });
      }
    }
  }

  /** @param {string} rowId */
  const drawnElement = (rowId) => drawn.get(rowId)?.element ?? null;

  const controller = createFileTreeController(
    {
      request: host.request,
      schedule: (callback, delayMs) => window.setTimeout(callback, delayMs),
      cancel: (handle) => window.clearTimeout(/** @type {number} */ (handle)),
      now: () => Date.now(),
      isVisible: () => document.visibilityState === "visible",
      formatTime: host.formatTime,
      render: paint,
      markAnchor(previous, next, focus) {
        const leaving = previous === null ? null : drawnElement(previous);
        leaving?.setAttribute("tabindex", "-1");
        if (next === null) {
          return;
        }
        const wasFocused = leaving !== null && leaving === document.activeElement;
        paintWindow();
        if (!focus && wasFocused && leaving !== null && !leaving.isConnected) {
          removedFocus = leaving;
        }
        const arriving = drawnElement(next);
        arriving?.setAttribute("tabindex", "0");
        if (arriving !== null && focus) {
          arriving.focus({ preventScroll: true });
          arriving.scrollIntoView({ block: "nearest" });
        }
      },
      markCurrent(previous, next) {
        for (const rowId of [previous, next]) {
          const at = rowId === null ? undefined : index.get(rowId);
          const element = rowId === null ? null : drawnElement(rowId);
          if (element !== null && at !== undefined && model !== null) {
            place(element, model.rows[at], at);
          }
        }
      },
      markMuted(rowId) {
        const at = index.get(rowId);
        const element = drawnElement(rowId);
        if (element !== null && at !== undefined && model !== null) {
          place(element, model.rows[at], at);
        }
      },
      page: host.page,
      open: host.open,
      routable: (path) => host.href(path) !== null,
      leave: host.leave,
      ...(host.lastInput === undefined ? {} : { lastInput: host.lastInput }),
      ...(host.held === undefined ? {} : { held: host.held }),
    },
    {
      number: host.number,
      autoExpandFiles: host.autoExpandFiles,
      current: host.current,
      shown: host.shown,
    },
  );

  const listening = new AbortController();
  const { signal } = listening;
  offer.addEventListener(
    "click",
    (event) => {
      // A click from Enter or Space has no pointer press to count.
      offerByKey = event.detail === 0;
      controller.reveal();
    },
    { signal },
  );
  /** @param {EventTarget | null} target */
  const rowOf = (target) =>
    target instanceof Element
      ? /** @type {HTMLElement | null} */ (
          target.closest(".github-pull-file-row, .github-pull-folder-row")
        )
      : null;
  list.addEventListener(
    "click",
    (event) => {
      const row = rowOf(event.target);
      if (row === null || row.dataset.id === undefined) {
        return;
      }
      // A file's new tab and copied address are the browser's own.
      if (row.tagName === "A" && !isPlainClick(event)) {
        return;
      }
      event.preventDefault();
      controller.activate(row.dataset.id);
    },
    { signal },
  );
  list.addEventListener(
    "focusin",
    (event) => {
      const row = rowOf(event.target);
      if (row !== null && row.dataset.id !== undefined) {
        controller.focused(row.dataset.id);
        host.focusedIn();
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
  host.scrollRoot?.addEventListener("scroll", onScroll, { passive: true, signal });
  const sized = typeof ResizeObserver === "function" ? new ResizeObserver(onScroll) : null;
  if (host.scrollRoot !== null) {
    sized?.observe(host.scrollRoot);
  }

  return Object.freeze({
    group,
    controller,
    /**
     * Hang the tree under a pull request's row, which a repaint of the list may build again.
     *
     * @param {HTMLElement} item
     * @param {HTMLAnchorElement} row
     */
    attach(item, row) {
      owner = row;
      row.setAttribute("aria-owns", id);
      if (model !== null) {
        row.setAttribute("aria-expanded", String(model.expanded));
        row.classList.toggle("expanded", model.expanded);
        row.classList.toggle("collapsed", !model.expanded);
      }
      if (group.parentNode !== item) {
        item.append(group);
      }
    },
    /** Release offscreen DOM while retaining logical folders, selection and cached rows. */
    detach() {
      controller.setShown(false);
      owner?.removeAttribute("aria-owns");
      owner = null;
      for (const entry of drawn.values()) {
        entry.element.remove();
      }
      drawn.clear();
      group.remove();
    },
    /** The list around it moved: draw what is in view now. */
    repaint: paintWindow,
    dispose() {
      disposed = true;
      listening.abort();
      sized?.disconnect();
      if (frame !== null) {
        window.cancelAnimationFrame(frame);
      }
      controller.dispose();
      drawn.clear();
      owner?.removeAttribute("aria-owns");
      group.remove();
    },
  });
}
