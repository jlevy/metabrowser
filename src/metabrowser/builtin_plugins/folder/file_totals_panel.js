import {
  buildFolderTotalsComposition,
  mountFolderTotalsView,
  normalizeFolderTotals,
} from "./folder_totals.js";

/** @typedef {{metric: "size" | "files", includeIgnored: boolean}} FolderRollupState */
/** @typedef {{mount: (container: HTMLElement, parts?: {metric?: boolean, ignored?: boolean}) => () => void, get: () => FolderRollupState, subscribe: (listener: (state: FolderRollupState) => void) => () => void}} FolderRollupControls */

/**
 * Mount immediate directory totals with the shared Files / Bytes chooser.
 *
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown}} context
 * @param {MetabrowserPublicSdk} mb
 * @param {{acquire(path: string): {sync(keys: Array<string>): void, classFor(key: string): string, release(): void}}} palettePool
 * @param {{acquire(path: string): {subscribe(listener: (value: unknown) => void): () => void, release(): void}}} projectionPool
 * @param {FolderRollupControls} rollupControls
 * @param {{signal?: AbortSignal}} options
 */
export function mountFileTotalsPanel(
  container,
  context,
  mb,
  palettePool,
  projectionPool,
  rollupControls,
  options,
) {
  let disposed = false;
  let controlsState = rollupControls.get();
  const path = context.path || "";
  const palette = palettePool.acquire(path);
  const projection = projectionPool.acquire(path);
  /** @type {Parameters<typeof buildFolderTotalsComposition>[0]} */
  let rollupEnvelope = null;
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
  const unsubscribeTotals = mb.directoryTotals.subscribe(path, (next) => {
    const normalized = normalizeFolderTotals(next);
    if (normalized.state === "complete") {
      totalsView.update(normalized);
    }
  });

  function updateComposition() {
    try {
      const composition = buildFolderTotalsComposition(
        rollupEnvelope,
        mb.fileTypes,
        controlsState.metric,
      );
      const paletteKeys = composition
        ? [
            ...composition.files.segments.map((segment) => segment.paletteKey),
            ...composition.ignored.segments.map((segment) => segment.paletteKey),
          ]
        : [];
      palette.sync(paletteKeys);
      totalsView.updateComposition(composition, palette);
    } catch (error) {
      palette.sync([]);
      totalsView.updateComposition(null, null);
      console.warn("Could not compose folder population bars.", error);
    }
  }

  const unsubscribeProjection = projection.subscribe((raw) => {
    rollupEnvelope = /** @type {Parameters<typeof buildFolderTotalsComposition>[0]} */ (raw);
    updateComposition();
  });
  const unsubscribeControls = rollupControls.subscribe((nextState) => {
    if (nextState.metric !== controlsState.metric) {
      controlsState = nextState;
      totalsView.updateMetric(nextState.metric);
      updateComposition();
      return;
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
    unsubscribeProjection();
    unsubscribeTotals();
    unmountMetricControls();
    projection.release();
    palette.release();
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

/** @param {MetabrowserPublicSdk} mb @param {{acquire(path: string): {sync(keys: Array<string>): void, classFor(key: string): string, release(): void}}} palettePool @param {{acquire(path: string): {subscribe(listener: (value: unknown) => void): () => void, release(): void}}} projectionPool @param {FolderRollupControls} rollupControls */
export function createFileTotalsPanel(mb, palettePool, projectionPool, rollupControls) {
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
      mountFileTotalsPanel(
        container,
        context,
        mb,
        palettePool,
        projectionPool,
        rollupControls,
        options,
      ),
  });
}
