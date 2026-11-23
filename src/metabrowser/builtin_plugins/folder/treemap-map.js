// Folder treemap map: the drawn cells of a rollup tree.
//
// The map behind the Treemap view (treemap.js). It owns the cells and
// everything a cell does — layout through treemap-layout.js, labels,
// tooltip, pointer and keyboard activation, and the hover the map shares
// with its tally bars and legend — and nothing about where the rollup comes
// from or what surrounds the map. Its host hands it a node and asks for a
// layout; the map measures its own drawable box.

import { layoutTree } from "./treemap-layout.js";

/** @typedef {{classFor: (key: string) => string, styleFor: (key: string) => string, paint: (element: HTMLElement, key: string) => void}} TreemapPalette */
/** @typedef {{metric: "size" | "files", includeIgnored: boolean}} TreemapState */
/** @typedef {import("./distribution-hover.js").DistributionHover} DistributionHover */
/** @typedef {import("./distribution-hover.js").DistributionHoverTarget} DistributionHoverTarget */

/**
 * Size presets. `layout` overrides LAYOUT_DEFAULTS (treemap-layout.js); the
 * label bounds are paint thresholds, since type size itself comes from cell
 * geometry.
 */
const SIZE_PRESETS = Object.freeze({
  full: Object.freeze({
    layout: Object.freeze({}),
    labelMinW: 56,
    labelMinH: 16,
    values: true,
    restLabels: true,
  }),
});

/**
 * The rollup a treemap requests: the deepest tree the server returns, with
 * the most children per folder (ROLLUP_MAX_DEPTH and ROLLUP_MAX_TOP,
 * settings.py). The server's node budget, not these, bounds the response, and
 * the layout folds whatever has no room into remainder cells. A page without
 * the settings asks for the server's defaults.
 * @returns {{depth?: number, top?: number}}
 */
export function treemapRollupQuery() {
  const settings = window.METABROWSER_SETTINGS;
  /** @type {{depth?: number, top?: number}} */
  const query = {};
  if (typeof settings?.ROLLUP_MAX_DEPTH === "number") {
    query.depth = settings.ROLLUP_MAX_DEPTH;
  }
  if (typeof settings?.ROLLUP_MAX_TOP === "number") {
    query.top = settings.ROLLUP_MAX_TOP;
  }
  return query;
}

/**
 * @typedef {object} TreemapMapOptions
 * @property {"full"} [size]
 * @property {() => TreemapState} getState
 * @property {(cell: Record<string, any>) => void} onActivate  a folder or file cell was chosen
 * @property {DistributionHover} [hover]  the hover the map shares with its bars and legend
 * @property {() => void} [onParent]  Backspace asks for the enclosing folder
 */

/**
 * Mount a treemap map on `viewport`, which the map fills with cells.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {TreemapPalette} palette
 * @param {HTMLElement} viewport
 * @param {TreemapMapOptions} options
 */
