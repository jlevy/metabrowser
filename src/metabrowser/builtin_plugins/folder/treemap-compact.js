// Compact folder treemap: the map component (treemap-map.js) at a small,
// fixed height, under File Overview's type breakdown.
//
// It answers the question the breakdown above it cannot, where in the folder
// the space or the files sit, at a glance, without leaving the Overview. It
// draws the same tree the Treemap view does, from its own rollup watch, and
// follows the section's measure and Show ignored. It shares the section's
// hover, so pointing at a breakdown legend entry marks that family's cells
// here too. Folder cells open the folder; file cells open the file; every
// cell, however small, names itself in its tooltip.
//
// It shows a skeleton while the rollup is on its way and steps out of the
// section when the rollup fails or the folder is empty: the breakdown above
// already says why there is nothing to draw.

import { createTreemapMap, treemapRollupQuery } from "./treemap-map.js";

/** @typedef {{classFor: (key: string) => string, styleFor: (key: string) => string, paint: (element: HTMLElement, key: string) => void}} TreemapPalette */
/** @typedef {{metric: "size" | "files", includeIgnored: boolean}} TreemapState */
/** @typedef {{mount: (container: HTMLElement) => () => void, get: () => TreemapState, subscribe: (listener: (state: TreemapState) => void) => () => void}} FolderRollupControls */

const LOADING_HTML =
  '<div class="tm-loading mb-delayed-loading" aria-hidden="true"></div><span class="sr-only">Loading treemap…</span>';

/**
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown}} context
 * @param {MetabrowserPublicSdk} mb
 * @param {TreemapPalette} palette
 * @param {FolderRollupControls} rollupControls
 * @param {{signal?: AbortSignal, hover?: import("./distribution-hover.js").DistributionHover}} options
 */
export function mountCompactTreemap(container, context, mb, palette, rollupControls, options) {
  const path = context.path || "";
  let state = rollupControls.get();
  let disposed = false;
  /** @type {Record<string, any> | null} */
  let envelope = null;
  let failed = false;

  container.classList.add("tm-compact");
  const viewport = document.createElement("div");
  viewport.className = "tm-viewport tm-viewport-compact";
  viewport.setAttribute("role", "application");
  viewport.setAttribute("aria-label", "Folder treemap");
  container.append(viewport);

  const map = createTreemapMap(mb, palette, viewport, {
    size: "compact",
    getState: () => state,
    hover: options.hover,
    onActivate(cell) {
      if (cell.kind === "dir" || cell.kind === "file") {
        void mb.navigation.open({ path: cell.path });
      }
    },
  });

  /**
   * The index has stopped, and has said all it will about this folder.
   * @param {Record<string, any> | null} snapshot
   */
  function isCompleteSnapshot(snapshot) {
    return (
      (snapshot?.index_status === "done" || snapshot?.index_status === "truncated") &&
      snapshot.node?.state !== "pending"
    );
  }

  function relayout() {
    if (disposed) {
      return;
    }
    const node = envelope?.node ?? null;
    const terminal = isCompleteSnapshot(envelope);
    if (failed || envelope?.index_status === "failed" || (terminal && !node)) {
      container.hidden = true;
      map.render(null);
      return;
    }
    container.hidden = false;
    if (!terminal || !node) {
      map.render(null, { placeholderHtml: LOADING_HTML });
      return;
    }
    const drawn = map.render(node, { placeholderHtml: LOADING_HTML });
    if (drawn === 0 && viewport.clientWidth > 0) {
      // Laid out and still nothing to draw: an empty folder.
      container.hidden = true;
    }
  }

  const activeContainer = /** @type {HTMLElement} */ (
    container.closest("[data-tab-content]") || container
  );
  const watch = mb.watchRollup(
    path,
    {
      active: () => mb.viewState.isActive(activeContainer),
      ...treemapRollupQuery(),
      // The tree alone: the breakdown above fetches the type tallies.
      ext_top: 0,
      filename_top: 0,
      remaining_top: 0,
      /** @param {unknown} error */
      onError(error) {
        console.warn("Could not load the compact treemap.", error);
        if (!isCompleteSnapshot(envelope) || !envelope?.node) {
          failed = true;
          relayout();
        }
      },
    },
    /** @param {Record<string, any>} next */
    (next) => {
      envelope = next;
      failed = false;
      relayout();
    },
  );
  relayout();

  const unsubscribeControls = rollupControls.subscribe((next) => {
    state = next;
    relayout();
  });
  const unsubscribeActive = mb.viewState.subscribeActive(activeContainer, (active) => {
    if (active && watch.stale()) {
      void watch.refresh();
    }
  });
  // The map's width follows the pane; its height is fixed in styles.css.
  let lastWidth = -1;
  const resizeObserver =
    typeof ResizeObserver !== "undefined"
      ? new ResizeObserver(() => {
          const width = viewport.clientWidth;
          if (width !== lastWidth) {
            lastWidth = width;
            relayout();
          }
        })
      : null;
  resizeObserver?.observe(viewport);

  const abort = () => dispose();
  options.signal?.addEventListener("abort", abort, { once: true });

  function dispose() {
    if (disposed) {
      return;
    }
    disposed = true;
    options.signal?.removeEventListener("abort", abort);
    resizeObserver?.disconnect();
    watch.dispose();
    unsubscribeControls();
    unsubscribeActive();
    map.dispose();
    // The map's tooltip, and no other surface's (mb-alff).
    mb.tooltip.hide(container);
  }
  return Object.freeze({ dispose });
}
