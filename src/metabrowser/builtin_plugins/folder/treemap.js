// Folder Treemap view controller.
//
// The `folder` kind is assigned by the server's api_file is_dir branch
// (see manifest.toml for why there is no [[kind]] rule). Owns one view:
//
//   ("folder", "treemap") — squarified folder/file hierarchy from
//       /api/rollup via mb.watchRollup: a Bytes/Files metric choice,
//       a default-on ignored-file checkbox, shared file-type colors,
//       fluid cell typography, hover tooltip, click navigation,
//       keyboard support, pending and truncated presentations, and the
//       file-type legend File Overview shows, under the tally bars.
//
// The map's cells, its tally bars, and its legend share one hover
// (distribution-hover.js), as File Overview's bars, legend, and table do:
// pointing at a legend entry marks every cell of its family and the family's
// segment in every tally row, and pointing at a cell or a segment marks it and
// its family's entry (docs/design-system.md, "Aggregate Distributions").
//
// The cells themselves, their layout, labels, tooltip, activation, and their
// part of the shared hover, are the map component (treemap-map.js), which the
// Overview's compact map mounts too. Toggle state comes from the shared
// folder rollup controls, persists through mb.prefs (host-only cookies,
// shared across per-root ports), and live refresh rides mb.watchRollup's
// debounced /api/events signal.

import { createDistributionHover } from "./distribution-hover.js";
import { createDistributionLegend } from "./distribution-legend.js";
import { buildFileTypeLegendModel, normalizeRollupEnvelope } from "./file-type-summary-model.js";
import {
  buildFolderTotalsComposition,
  mountFolderTotalsView,
  normalizeFolderTotals,
  notIndexedStatement,
} from "./folder-totals.js";
import {
  createTreemapMap,
  isCompleteSnapshot,
  retainTreemap,
  TREEMAP_LOADING_HTML,
  TREEMAP_VIEW_ID,
  treemapAvailability,
  treemapFullRollupQuery,
  withOuterBox,
} from "./treemap-map.js";
import { parentNavigation } from "./treemap-model.js";
import { decodeRollupEnvelope } from "./treemap-rollup-decode.js";

/** @typedef {{classFor: (key: string) => string, styleFor: (key: string) => string, paint: (element: HTMLElement, key: string) => void}} TreemapPalette */
/** @typedef {{acquire: (path: string) => TreemapPalette}} TreemapPalettePool */
/** @typedef {{metric: "size" | "files", includeIgnored: boolean}} TreemapState */

