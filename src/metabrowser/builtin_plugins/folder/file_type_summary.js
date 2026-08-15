import { mountDistributionView, updateDistributionView } from "./distribution_view.js";
import { buildFileTypeSummaryModel, normalizeRollupEnvelope } from "./file_type_summary_model.js";

/** @typedef {{sync: (keys: Array<string>) => void, release: () => void, classFor: (key: string) => string}} SummaryPalette */
/** @typedef {{acquire: (path: string) => SummaryPalette}} SummaryPalettePool */

/**
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown}} context
 * @param {MetabrowserPublicSdk} mb
 * @param {SummaryPalettePool} palettePool
 * @param {{mount: (container: HTMLElement, parts?: {metric?: boolean, ignored?: boolean}) => () => void, get: () => {metric: "size" | "files", includeIgnored: boolean}, subscribe: (listener: (state: {metric: "size" | "files", includeIgnored: boolean}) => void) => () => void}} rollupControls
 * @param {{signal?: AbortSignal}} options
 */
export function mountFileTypeSummary(container, context, mb, palettePool, rollupControls, options) {
  const palette = palettePool.acquire(context.path || "");
  let disposed = false;
  let controlsState = rollupControls.get();
  let showIgnored = controlsState.includeIgnored;
  /** @type {ReturnType<typeof normalizeRollupEnvelope> | null} */
  let envelope = null;
  const formatters = {
    formatFileCount: mb.formatFileCount,
    formatInteger: mb.formatInteger,
    formatSize: mb.formatSize,
  };
  let model = buildFileTypeSummaryModel(
    null,
    showIgnored,
    formatters,
    mb.fileTypes,
    controlsState.metric,
  );
  const metricClasses = {
    countClass: mb.countClass,
    sizeClass: mb.sizeClass,
  };
  const scopeControls = document.createElement("div");
  container.append(scopeControls);
  const unmountScopeControls = rollupControls.mount(scopeControls, {
    metric: false,
    ignored: true,
  });
  const view = mountDistributionView(container, model, palette, metricClasses, mb.fileTypeIcon);

  function render() {
    model = buildFileTypeSummaryModel(
      envelope,
      showIgnored,
      formatters,
      mb.fileTypes,
      controlsState.metric,
    );
    updateDistributionView(view, model);
  }

  /** @param {unknown} raw */
  function applyEnvelope(raw) {
    if (disposed) {
      return;
    }
    const nextEnvelope = normalizeRollupEnvelope(raw);
    const nextModel = buildFileTypeSummaryModel(
      nextEnvelope,
      showIgnored,
      formatters,
      mb.fileTypes,
      controlsState.metric,
    );
    palette.sync([
      ...nextEnvelope.groups.flatMap((group) =>
        group.families.map((family) => `family:${family.id}`),
      ),
      ...(nextEnvelope.specialTypes?.remainingTypes.extensions ?? []).map((row) => row.key),
    ]);
    updateDistributionView(view, nextModel);
    envelope = nextEnvelope;
    model = nextModel;
  }

  const watch = mb.watchRollup(
    context.path || "",
    {
      active: () => mb.viewState.isActive(container.closest("[data-tab-content]") || container),
      depth: 0,
      top: 0,
      ext_top: 0,
      filename_top: window.METABROWSER_SETTINGS?.ROLLUP_FILE_TYPE_FILENAME_LIMIT ?? 20,
      remaining_top: window.METABROWSER_SETTINGS?.ROLLUP_FILE_TYPE_REMAINING_LIMIT ?? 20,
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
        const contractFailure = error instanceof TypeError;
        const classification = contractFailure
          ? { retryable: false }
          : mb.errors.classifyRequestError(error);
        if (contractFailure) {
          console.warn("Could not display the file-type rollup.", error);
        }
        const message = contractFailure
          ? "Could not display file types because the rollup data is incompatible."
          : "Could not load file types.";
        view.body.innerHTML = `<div class="folder-overview-panel-error" role="alert">${message}${classification.retryable ? ' <button type="button" data-file-types-retry>Retry</button>' : ""}</div>`;
        view.body.querySelector("[data-file-types-retry]")?.addEventListener("click", () => {
          void watch.refresh();
        });
      },
    },
    applyEnvelope,
  );
  const unsubscribeControls = rollupControls.subscribe((nextState) => {
    const metricChanged = nextState.metric !== controlsState.metric;
    controlsState = nextState;
    if (nextState.includeIgnored !== showIgnored || metricChanged) {
      showIgnored = nextState.includeIgnored;
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
    unsubscribeControls();
    unmountScopeControls();
    unsubscribeActive();
    palette.release();
  }
  return Object.freeze({
    dispose,
  });
}

/** @param {MetabrowserPublicSdk} mb @param {SummaryPalettePool} palettePool @param {{mount: (container: HTMLElement, parts?: {metric?: boolean, ignored?: boolean}) => () => void, get: () => {metric: "size" | "files", includeIgnored: boolean}, subscribe: (listener: (state: {metric: "size" | "files", includeIgnored: boolean}) => void) => () => void}} rollupControls */
export function createFileTypeSummaryPanel(mb, palettePool, rollupControls) {
  return Object.freeze({
    label: "File Breakdown",
    placement: /** @type {const} */ ("summary"),
    presentation: /** @type {const} */ ("surface"),
    required: true,
    collapsible: true,
    defaultExpanded: false,
    printable: false,
    /** @param {{path?: string}} context */
    resolve: (context) => Object.freeze({ key: context.path || "", data: null }),
    /** @param {HTMLElement} container @param {{path?: string, raw?: unknown}} context @param {unknown} _data @param {{signal?: AbortSignal}} options */
    mount: (container, context, _data, options) =>
      mountFileTypeSummary(container, context, mb, palettePool, rollupControls, options),
  });
}