export function createTreemapMap(mb, palette, viewport, options) {
  const preset = SIZE_PRESETS[options.size ?? "full"];
  const hover = options.hover ?? null;
  /** @type {Record<string, any>[]} */
  let cells = [];
  /** @type {number[]} */
  let actionableIndexes = [];
  let focusPos = 0;
  let disposed = false;
  /** The hover the cell under the pointer entered, until the pointer leaves the cell. */
  /** @type {DistributionHoverTarget | null} */
  let cellHover = null;
  /** @type {Array<HTMLElement>} */
  let hoveredCells = [];

  /**
   * The distribution key for a cell: the family behind a file's extension, and
   * the neutral fallback for the remainder cell that stands for what did not
   * fit.
   * @param {Record<string, any>} cell
   * @returns {string}
   */
  function cellPaletteKey(cell) {
    const extension = cell.ext || "(none)";
    return cell.kind === "rest" ? "" : mb.fileTypes.distributionKeyForExtension(extension);
  }

  /** @param {Record<string, any>} cell @returns {boolean} */
  function cellIsActionable(cell) {
    return cell.kind === "dir" || cell.kind === "file";
  }

  /** @param {Record<string, any>} cell @param {TreemapState} state */
  function cellClasses(cell, state) {
    const cls = [
      "tm-cell",
      `tm-${cell.kind}`,
      "tm-type-fill",
      palette.classFor(cellPaletteKey(cell)),
    ];
    if (cellIsActionable(cell)) {
      cls.push("tm-actionable");
    }
    if (cell.gitignored && state.includeIgnored) {
      cls.push("tm-ignored");
    }
    if (cell.state === "pending") {
      cls.push("tm-pending");
    }
    if (cell.nested) {
      cls.push("tm-nested");
    }
    if (cell.framed) {
      cls.push("tm-framed");
    }
    return cls.join(" ");
  }

  /**
   * Value phrase for a cell: aggregate cells follow the active metric;
   * file leaves retain their more useful byte size in both modes.
   * @param {Record<string, any>} cell
   * @param {TreemapState} state
   * @returns {string}
   */
  function cellValueText(cell, state) {
    // One file is already obvious from a leaf rectangle. Its byte size
    // remains useful in either area mode; folders and remainder cells
    // report the active metric because their count is aggregate data.
    if (cell.kind === "file") {
      return mb.formatSize(cell.bytes ?? cell.value);
    }
    if (state.metric === "files") {
      return mb.formatFileCount(cell.files ?? cell.value);
    }
    return mb.formatSize(cell.bytes ?? cell.value);
  }

  /**
   * @param {Record<string, any>} cell
   * @param {TreemapState} state
   * @returns {string}
   */
  function cellAriaLabel(cell, state) {
    if (cell.kind === "rest") {
      return `${mb.formatFileCount(cell.files || 0)} represented by the remainder, ${cellValueText(cell, state)}`;
    }
    const what = cell.kind === "dir" ? "folder" : "file";
    return `${cell.name} (${what}, ${cellValueText(cell, state)})`;
  }

  /**
   * @param {Record<string, any>} cell
   * @param {TreemapState} state
   * @param {number} index
   */
  function cellHtml(cell, state, index) {
    const style =
      `left:${cell.x.toFixed(1)}px;top:${cell.y.toFixed(1)}px;` +
      `width:${Math.max(0, cell.w - 1).toFixed(1)}px;height:${Math.max(0, cell.h - 1).toFixed(1)}px;` +
      `--tm-label-size:${cell.labelPx}px;--tm-value-size:${cell.valuePx}px;`;
    const labelLineHeight = cell.labelPx * 1.2;
    const valueLineHeight = cell.valuePx * 1.2;
    // A framed folder's children cover its whole interior, so it has no
    // room for a label; the tooltip names it.
    const showLabel =
      !cell.framed &&
      (preset.restLabels || cell.kind !== "rest") &&
      cell.w >= preset.labelMinW &&
      cell.h >= Math.max(preset.labelMinH, labelLineHeight + 2);
    // Nested parents suppress the sublabel: the reserved header strip
    // is one line tall, and a second line would overlap child cells.
    const showStackedSub =
      preset.values &&
      showLabel &&
      cell.h >= labelLineHeight + valueLineHeight + 6 &&
      cell.kind !== "rest" &&
      !cell.nested;
    const showInlineSub =
      preset.values && showLabel && cell.nested && cell.kind === "dir" && cell.w >= 140;
    const sub = cellValueText(cell, state);
    const aria = mb.escapeHtml(cellAriaLabel(cell, state));
    const actionable = cellIsActionable(cell);
    // A nested directory cell contains its children's cells, so the
    // cell itself stays a group and its label is the keyboard control.
    // Pointer routing uses the deepest outer cell instead, avoiding a
    // nested button tree without shrinking the hit target to the label.
    // A framed folder has no label, so its own cell stays the control.
    const titleInteractive = actionable && cell.nested && showLabel;
    const titleAttrs = titleInteractive
      ? ` role="button" tabindex="-1" data-tm-index="${index}" aria-label="${aria}"`
      : "";
    const visibleName = cell.kind === "dir" ? `${cell.name}/` : cell.name;
    const fileIcon = showLabel && cell.kind === "file" ? mb.fileTypeIcon(cell.name) : null;
    const fileIconHtml = fileIcon?.svg
      ? `<span class="file-identity-icon tm-cell-file-icon ${mb.escapeHtml(fileIcon.className)}" aria-hidden="true">${fileIcon.svg}</span>`
      : "";
    const label = showLabel
      ? `<span class="tm-cell-title"${titleAttrs}>${fileIconHtml}<span class="tm-cell-label">${mb.escapeHtml(visibleName)}</span>${
          showInlineSub
            ? `<span class="tm-cell-sub tm-cell-sub-inline">${mb.escapeHtml(sub)}</span>`
            : ""
        }</span>${showStackedSub ? `<span class="tm-cell-sub">${mb.escapeHtml(sub)}</span>` : ""}`
      : "";
    const outerInteractive = actionable && !titleInteractive;
    const outerAttrs = outerInteractive
      ? ` role="button" tabindex="-1" data-tm-index="${index}" aria-label="${aria}"`
      : ` role="group" aria-label="${aria}"`;
    return (
      `<div class="${cellClasses(cell, state)}"${outerAttrs}` +
      ` data-tm-cell="${index}" data-tm-kind="${cell.kind}" data-tm-path="${mb.escapeHtml(cell.path)}"` +
      ` style="${style}${palette.styleFor(cellPaletteKey(cell))}">${label}</div>`
    );
  }

  /**
   * @param {Record<string, any>} cell
   * @param {TreemapState} state
   * @returns {string}
   */
  function tooltipHtml(cell, state) {
    const rows = [];
    if (cell.kind === "rest") {
      rows.push(`<strong>${mb.formatFileCount(cell.files || 0)} in the remainder</strong>`);
      rows.push(cellValueText(cell, state));
    } else {
      const pathLabel =
        window.MetabrowserNavigationRoute?.displayPath?.(cell.path || "", mb.sourceKind()) ||
        cell.path ||
        cell.name;
      rows.push(`<strong>${mb.escapeHtml(pathLabel)}</strong>`);
      rows.push(`${mb.formatFileCount(cell.files || 0)} · ${mb.formatSize(cell.bytes || 0)}`);
      if (typeof cell.mtime === "number" && cell.mtime > 0) {
        rows.push(`modified ${mb.formatTimestamp(cell.mtime)}`);
      }
      if (cell.gitignored) {
        rows.push("gitignored");
      }
      if (cell.state === "pending") {
        rows.push("still scanning");
      }
    }
    return rows.join("<br>");
  }

  /**
   * The box cells are laid out in: the viewport's padding box, inside its
   * border, which is what absolutely positioned cells are placed against.
   * The border box is larger by the border, and laying out to it pushed
   * every right- and bottom-edge cell under the viewport's clipping edge.
   * A host without layout metrics (the vm harness) falls back to the
   * bounding rectangle, or to no box at all.
   * @returns {{w: number, h: number}}
   */
  function drawableBox() {
    if (typeof viewport.getBoundingClientRect !== "function") {
      return { w: 0, h: 0 };
    }
    const rect = viewport.getBoundingClientRect();
    const clientW = Number(viewport.clientWidth);
    const clientH = Number(viewport.clientHeight);
    return {
      w: Number.isFinite(clientW) && clientW > 0 ? clientW : rect.width,
      h: Number.isFinite(clientH) && clientH > 0 ? clientH : rect.height,
    };
  }

  /**
   * Draw the hover on the map's cells: a legend entry's hover marks every cell of its
   * family, the files of its types and the folders it is the dominant type of, the cells
   * it colors, as `family`; a cell's own hover marks that cell as `self`. The legend
   * marks its entry and the tally bars their segments (distribution-legend.js,
   * folder-totals.js). Every marked cell lifts, and none grows, since a cell's area is
   * its value; only the cell under the pointer shimmers, because a family can hold
   * every cell the map draws and each shimmering cell is a layer of its own
   * (styles.css, beside the rule; docs/design-system.md, "Folder Treemap").
   */
  function drawCellHover() {
    for (const element of hoveredCells) {
      delete element.dataset.hovered;
    }
    hoveredCells = [];
    const target = hover?.current();
    // A map with no cells drawn yet has nothing to mark.
    if (!target || cells.length === 0) {
      return;
    }
    if (target.marks === "self") {
      const own = cellElementFor(target.anchor);
      if (own === target.anchor && viewport.contains(own)) {
        own.dataset.hovered = "self";
        hoveredCells.push(own);
      }
      return;
    }
    for (const element of /** @type {NodeListOf<HTMLElement>} */ (
      viewport.querySelectorAll("[data-tm-cell]")
    )) {
      const cell = cells[Number(element.dataset.tmCell)];
      if (cell && cellPaletteKey(cell) === target.key) {
        element.dataset.hovered = "family";
        hoveredCells.push(element);
      }
    }
  }
  const unsubscribeCellHover = hover ? hover.subscribe(drawCellHover) : () => {};

  /**
   * Let go of the hover the cell under the pointer entered, as a layout replaces the
   * cell or the pointer leaves it: a removed element never hears the pointer leave it.
   */
  function releaseCellHover() {
    if (cellHover && hover) {
      hover.leave(cellHover);
    }
    cellHover = null;
  }

  /**
   * The cell element under `el`, which is what a tooltip anchors to.
   * Every cell carries data-tm-cell.
   * @param {Element | null} el
   */
  function cellElementFor(el) {
    return el ? /** @type {HTMLElement | null} */ (el.closest("[data-tm-cell]")) : null;
  }

  /**
   * Cell record for hover/tooltip lookup.
   * @param {Element | null} el
   * @returns {Record<string, any> | null}
   */
  function cellForElement(el) {
    const host = cellElementFor(el);
    if (!host) {
      return null;
    }
    const idx = Number(host.dataset.tmCell);
    return Number.isInteger(idx) && idx >= 0 && idx < cells.length ? cells[idx] : null;
  }

  /** @param {number} nextPos position within actionableIndexes */
  function moveFocus(nextPos) {
    if (nextPos < 0 || nextPos >= actionableIndexes.length) {
      return;
    }
    const prev = viewport.querySelector(`[data-tm-index="${actionableIndexes[focusPos]}"]`);
    if (prev) {
      prev.setAttribute("tabindex", "-1");
    }
    focusPos = nextPos;
    const next = /** @type {HTMLElement | null} */ (
      viewport.querySelector(`[data-tm-index="${actionableIndexes[focusPos]}"]`)
    );
    if (next) {
      next.setAttribute("tabindex", "0");
      next.focus();
    }
  }

  /** @param {Event} e */
  function onClick(e) {
    const cell = cellForElement(/** @type {Element} */ (e.target));
    if (cell && cellIsActionable(cell)) {
      options.onActivate(cell);
    }
  }
  // One delegated pair for the whole map. mouseover fires again for every
  // descendant the pointer crosses inside a cell, so the tooltip is anchored
  // to the cell's own element: re-announcing the same anchor holds it still,
  // and crossing into a different cell replaces it.
  //
  // The cell also says where the pointer is to the hover the map shares with its bars
  // and legend, once per cell: crossing a cell's own label is not leaving it.
  /** @param {Event} e */
  function onMouseOver(e) {
    const host = cellElementFor(/** @type {Element} */ (e.target));
    const cell = cellForElement(/** @type {Element} */ (e.target));
    if (!host || !cell) {
      return;
    }
    const state = options.getState();
    mb.tooltip.show(tooltipHtml(cell, state), host);
    if (hover && cellHover?.anchor !== host) {
      releaseCellHover();
      /** @type {DistributionHoverTarget} */
      const target = Object.freeze({
        population: state.includeIgnored ? "all" : "files",
        key: cellPaletteKey(cell),
        anchor: host,
        marks: /** @type {const} */ ("self"),
      });
      cellHover = target;
      hover.enter(target);
    }
  }
  /** @param {MouseEvent} e */
  function onMouseOut(e) {
    mb.tooltip.hide();
    if (
      cellHover &&
      cellElementFor(/** @type {Element | null} */ (e.relatedTarget)) !== cellHover.anchor
    ) {
      releaseCellHover();
    }
  }
  /** @param {KeyboardEvent} e */
  function onKeyDown(e) {
    // A key held with Command, Control, or Option is the browser's: Command-R
    // reloads, and Command-Left or Alt-Left goes back.
    if (e.altKey || e.ctrlKey || e.metaKey) {
      return;
    }
    const key = e.key;
    if (key === "Enter" || key === " ") {
      const cell = cells[actionableIndexes[focusPos]];
      if (cell) {
        options.onActivate(cell);
      }
      e.preventDefault();
    } else if (key === "ArrowRight" || key === "ArrowDown") {
      moveFocus(focusPos + 1);
      e.preventDefault();
    } else if (key === "ArrowLeft" || key === "ArrowUp") {
      moveFocus(focusPos - 1);
      e.preventDefault();
    } else if (key === "Backspace" && options.onParent) {
      options.onParent();
      e.preventDefault();
    }
  }
  viewport.addEventListener("click", onClick);
  viewport.addEventListener("mouseover", onMouseOver);
  viewport.addEventListener("mouseout", /** @type {EventListener} */ (onMouseOut));
  viewport.addEventListener("keydown", /** @type {EventListener} */ (onKeyDown));

  /**
   * Replace the viewport's content with cells for `node`, or with
   * `placeholderHtml` when there is no tree to draw.
   * @param {Record<string, any> | null} node
   * @param {{placeholderHtml?: string, emptyHtml?: string}} [content]
   * @returns {number} cells drawn
   */
  function render(node, content) {
    if (disposed) {
      return 0;
    }
    // The cells are replaced below, and with them the one a cell's hover was entered
    // from; the browser enters its replacement under a pointer that has not moved. A
    // legend entry outlives the layout, so its hover is drawn again on the new cells.
    releaseCellHover();
    try {
      return renderCells(node, content ?? {});
    } finally {
      drawCellHover();
    }
  }

  /**
   * @param {Record<string, any> | null} node
   * @param {{placeholderHtml?: string, emptyHtml?: string}} content
   */
  function renderCells(node, content) {
    const box = drawableBox();
    if (!node || box.w < 10 || box.h < 10) {
      cells = [];
      actionableIndexes = [];
      viewport.innerHTML = content.placeholderHtml ?? "";
      return 0;
    }
    const state = options.getState();
    cells = layoutTree(node, box, {
      ...preset.layout,
      metric: state.metric,
      includeIgnored: state.includeIgnored,
    });
    const html = cells.map((cell, i) => cellHtml(cell, state, i)).join("");
    viewport.innerHTML = html || (content.emptyHtml ?? "");
    // Roving tabindex over actionable cells only (dir/file); remainder
    // cells are descriptive groups outside the focus order.
    actionableIndexes = [];
    cells.forEach((cell, i) => {
      if (cellIsActionable(cell)) {
        actionableIndexes.push(i);
      }
    });
    focusPos = 0;
    const first = /** @type {HTMLElement | null} */ (
      viewport.querySelector(`[data-tm-index="${actionableIndexes[0] ?? -1}"]`)
    );
    if (first) {
      first.setAttribute("tabindex", "0");
    }
    return cells.length;
  }

  function dispose() {
    if (disposed) {
      return;
    }
    disposed = true;
    releaseCellHover();
    unsubscribeCellHover();
    viewport.removeEventListener("click", onClick);
    viewport.removeEventListener("mouseover", onMouseOver);
    viewport.removeEventListener("mouseout", /** @type {EventListener} */ (onMouseOut));
    viewport.removeEventListener("keydown", /** @type {EventListener} */ (onKeyDown));
    // The host puts away the tooltip, its own and the map's at once, since it
    // may own other tooltips around the map (mb-alff).
  }

  return Object.freeze({
    render,
    /** Let go of the cell hover, as the host's own disposal begins. */
    releaseHover: releaseCellHover,
    dispose,
  });
}
