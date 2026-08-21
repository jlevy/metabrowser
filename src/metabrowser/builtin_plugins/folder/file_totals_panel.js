import {
  buildFolderTotalsComposition,
  mountFolderTotalsView,
  normalizeFolderTotals,
} from "./folder_totals.js";

/** @typedef {import("./folder_totals.js").FolderTotals} FolderTotals */
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
  const envelopeTotals = totalsFromFolderEnvelope(context.raw);
  const totalsView = mountFolderTotalsView(
    totalsContainer,
    envelopeTotals,
    mb,
    controlsState.metric,
  );

  // Totals arrive from two places and neither is reliably first. The
  // directory index carries the walker's aggregate, but the walker only
  // finalizes a directory once every descendant is walked, so for a large
  // root it stays pending for the whole crawl. The rollup meanwhile carries
  // counts for everything indexed so far. Keep the best of each and render
  // whichever is better, so a still-pending update can never replace numbers
  // already on screen with a loading state.
  /** @type {FolderTotals | null} */
  let indexedTotals = null;
  /** @type {FolderTotals | null} */
  let rollupTotals = null;

  function applyBestTotals() {
    // While a crawl runs, both sources are lower bounds that only grow, and
    // either can be the stale one: the directory index reports 0 for a root
    // it has not finalized, and the rollup lags behind its own refresh
    // debounce. Take the source that has seen more files, whole, rather than
    // mixing fields from both. This is a max over the two current sources, not
    // a ratchet over time: a fresh, smaller reading replaces an older one,
    // because files really can be deleted. Once the crawl finishes both agree.
    const best =
      indexedTotals && rollupTotals
        ? (indexedTotals.totalFiles ?? 0) >= (rollupTotals.totalFiles ?? 0)
          ? indexedTotals
          : rollupTotals
        : (indexedTotals ?? rollupTotals);
    if (best) {
      totalsView.update(best);
    }
  }

  /** @param {FolderTotals} next */
  function offerIndexedTotals(next) {
    if (next.state === "complete") {
      indexedTotals = next;
      applyBestTotals();
    }
  }

  // Seed with what the envelope already put on screen. subscribe() calls back
  // synchronously, but only when the store already holds this path: on first
  // paint the SSE snapshot may not have landed, and without this the first
  // rollup projection wins unopposed and the panel drops from the envelope's
  // count to the rollup's lower in-progress one — the regression the rule
  // above exists to prevent.
  offerIndexedTotals(envelopeTotals);

  const unsubscribeTotals = mb.directoryTotals.subscribe(path, (next) => {
    offerIndexedTotals(normalizeFolderTotals(next));
  });

  function updateComposition() {
    try {
      const composition = buildFolderTotalsComposition(
        rollupEnvelope,
        mb.fileTypes,
        controlsState.metric,
        controlsState.includeIgnored,
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
    const fromRollup = totalsFromRollupProjection(raw);
    if (fromRollup.state === "complete") {
      rollupTotals = fromRollup;
      applyBestTotals();
    }
    updateComposition();
  });
  const unsubscribeControls = rollupControls.subscribe((nextState) => {
    const metricChanged = nextState.metric !== controlsState.metric;
    const populationChanged = nextState.includeIgnored !== controlsState.includeIgnored;
    controlsState = nextState;
    if (metricChanged) {
      totalsView.updateMetric(nextState.metric);
    }
    if (metricChanged || populationChanged) {
      updateComposition();
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
    unsubscribeControls();
    unsubscribeProjection();
    unsubscribeTotals();
    unmountMetricControls();
    totalsView.dispose();
    projection.release();
    palette.release();
  }

  return Object.freeze({
    dispose,
    /** @param {{raw?: unknown}} nextContext */
    update(nextContext) {
      // A folder envelope refreshed mid-crawl still carries the walker's
      // unfinalized aggregate. Offer it, but fall back to the best totals
      // already known rather than dropping the panel back to a spinner.
      offerIndexedTotals(totalsFromFolderEnvelope(nextContext.raw));
      applyBestTotals();
    },
  });
}

/**
 * Folder totals from a rollup projection, covering what the crawl has indexed
 * so far. Returns a pending value when the projection carries no totals yet.
 *
 * @param {unknown} raw
 */
function totalsFromRollupProjection(raw) {
  const envelope =
    raw && typeof raw === "object" ? /** @type {Record<string, unknown>} */ (raw) : {};
  const totals =
    envelope.totals && typeof envelope.totals === "object"
      ? /** @type {Record<string, unknown>} */ (envelope.totals)
      : null;
  if (!totals) {
    return normalizeFolderTotals(null);
  }
  // normalizeFolderTotals accepts both the camelCase and snake_case spellings;
  // use one of them so this does not read like a mistake. The camelCase byte
  // fields are totalBytes / unignoredBytes, not *Size.
  return normalizeFolderTotals({
    totalFiles: totals.allFiles,
    totalBytes: totals.allBytes,
    unignoredFiles: totals.unignoredFiles,
    unignoredBytes: totals.unignoredBytes,
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
