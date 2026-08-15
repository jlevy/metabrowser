import { mountFolderTotalsView, normalizeFolderTotals } from "./folder_totals.js";

/** @typedef {{metric: "size" | "files", includeIgnored: boolean}} FolderRollupState */
/** @typedef {{mount: (container: HTMLElement, parts?: {metric?: boolean, ignored?: boolean}) => () => void, get: () => FolderRollupState, subscribe: (listener: (state: FolderRollupState) => void) => () => void}} FolderRollupControls */

/**
 * Mount immediate directory totals with the shared Files / Bytes chooser.
 *
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown}} context
 * @param {MetabrowserPublicSdk} mb
 * @param {FolderRollupControls} rollupControls
 * @param {{signal?: AbortSignal}} options
 */
export function mountFileTotalsPanel(container, context, mb, rollupControls, options) {
  let disposed = false;
  let controlsState = rollupControls.get();
  const metricControls = document.createElement("div");
  const totalsContainer = document.createElement("div");
  container.append(metricControls, totalsContainer);
  const unmountMetricControls = rollupControls.mount(metricControls, {
    metric: true,
    ignored: false,
  });
  const totalsView = mountFolderTotalsView(
    totalsContainer,
    totalsFromFolderEnvelope(context.raw),
    mb,
    controlsState.metric,
  );
  const unsubscribeTotals = mb.directoryTotals.subscribe(context.path || "", (next) => {
    const normalized = normalizeFolderTotals(next);
    if (normalized.state === "complete") {
      totalsView.update(normalized);
    }
  });
  const unsubscribeControls = rollupControls.subscribe((nextState) => {
    if (nextState.metric !== controlsState.metric) {
      totalsView.updateMetric(nextState.metric);
    }
    controlsState = nextState;
  });
  const abort = () => dispose();
  options.signal?.addEventListener("abort", abort, { once: true });

  function dispose() {
    if (disposed) {
      return;
    }
    disposed = true;
    options.signal?.removeEventListener("abort", abort);
    unsubscribeControls();
    unsubscribeTotals();
    unmountMetricControls();
  }

  return Object.freeze({
    dispose,
    /** @param {{raw?: unknown}} nextContext */
    update(nextContext) {
      totalsView.update(totalsFromFolderEnvelope(nextContext.raw));
    },
  });
}

/** @param {unknown} raw */
function totalsFromFolderEnvelope(raw) {
  const envelope =
    raw && typeof raw === "object" ? /** @type {Record<string, unknown>} */ (raw) : {};
  return normalizeFolderTotals(envelope.dir);
}

/** @param {MetabrowserPublicSdk} mb @param {FolderRollupControls} rollupControls */
export function createFileTotalsPanel(mb, rollupControls) {
  return Object.freeze({
    label: "Files",
    placement: /** @type {const} */ ("summary"),
    presentation: /** @type {const} */ ("surface"),
    required: true,
    collapsible: true,
    defaultExpanded: true,
    printable: false,
    /** @param {{path?: string}} context */
    resolve: (context) => Object.freeze({ key: context.path || "", data: null }),
    /** @param {HTMLElement} container @param {{path?: string, raw?: unknown}} context @param {unknown} _data @param {{signal?: AbortSignal}} options */
    mount: (container, context, _data, options) =>
      mountFileTotalsPanel(container, context, mb, rollupControls, options),
  });
}