/** @param {MetabrowserPublicSdk} mb @param {TreemapPalette} palette @param {{mount: (container: HTMLElement) => () => void, get: () => TreemapState, subscribe: (listener: (state: TreemapState) => void) => () => void}} rollupControls */
export function registerTreemap(mb, palette, rollupControls) {
  /** Viewport height bounds: the map fills the space between its own
   * top edge and the window bottom (minus the status line and pane
   * padding), so wrapped toolbars or long breadcrumbs never push it
   * past the pane's single scroll owner. The CSS calc() height is
   * only the pre-measurement fallback. */
  const VIEWPORT_MIN_H = 280;
  const VIEWPORT_MAX_H = 900;
  const VIEWPORT_BOTTOM_RESERVE = 64;

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
      return "Could not scan this folder; the treemap is unavailable.";
    }
    if (envelope.truncated) {
      return `Only the first ${mb.formatFileCount(envelope.max_files)} were scanned; the treemap covers those files.`;
    }
    return "";
  }

  /**
   * ("folder", "treemap") renderer. All mutable state lives in this
   * closure; dispose tears down the watch, observer, and tooltip.
   * @param {HTMLElement} container
   * @param {Record<string, any>} ctx
   */
  function renderTreemap(container, ctx) {
    /** @type {Record<string, any> | null} */
    let envelope = null;
    // Whether the envelope's tree holds gitignored nodes: the view asks without them
    // while Show ignored is off (treemapFullRollupQuery).
    let envelopeHasIgnored = false;
    let rollupFailed = false;
    // The last request failed, so a map drawn without ignored files while Show ignored
    // is on says so until a tree with them arrives.
    let refreshFailed = false;
    let disposed = false;
    const parent = parentNavigation(ctx.path || "", mb.sourceKind());
    const parentControlHtml = parent
      ? '<div class="tm-parent-nav-row">' +
        `<button type="button" class="btn parent-nav-btn tm-parent-nav" aria-label="Zoom out to ${mb.escapeHtml(parent.label)}">` +
        '<span class="parent-nav-arrow" aria-hidden="true">↑</span>' +
        `<span>${mb.escapeHtml(parent.label)}</span></button></div>`
      : "";

    function openParent() {
      if (parent) {
        void mb.navigation.open({ path: parent.path }, { viewId: TREEMAP_VIEW_ID });
      }
    }

    const statement = notIndexedStatement(ctx.raw);
    if (statement) {
      container.innerHTML =
        '<h2 class="section-heading tm-totals-heading">Files</h2>' +
        parentControlHtml +
        `<div class="preview-empty">${mb.escapeHtml(statement)}</div>`;
      const parentControl = parent
        ? /** @type {HTMLButtonElement} */ (container.querySelector(".tm-parent-nav"))
        : null;
      if (parentControl) {
        parentControl.addEventListener("click", openParent);
      }
      return Object.freeze({
        dispose() {
          if (disposed) {
            return;
          }
          disposed = true;
          if (parentControl) {
            parentControl.removeEventListener("click", openParent);
          }
          mb.tooltip.hide(container);
        },
      });
    }

    /** @type {TreemapState} */
    let state = rollupControls.get();
    container.innerHTML =
      '<h2 class="section-heading tm-totals-heading">Files</h2>' +
      // One row for both halves, above the bars they govern — the same
      // arrangement as the Overview's File Overview. They used to sit apart,
      // the measure above the tally bars and the gitignore switch below them,
      // so the two choices about the same numbers were in two places and each
      // silently moved the other's.
      '<div class="tm-rollup-controls folder-rollup-controls"></div>' +
      '<div class="tm-totals"></div>' +
      // The legend's line is held while it has no entries, so the map below does not move
      // when the rollup's legend arrives (docs/design-system.md, "Regions Keep Their
      // Boxes").
      '<div class="tm-legend-row"><ul class="file-type-summary-legend tm-legend" hidden></ul></div>' +
      parentControlHtml +
      '<div class="tm-viewport" role="application" aria-label="Folder treemap"></div>' +
      '<div class="notice tm-status" data-severity="warning" role="status"></div>';
    const totalsContainer = /** @type {HTMLElement} */ (container.querySelector(".tm-totals"));
    const rollupControlsHost = /** @type {HTMLElement} */ (
      container.querySelector(".tm-rollup-controls")
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
    // The one hover the cells, the tally bars, and the legend share.
    const hover = createDistributionHover();
    const totalsView = mountFolderTotalsView(
      totalsContainer,
      normalizeFolderTotals(initialRaw),
      mb,
      state.metric,
      hover,
    );
    const legendList = /** @type {HTMLElement} */ (container.querySelector(".tm-legend"));
    const legend = createDistributionLegend(legendList, palette, hover);
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
    /**
     * The legend File Overview shows for the same rollup, measure, and Show ignored, under
     * the tally bars it keys. A rollup that breaks the legend's contract leaves it empty
     * rather than taking the map down with it.
     */
    function updateLegend() {
      /** @type {ReturnType<typeof buildFileTypeLegendModel>} */
      let model = { legend: [], caption: "" };
      try {
        model = buildFileTypeLegendModel(
          totalsEnvelope,
          state.includeIgnored,
          state.metric,
          mb,
          mb.fileTypes,
        );
      } catch (error) {
        console.warn("Could not read the treemap file-type legend.", error);
      }
      // The tally row the entries' shares are of, whose segment of a family gives an
      // entry's tooltip, as in File Overview.
      legend.update(model.legend, state.includeIgnored ? "all" : "files");
      legendList.setAttribute("aria-label", model.caption);
    }

    // No parts argument: this row is both halves.
    const unmountControls = rollupControls.mount(rollupControlsHost);

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

    // The cells, and their part of the hover the map shares with its bars and legend.
    const map = createTreemapMap(mb, palette, viewport, {
      size: "full",
      getState: mapState,
      onActivate: activateCell,
      // The outer box is this view's own folder, so it opens nothing.
      opens: (cell) => !(cell.kind === "dir" && cell.path === (ctx.path || "")),
      hover,
      onParent: openParent,
    });

    /**
     * The state the map lays its tree out under. A tree asked for without gitignored
     * nodes draws as Show ignored off until the one with them arrives, so turning it on
     * keeps the map it had rather than sizing folders by totals whose nodes are missing.
     * @returns {TreemapState}
     */
    function mapState() {
      return envelopeHasIgnored ? state : { ...state, includeIgnored: false };
    }

    function relayout() {
      if (disposed || !viewport) {
        return;
      }
      status.textContent =
        statusHtml(envelope) ||
        (refreshFailed && state.includeIgnored && !envelopeHasIgnored
          ? "Could not load the ignored files; the treemap shows the others."
          : refreshFailed && treemapAvailability(envelope, false) === "map"
            ? "Could not refresh the treemap; showing the previous data."
            : "");
      status.hidden = status.textContent === "";
      const failed = envelope?.index_status === "failed";
      status.dataset.severity = failed ? "error" : "warning";
      status.setAttribute("role", failed ? "alert" : "status");
      const availability = treemapAvailability(envelope, rollupFailed);
      if (availability !== "map") {
        // Nothing is coming when it is unavailable, so no skeleton either.
        map.render(null, {
          placeholderHtml:
            availability === "unavailable"
              ? '<div class="preview-empty">Treemap unavailable.</div>'
              : TREEMAP_LOADING_HTML,
        });
        return;
      }
      map.render(envelope?.node ? withOuterBox(envelope.node) : null, {
        // A box too small to draw in yet is a map still arriving.
        placeholderHtml: TREEMAP_LOADING_HTML,
        emptyHtml:
          '<div class="preview-empty">This folder is empty, so there is nothing to draw yet.</div>',
      });
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
      if (populationChanged) {
        syncTreeWatch();
      }
      relayout();
      if (metricChanged || populationChanged) {
        updateLegend();
      }
    });

    sizeViewport();
    /** Tab switches hide inactive view containers (display:none)
     * without disposing them, so the watch must not spend fetches on
     * a map nobody can see. The stub-tolerant checks treat missing
     * properties (vm harness) as visible. */
    function isVisible() {
      return mb.viewState.isActive(container);
    }
    /** @param {unknown} error */
    function onRollupError(error) {
      console.warn("watchRollup refresh failed:", error);
      refreshFailed = true;
      if (!isCompleteSnapshot(envelope) || !envelope?.node) {
        rollupFailed = true;
        totalsView.stopLoading();
      }
      relayout();
    }
    /**
     * Watch the folder's tree as Show ignored asks for it now.
     * @returns {ReturnType<MetabrowserPublicSdk["watchRollup"]>}
     */
    function watchTree() {
      const includeIgnored = state.includeIgnored;
      watchedIgnored = includeIgnored;
      return mb.watchRollup(
        ctx.path,
        {
          active: isVisible,
          ...treemapFullRollupQuery(includeIgnored),
          onError: onRollupError,
        },
        (raw) => onTree(raw, includeIgnored),
      );
    }
    /**
     * @param {Record<string, any>} raw
     * @param {boolean} includeIgnored  whether it was asked for with gitignored nodes
     */
    function onTree(raw, includeIgnored) {
      /** @type {Record<string, any>} */
      let env;
      try {
        env = decodeRollupEnvelope(raw);
      } catch (error) {
        onRollupError(error);
        return;
      }
      if (retainTreemap(envelope, env)) {
        return;
      }
      envelope = env;
      envelopeHasIgnored = includeIgnored;
      rollupFailed = false;
      refreshFailed = false;
      const completeSnapshot = isCompleteSnapshot(env);
      if (completeSnapshot && env.node) {
        totalsView.update(normalizeFolderTotals(env.node));
      } else if (
        completeSnapshot ||
        env.index_status === "failed" ||
        env.index_status === "truncated"
      ) {
        totalsView.stopLoading();
      } else {
        // Still scanning, so the map shows its skeleton, whatever a failure or a
        // finished index ended before this answer.
        totalsView.resumeLoading();
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
      updateLegend();
    }
    /** Whether the watch asks for the tree with its gitignored nodes. */
    let watchedIgnored = state.includeIgnored;
    let watch = watchTree();
    let rereadOnReveal = false;
    /**
     * The tree is asked for with or without its gitignored nodes, so a Show ignored that
     * no longer matches the watch asks again; the totals and the legend above hold both
     * populations already. A view out of sight asks when it shows, since a watch fetches
     * as it starts and the switch is shared with File Overview's.
     */
    function syncTreeWatch() {
      if (state.includeIgnored !== watchedIgnored && isVisible()) {
        watch.dispose();
        watch = watchTree();
      }
    }
    const unsubscribeActive = mb.viewState.subscribeActive(container, (active) => {
      if (!active) {
        return;
      }
      const reread = rereadOnReveal;
      rereadOnReveal = false;
      if (state.includeIgnored !== watchedIgnored) {
        syncTreeWatch();
      } else if (reread || watch.stale()) {
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
      // The legend's row holds one line, and takes more in a pane too narrow for its
      // entries, which moves the map's top edge: measured again, the map keeps to the
      // space below it.
      const legendRow = legendList.parentElement;
      if (legendRow) {
        resizeObserver.observe(legendRow);
      }
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
      unmountControls();
      // The hover goes with the marks it was drawn on. Each part lets go of what it holds
      // before the cells stop listening, so nothing is left marked: the cells, the legend,
      // and the bars, whose disposal clears the hover for every part still listening.
      map.releaseHover();
      legend.dispose();
      totalsView.dispose();
      map.dispose();
      if (parentControl) {
        parentControl.removeEventListener("click", openParent);
      }
      window.removeEventListener("resize", onWindowResize);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      // The map's tooltip, and no other surface's (mb-alff).
      mb.tooltip.hide(container);
    };
    return Object.freeze({
      dispose,
      /** @param {MetabrowserPublicRenderContext} next */
      async refresh(next) {
        if (notIndexedStatement(next.raw)) {
          return false;
        }
        if (isVisible()) {
          await watch.refresh();
        } else {
          rereadOnReveal = true;
        }
        return true;
      },
    });
  }

  mb.registerView("folder", TREEMAP_VIEW_ID, { render: renderTreemap });
}
