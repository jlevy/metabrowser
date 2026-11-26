// Compact folder treemap: the map component (treemap-map.js) at a small,
// fixed height, under File Overview's type breakdown.
//
// It answers the question the breakdown above it cannot, where in the folder
// the space or the files sit, at a glance, without leaving the Overview. It
// draws the same tree the Treemap view does and follows the section's measure
// and Show ignored. It shares the section's hover, so pointing at a breakdown
// legend entry marks that family's cells here too. A cell opens the Treemap
// view: a folder's cell at that folder, a file's or a remainder's at the
// folder holding it, and the outer box, labelled with the folder's name, at
// the folder itself. Every cell, however small, names itself in its tooltip.
//
// Its box is decided by the breakdown's answer, which the section holds its
// first paint for (file-overview-panel.js), so the box is there or not from
// that paint on instead of appearing or going away under the reader: it is
// left out when the index failed, stopped at its cap before finishing this
// folder, or the folder holds no files in the population shown, since the
// breakdown above already says why; otherwise it is kept, with a skeleton
// until the map draws. The map asks for its own deep rollup only once the
// index has settled: during a scan every answer would be discarded, and the
// deep one is the costliest body the route serves (ROLLUP_BODY_CACHE_ENTRIES
// in settings.py).

import {
  createTreemapMap,
  isCompleteSnapshot,
  retainTreemap,
  TREEMAP_LOADING_HTML,
  TREEMAP_VIEW_ID,
  treemapAvailability,
  treemapRollupQuery,
  withOuterBox,
} from "./treemap-map.js";

/** @typedef {{classFor: (key: string) => string, styleFor: (key: string) => string, paint: (element: HTMLElement, key: string) => void}} TreemapPalette */
/** @typedef {{metric: "size" | "files", includeIgnored: boolean}} TreemapState */
/** @typedef {{mount: (container: HTMLElement) => () => void, get: () => TreemapState, subscribe: (listener: (state: TreemapState) => void) => () => void}} FolderRollupControls */

const UNAVAILABLE_HTML = '<div class="preview-empty">Treemap unavailable.</div>';

/**
 * The folder a cell opens the Treemap at: a folder's own, or the one holding
 * a file. A remainder carries its folder's path.
 * @param {Record<string, any>} cell
 * @returns {string}
 */
function treemapFolderOf(cell) {
  if (cell.kind !== "file") {
    return cell.path;
  }
  const slash = cell.path.lastIndexOf("/");
  return slash === -1 ? "" : cell.path.slice(0, slash);
}

/**
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown}} context
 * @param {MetabrowserPublicSdk} mb
 * @param {TreemapPalette} palette
 * @param {FolderRollupControls} rollupControls
 * @param {{signal?: AbortSignal, hover?: import("./distribution-hover.js").DistributionHover}} options
 * @returns {{dispose: () => void, follow: (snapshot: Record<string, any> | null) => void, refresh: () => Promise<void>}}
 *   `follow` takes each answer the section's breakdown gets (null when its
 *   request failed with nothing to show), and `refresh` reads the map again
 *   once its watch has started.
 */
export function mountCompactTreemap(container, context, mb, palette, rollupControls, options) {
  const path = context.path || "";
  let state = rollupControls.get();
  let disposed = false;
  /** The breakdown's last answer; undefined until it has one. */
  /** @type {Record<string, any> | null | undefined} */
  let section;
  /** The map's own last answer. */
  /** @type {Record<string, any> | null} */
  let envelope = null;
  let failed = false;
  /** @type {ReturnType<MetabrowserPublicSdk["watchRollup"]> | null} */
  let watch = null;

  container.classList.add("tm-compact");
  const viewport = document.createElement("div");
  viewport.className = "tm-viewport tm-viewport-compact";
  viewport.setAttribute("role", "application");
  viewport.setAttribute("aria-label", "Folder treemap");
  // Keep the live region mounted and give it the notice's box only when it has a message.
  const status = document.createElement("div");
  status.setAttribute("role", "status");
  status.dataset.severity = "warning";
  container.append(viewport, status);

  const map = createTreemapMap(mb, palette, viewport, {
    size: "compact",
    getState: () => state,
    hover: options.hover,
    onActivate(cell) {
      void mb.navigation.open({ path: treemapFolderOf(cell) }, { viewId: TREEMAP_VIEW_ID });
    },
  });

  /**
   * Files in the population shown, from the answer's totals: emptiness is a
   * fact of the data, not of how many cells a box had room for.
   * @param {Record<string, any>} node
   */
  function shownFiles(node) {
    return state.includeIgnored ? node.total_files : node.unignored_files;
  }

  const activeContainer = /** @type {HTMLElement} */ (
    container.closest("[data-tab-content]") || container
  );

  function startWatch() {
    watch = mb.watchRollup(
      path,
      {
        active: () => mb.viewState.isActive(activeContainer),
        ...treemapRollupQuery(),
        /** @param {unknown} error */
        onError(error) {
          if (disposed) {
            return;
          }
          console.warn("Could not load the compact treemap.", error);
          if (!isCompleteSnapshot(envelope) || !envelope?.node) {
            failed = true;
            relayout();
          } else if (!status.textContent) {
            status.className = "notice tm-status";
            status.textContent = "Could not refresh the treemap. Showing the previous data.";
          }
        },
      },
      /** @param {Record<string, any>} next */
      (next) => {
        if (disposed || retainTreemap(envelope, next)) {
          return;
        }
        envelope = next;
        failed = false;
        status.textContent = "";
        status.className = "";
        relayout();
      },
    );
  }

  function relayout() {
    if (disposed) {
      return;
    }
    // Before the breakdown answers, a map is likely: the box waits with its skeleton.
    const sectionState = section === undefined ? "loading" : treemapAvailability(section, false);
    const empty = sectionState === "map" && section?.node && shownFiles(section.node) === 0;
    if (section === null || sectionState === "unavailable" || empty) {
      container.hidden = true;
      map.render(null);
      return;
    }
    container.hidden = false;
    if (sectionState !== "map") {
      // Still scanning: the map's own request waits for the index to settle.
      map.render(null, { placeholderHtml: TREEMAP_LOADING_HTML });
      return;
    }
    if (!watch) {
      startWatch();
    }
    const availability = treemapAvailability(envelope, failed);
    if (availability !== "map") {
      map.render(null, {
        placeholderHtml: availability === "unavailable" ? UNAVAILABLE_HTML : TREEMAP_LOADING_HTML,
      });
      return;
    }
    map.render(envelope?.node ? withOuterBox(envelope.node) : null, {
      placeholderHtml: TREEMAP_LOADING_HTML,
    });
  }
  relayout();

  const unsubscribeControls = rollupControls.subscribe((next) => {
    state = next;
    relayout();
  });
  const unsubscribeActive = mb.viewState.subscribeActive(activeContainer, (active) => {
    if (active && watch?.stale()) {
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
    watch?.dispose();
    unsubscribeControls();
    unsubscribeActive();
    map.dispose();
    // The map's tooltip, and no other surface's (mb-alff).
    mb.tooltip.hide(container);
  }
  return Object.freeze({
    dispose,
    /** @param {Record<string, any> | null} snapshot */
    follow(snapshot) {
      if (
        treemapAvailability(envelope, false) === "map" &&
        retainTreemap(section ?? null, snapshot)
      ) {
        return;
      }
      section = snapshot;
      relayout();
    },
    async refresh() {
      await watch?.refresh();
    },
  });
}
