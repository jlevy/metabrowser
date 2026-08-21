// Folder Treemap view controller.
//
// The `folder` kind is assigned by the server's api_file is_dir branch
// (see manifest.toml for why there is no [[kind]] rule). Owns one view:
//
//   ("folder", "treemap") — squarified folder/file hierarchy from
//       /api/rollup via mb.watchRollup: a Bytes/Files metric choice,
//       a default-on ignored-file checkbox, shared file-type colors,
//       fluid cell typography, hover tooltip, click navigation,
//       keyboard support, pending and truncated presentations.
//
// Geometry comes from treemap_layout.js. Toggle state comes from the shared
// folder rollup controls, persists through mb.prefs (host-only cookies,
// shared across per-root ports), and live refresh rides mb.watchRollup's
// debounced /api/events signal.

import { normalizeRollupEnvelope } from "./file_type_summary_model.js";
import {
  buildFolderTotalsComposition,
  mountFolderTotalsView,
  normalizeFolderTotals,
} from "./folder_totals.js";
import { layoutTree } from "./treemap_layout.js";
import { parentNavigation } from "./treemap_model.js";

/** @typedef {{classFor: (key: string) => string, styleFor: (key: string) => string, paint: (element: HTMLElement, key: string) => void}} TreemapPalette */
/** @typedef {{acquire: (path: string) => TreemapPalette}} TreemapPalettePool */
/** @typedef {{metric: "size" | "files", includeIgnored: boolean}} TreemapState */

