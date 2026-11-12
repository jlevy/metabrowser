import { mountDistributionView, updateDistributionView } from "./distribution-view.js";
import { buildFileTypeSummaryModel, normalizeRollupEnvelope } from "./file-type-summary-model.js";

/** @typedef {{classFor: (key: string) => string, styleFor: (key: string) => string, paint: (element: HTMLElement, key: string) => void}} SummaryPalette */

/**
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown}} context
 * @param {MetabrowserPublicSdk} mb
 * @param {SummaryPalette} palette
 * @param {{acquire(path: string): {publish(value: unknown): void, release(): void}}} projectionPool
 * @param {{mount: (container: HTMLElement) => () => void, get: () => {metric: "size" | "files", includeIgnored: boolean}, subscribe: (listener: (state: {metric: "size" | "files", includeIgnored: boolean}) => void) => () => void}} rollupControls
 * @param {{signal?: AbortSignal, onNoTotals?: () => void, onTotalsPending?: () => void}} options
 *   `onNoTotals` is called when the rollup answers or fails without totals and this body says
 *   why, so a sibling can stop waiting for them. `onTotalsPending` is called when an answer
 *   says they are still on their way and this body shows its skeleton, so the sibling waits too.
 */
export function mountFileTypeSummary(
  container,
  context,
  mb,
  palette,
  projectionPool,
  rollupControls,
  options,
) {
  const path = context.path || "";
  const projection = projectionPool.acquire(path);
  let disposed = false;
  let controlsState = rollupControls.get();
  let showIgnored = controlsState.includeIgnored;
  /** @type {ReturnType<typeof normalizeRollupEnvelope> | null} */
  let envelope = null;
  // The last request failed with nothing to show. Its message stays until a
  // rollup answers: a control change must not bring the loading skeleton back.
  let loadFailed = false;
  /** @type {() => void} */
  let answered = () => {};
  // The first answer, whatever it says, or the end of the mount.
  /** @type {Promise<void>} */
  const firstAnswer = new Promise((resolve) => {
    answered = () => resolve(undefined);
  });
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
  const view = mountDistributionView(container, model, palette, metricClasses, mb.fileTypeIcon);

  function render() {
    if (loadFailed) {
      return;
    }
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
    updateDistributionView(view, nextModel);
    envelope = nextEnvelope;
    model = nextModel;
    loadFailed = false;
    if (nextEnvelope.totals) {
      // Publish while the crawl is still running too. Sibling panels read
      // ``indexStatus`` and label their numbers as in-progress, so holding
      // the projection back until the scan finished only meant they showed
      // a loading state for the whole crawl instead of counts that refine.
      projection.publish(nextEnvelope);
    } else if (nextModel.state === "pending") {
      options.onTotalsPending?.();
    } else {
      options.onNoTotals?.();
    }
    answered();
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
        if (envelope?.totals) {
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
        loadFailed = true;
        options.onNoTotals?.();
        answered();
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
    answered();
    options.signal?.removeEventListener("abort", abort);
    watch.dispose();
    unsubscribeControls();
    unsubscribeActive();
    projection.release();
  }
  return Object.freeze({
    dispose,
    ready: firstAnswer,
  });
}
