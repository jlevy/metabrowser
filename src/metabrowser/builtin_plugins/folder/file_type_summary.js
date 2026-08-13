import {
  disposeDistributionView,
  mountDistributionView,
  updateDistributionView,
} from "./distribution_view.js";
import { buildFileTypeSummaryModel, normalizeRollupEnvelope } from "./file_type_summary_model.js";

const PREF_KEY = "folder.fileTypeSummary.open";
/** @typedef {{sync: (keys: Array<string>) => void, release: () => void, classFor: (key: string) => string}} SummaryPalette */
/** @typedef {{acquire: (path: string) => SummaryPalette}} SummaryPalettePool */

/**
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown}} context
 * @param {MetabrowserPublicSdk} mb
 * @param {SummaryPalettePool} palettePool
 * @param {{signal?: AbortSignal}} options
 */
export function mountFileTypeSummary(container, context, mb, palettePool, options) {
  const palette = palettePool.acquire(context.path || "");
  let disposed = false;
  let showIgnored = mb.filters.get().showIgnored;
  /** @type {ReturnType<typeof normalizeRollupEnvelope> | null} */
  let envelope = null;
  const formatters = {
    formatFileCount: mb.formatFileCount,
    formatInteger: mb.formatInteger,
    formatSize: mb.formatSize,
  };
  let model = buildFileTypeSummaryModel(null, showIgnored, formatters);
  const view = mountDistributionView(container, model, palette);
  view.details.open = mb.prefs.get(PREF_KEY, /** @type {boolean} */ (true));
  const handleDisclosure = () => mb.prefs.set(PREF_KEY, view.details.open);
  let disclosureTimer = 0;
  const handleDisclosureActivation = () => {
    window.clearTimeout(disclosureTimer);
    disclosureTimer = window.setTimeout(handleDisclosure, 0);
  };
  view.disclosureListener = handleDisclosure;
  view.details.addEventListener("toggle", handleDisclosure);
  view.summary.addEventListener("click", handleDisclosureActivation);

  function render() {
    model = buildFileTypeSummaryModel(envelope, showIgnored, formatters);
    updateDistributionView(view, model);
  }

  /** @param {unknown} raw */
  function applyEnvelope(raw) {
    if (disposed) {
      return;
    }
    envelope = normalizeRollupEnvelope(raw);
    palette.sync(envelope.tallies.filter((row) => row.key !== "").map((row) => row.key));
    render();
  }

  const watch = mb.watchRollup(
    context.path || "",
    {
      active: () => mb.viewState.isActive(container.closest("[data-tab-content]") || container),
      depth: 0,
      top: 0,
      ext_top: window.METABROWSER_SETTINGS?.ROLLUP_FILE_TYPE_NAMED_LIMIT ?? 10,
      ext_rank: "dual",
      /** @param {unknown} error */
      onError(error) {
        if (envelope) {
          const status = view.body.querySelector(".file-type-summary-status");
          if (status) {
            status.textContent = "Could not refresh file types; showing the previous totals.";
          }
          return;
        }
        const classification = mb.errors.classifyRequestError(error);
        view.body.innerHTML = `<div class="folder-overview-panel-error" role="alert">Could not load file types.${classification.retryable ? ' <button type="button" data-file-types-retry>Retry</button>' : ""}</div>`;
        view.body.querySelector("[data-file-types-retry]")?.addEventListener("click", () => {
          void watch.refresh();
        });
      },
    },
    applyEnvelope,
  );
  const unsubscribeFilters = mb.filters.subscribe((filters) => {
    if (filters.showIgnored !== showIgnored) {
      showIgnored = filters.showIgnored;
      render();
    }
  });
  const activeContainer = /** @type {HTMLElement} */ (
    container.closest("[data-tab-content]") || container
  );
  const unsubscribeActive = mb.viewState.subscribeActive(activeContainer, (active) => {
    if (active && watch.stale()) {
      void watch.refresh();
    }
  });
  const abort = () => dispose();
  options.signal?.addEventListener("abort", abort, { once: true });

  function dispose() {
    if (disposed) {
      return;
    }
    disposed = true;
    options.signal?.removeEventListener("abort", abort);
    watch.dispose();
    unsubscribeFilters();
    unsubscribeActive();
    window.clearTimeout(disclosureTimer);
    view.summary.removeEventListener("click", handleDisclosureActivation);
    disposeDistributionView(view);
    palette.release();
  }
  return Object.freeze({ dispose });
}

/** @param {MetabrowserPublicSdk} mb @param {SummaryPalettePool} palettePool */
export function createFileTypeSummaryPanel(mb, palettePool) {
  return Object.freeze({
    label: "File types",
    placement: /** @type {const} */ ("summary"),
    presentation: /** @type {const} */ ("surface"),
    required: true,
    printable: false,
    /** @param {{path?: string}} context */
    resolve: (context) => Object.freeze({ key: context.path || "", data: null }),
    /** @param {HTMLElement} container @param {{path?: string, raw?: unknown}} context @param {unknown} _data @param {{signal?: AbortSignal}} options */
    mount: (container, context, _data, options) =>
      mountFileTypeSummary(container, context, mb, palettePool, options),
  });
}