/** @param {MetabrowserPublicSdk} mb @param {TreemapPalette} palette @param {{mount: (container: HTMLElement, parts?: {metric?: boolean, ignored?: boolean}) => () => void, get: () => TreemapState, subscribe: (listener: (state: TreemapState) => void) => () => void}} rollupControls */
export function registerTreemap(mb, palette, rollupControls) {
  const TREEMAP_VIEW_ID = "treemap";
  /** Minimum paint thresholds; type size itself comes from cell geometry. */
  const LABEL_MIN_W = 56;
  const LABEL_MIN_H = 16;
  /** Viewport height bounds: the map fills the space between its own
   * top edge and the window bottom (minus the status line and pane
   * padding), so wrapped toolbars or long breadcrumbs never push it
   * past the pane's single scroll owner. The CSS calc() height is
   * only the pre-measurement fallback. */
  const VIEWPORT_MIN_H = 280;
  const VIEWPORT_MAX_H = 900;
  const VIEWPORT_BOTTOM_RESERVE = 64;

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

  /** @param {Record<string, any>} cell @returns {boolean} */
  function cellIsActionable(cell) {
    return cell.kind === "dir" || cell.kind === "file";
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
    const showLabel = cell.w >= LABEL_MIN_W && cell.h >= Math.max(LABEL_MIN_H, labelLineHeight + 2);
    // Nested parents suppress the sublabel: the reserved header strip
    // is one line tall, and a second line would overlap child cells.
    const showStackedSub =
      showLabel &&
      cell.h >= labelLineHeight + valueLineHeight + 6 &&
      cell.kind !== "rest" &&
      !cell.nested;
    const showInlineSub = showLabel && cell.nested && cell.kind === "dir" && cell.w >= 140;
    const sub = cellValueText(cell, state);
    const aria = mb.escapeHtml(cellAriaLabel(cell, state));
    const actionable = cellIsActionable(cell);
    // A nested directory cell contains its children's cells, so the
    // cell itself stays a group and its label is the keyboard control.
    // Pointer routing uses the deepest outer cell instead, avoiding a
    // nested button tree without shrinking the hit target to the label.
    const titleInteractive = actionable && cell.nested;
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
   * Exceptional status copy; steady-state totals render above the map.
   * @param {Record<string, any> | null} envelope
   * @returns {string}
   */
  function statusHtml(envelope) {
    if (!envelope) {
      return "";
    }
    if (envelope.index_status === "failed") {
      return "Indexing failed; the treemap is unavailable.";
    }
    if (envelope.truncated) {
      return `Index capped at ${mb.formatFileCount(envelope.max_files)}; the treemap covers the indexed files.`;
    }
    return "";
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
      rows.push(`<strong>${mb.escapeHtml(cell.path || cell.name)}</strong>`);
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
   * ("folder", "treemap") renderer. All mutable state lives in this
   * closure; dispose tears down the watch, observer, and tooltip.
   * @param {HTMLElement} container
   * @param {Record<string, any>} ctx
   */
  function renderTreemap(container, ctx) {
    /** @type {TreemapState} */
    let state = rollupControls.get();
    /** @type {Record<string, any> | null} */
    let envelope = null;
    /** @type {Record<string, any>[]} */
    let cells = [];
    let disposed = false;
    /** @type {number[]} */
    let actionableIndexes = [];
    let focusPos = 0;
    const parent = parentNavigation(ctx.path || "");
    const parentControlHtml = parent
      ? '<div class="tm-parent-nav-row">' +
        `<button type="button" class="btn parent-nav-btn tm-parent-nav" aria-label="Zoom out to ${mb.escapeHtml(parent.label)}"` +
        ` title="Open ${mb.escapeHtml(parent.label)} in Treemap">` +
        '<span class="parent-nav-arrow" aria-hidden="true">↑</span>' +
        `<span>${mb.escapeHtml(parent.label)}</span></button></div>`
      : "";

    container.innerHTML =
      '<h2 class="tm-totals-heading">Files</h2>' +
      '<div class="tm-metric-controls folder-rollup-controls"></div>' +
      '<div class="tm-totals"></div>' +
      '<div class="tm-scope-controls folder-rollup-controls"></div>' +
      parentControlHtml +
      '<div class="tm-viewport" role="application" aria-label="Folder treemap"></div>' +
      '<div class="tm-status" role="status"></div>';
    const totalsContainer = /** @type {HTMLElement} */ (container.querySelector(".tm-totals"));
    const metricControls = /** @type {HTMLElement} */ (
      container.querySelector(".tm-metric-controls")
    );
    const scopeControls = /** @type {HTMLElement} */ (
      container.querySelector(".tm-scope-controls")
    );
    const parentControl = parent
      ? /** @type {HTMLButtonElement} */ (container.querySelector(".tm-parent-nav"))
      : null;
    const viewport = /** @type {HTMLElement} */ (container.querySelector(".tm-viewport"));
    const status = /** @type {HTMLElement} */ (container.querySelector(".tm-status"));
    const initialRaw =
      ctx.raw && typeof ctx.raw === "object"
        ? /** @type {Record<string, any>} */ (ctx.raw).dir
        : null;
    const totalsView = mountFolderTotalsView(
      totalsContainer,
      normalizeFolderTotals(initialRaw),
      mb,
      state.metric,
    );
    const unsubscribeTotals = mb.directoryTotals.subscribe(ctx.path || "", (next) => {
      const normalized = normalizeFolderTotals(next);
      if (normalized.state === "complete") {
        totalsView.update(normalized);
      }
    });
    /** @type {ReturnType<typeof normalizeRollupEnvelope> | null} */
    let totalsEnvelope = null;

    /**
     * Paint the file-type segments behind the totals bars, so the tally
     * above the map reads the same as the Overview's. The treemap owns
     * its own rollup watch, so it composes straight from that envelope
     * rather than through the Overview's projection pool. A contract
     * failure leaves the bars a single neutral fill instead of taking
     * the map down with it.
     */
    function updateTotalsComposition() {
      try {
        totalsView.updateComposition(
          buildFolderTotalsComposition(totalsEnvelope, mb.fileTypes, state.metric),
          palette,
        );
      } catch (error) {
        totalsView.updateComposition(null, null);
        console.warn("Could not compose treemap population bars.", error);
      }
    }
    const unmountMetricControls = rollupControls.mount(metricControls, {
      metric: true,
      ignored: false,
    });
    const unmountScopeControls = rollupControls.mount(scopeControls, {
      metric: false,
      ignored: true,
    });

    function openParent() {
      if (parent) {
        void mb.navigation.open({ path: parent.path }, { viewId: TREEMAP_VIEW_ID });
      }
    }

    if (parentControl) {
      parentControl.addEventListener("click", openParent);
    }

    /** Keep the shared exclusive-control semantics in step with the
     * controller state. filterControls.bind delegates state ownership
     * to the consumer, so relayout must update both the visible fill
     * and the radiogroup's roving tabindex. */
    /** Measure the height actually available below the viewport's top
     * edge and pin it as an inline style (clamped to the bounds
     * above). Skips silently where layout metrics are unavailable
     * (the vm test harness without a shim, a detached container) —
     * the CSS fallback height governs there. */
    function sizeViewport() {
      if (disposed || !viewport || !viewport.style) {
        return;
      }
      const winH = window.innerHeight;
      const rect = viewport.getBoundingClientRect();
      if (!Number.isFinite(winH) || winH <= 0 || !Number.isFinite(rect.top)) {
        return;
      }
      const avail = winH - rect.top - VIEWPORT_BOTTOM_RESERVE;
      const next = `${Math.round(Math.max(VIEWPORT_MIN_H, Math.min(VIEWPORT_MAX_H, avail)))}px`;
      if (viewport.style.height !== next) {
        viewport.style.height = next;
      }
    }

    function relayout() {
      if (disposed || !viewport) {
        return;
      }
      const rect = viewport.getBoundingClientRect();
      const node = envelope ? envelope.node : null;
      status.textContent = statusHtml(envelope);
      status.hidden = status.textContent === "";
      const terminal =
        envelope &&
        (envelope.index_status === "done" || envelope.index_status === "truncated") &&
        node?.state !== "pending";
      if (!terminal || !node || rect.width < 10 || rect.height < 10) {
        viewport.innerHTML =
          envelope?.index_status === "failed"
            ? '<div class="preview-empty">Treemap unavailable.</div>'
            : '<div class="tm-loading mb-delayed-loading" aria-hidden="true"></div><span class="sr-only">Loading treemap…</span>';
        return;
      }
      cells = layoutTree(
        node,
        { w: rect.width, h: rect.height },
        {
          metric: state.metric,
          includeIgnored: state.includeIgnored,
        },
      );
      const html = cells.map((cell, i) => cellHtml(cell, state, i)).join("");
      viewport.innerHTML =
        html || '<div class="preview-empty">Empty folder — nothing to draw yet</div>';
      // Roving tabindex over actionable cells only (dir/file); ext and
      // rest cells are descriptive groups outside the focus order.
      actionableIndexes = [];
      cells.forEach((cell, i) => {
        if (cell.kind === "dir" || cell.kind === "file") {
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
    }

    /**
     * Cell for hover/tooltip lookup: every cell carries data-tm-cell.
     * @param {Element | null} el
     * @returns {Record<string, any> | null}
     */
    function cellForElement(el) {
      if (!el) {
        return null;
      }
      const host = /** @type {HTMLElement | null} */ (el.closest("[data-tm-cell]"));
      if (!host) {
        return null;
      }
      const idx = Number(host.dataset.tmCell);
      return Number.isInteger(idx) && idx >= 0 && idx < cells.length ? cells[idx] : null;
    }

    /** @param {Record<string, any>} cell */
    function activateCell(cell) {
      if (cell.kind === "dir" && cell.path !== ctx.path) {
        void mb.navigation.open({ path: cell.path }, { viewId: TREEMAP_VIEW_ID });
      } else if (cell.kind === "file") {
        void mb.navigation.open({ path: cell.path });
      }
      // rest / ext cells have no navigation target.
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

    viewport.addEventListener("click", (e) => {
      const cell = cellForElement(/** @type {Element} */ (e.target));
      if (cell && cellIsActionable(cell)) {
        activateCell(cell);
      }
    });
    viewport.addEventListener("mouseover", (e) => {
      const cell = cellForElement(/** @type {Element} */ (e.target));
      if (cell) {
        mb.tooltip.show(tooltipHtml(cell, state), e);
      }
    });
    viewport.addEventListener("mousemove", (e) => {
      mb.tooltip.move(e);
    });
    viewport.addEventListener("mouseout", () => {
      mb.tooltip.hide();
    });
    viewport.addEventListener("keydown", (e) => {
      const key = e.key;
      if (key === "Enter" || key === " ") {
        const cell = cells[actionableIndexes[focusPos]];
        if (cell) {
          activateCell(cell);
        }
        e.preventDefault();
      } else if (key === "ArrowRight" || key === "ArrowDown") {
        moveFocus(focusPos + 1);
        e.preventDefault();
      } else if (key === "ArrowLeft" || key === "ArrowUp") {
        moveFocus(focusPos - 1);
        e.preventDefault();
      } else if (key === "Backspace") {
        openParent();
        e.preventDefault();
      }
    });

    const unsubscribeControls = rollupControls.subscribe((next) => {
      const metricChanged = next.metric !== state.metric;
      const populationChanged = next.includeIgnored !== state.includeIgnored;
      if (metricChanged) {
        totalsView.updateMetric(next.metric);
      }
      state = next;
      if (metricChanged || populationChanged) {
        updateTotalsComposition();
      }
      relayout();
    });

    sizeViewport();
    /** Tab switches hide inactive view containers (display:none)
     * without disposing them, so the watch must not spend fetches on
     * a map nobody can see. The stub-tolerant checks treat missing
     * properties (vm harness) as visible. */
    function isVisible() {
      return mb.viewState.isActive(container);
    }
    const watch = mb.watchRollup(ctx.path, { active: isVisible, ext_rank: "dual" }, (env) => {
      envelope = env;
      const completeSnapshot =
        (env.index_status === "done" || env.index_status === "truncated") &&
        env.node?.state !== "pending";
      if (completeSnapshot && env.node) {
        totalsView.update(normalizeFolderTotals(env.node));
      }
      const breakdown = env.file_type_breakdown;
      try {
        totalsEnvelope = breakdown ? normalizeRollupEnvelope(env) : null;
      } catch (error) {
        totalsEnvelope = null;
        console.warn("Could not read the treemap file-type breakdown.", error);
      }
      updateTotalsComposition();
      relayout();
    });
    const unsubscribeActive = mb.viewState.subscribeActive(container, (active) => {
      if (active && watch.stale()) {
        void watch.refresh();
      }
    });
    const resizeObserver =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(() => {
            // The container can resize without a window resize (pane
            // drag wraps the toolbar or breadcrumb above, moving this
            // viewport's top edge) — re-measure before laying out.
            // sizeViewport only writes when the value changes, so the
            // observer settles after one extra tick.
            sizeViewport();
            relayout();
          })
        : null;
    if (resizeObserver) {
      resizeObserver.observe(viewport);
    }
    // Window resize re-measures the available height; the observer
    // then relayouts off the height change (directly where there is
    // no ResizeObserver, e.g. the vm harness).
    function onWindowResize() {
      sizeViewport();
      if (!resizeObserver) {
        relayout();
      }
    }
    window.addEventListener("resize", onWindowResize);

    const dispose = () => {
      if (disposed) {
        return;
      }
      disposed = true;
      watch.dispose();
      unsubscribeActive();
      unsubscribeControls();
      unsubscribeTotals();
      unmountMetricControls();
      unmountScopeControls();
      if (parentControl) {
        parentControl.removeEventListener("click", openParent);
      }
      window.removeEventListener("resize", onWindowResize);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      mb.tooltip.hide();
    };
    return Object.freeze({ dispose });
  }

  mb.registerView("folder", TREEMAP_VIEW_ID, { render: renderTreemap });
}
