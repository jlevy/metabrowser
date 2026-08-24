import {
  buildFolderTotalsComposition,
  chooseFolderTotals,
  mountFolderTotalsView,
  normalizeFolderTotals,
} from "./folder-totals.js";

/** @typedef {import("./folder-totals.js").FolderTotals} FolderTotals */
/** @typedef {{metric: "size" | "files", includeIgnored: boolean}} FolderRollupState */
/** @typedef {{mount: (container: HTMLElement, parts?: {metric?: boolean, ignored?: boolean}) => () => void, get: () => FolderRollupState, subscribe: (listener: (state: FolderRollupState) => void) => () => void}} FolderRollupControls */

/**
 * Mount immediate directory totals with the shared Files / Bytes chooser.
 *
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown}} context
 * @param {MetabrowserPublicSdk} mb
 * @param {{classFor(key: string): string, styleFor(key: string): string, paint(element: HTMLElement, key: string): void}} palette
 * @param {{acquire(path: string): {subscribe(listener: (value: unknown) => void): () => void, release(): void}}} projectionPool
 * @param {FolderRollupControls} rollupControls
 * @param {{signal?: AbortSignal}} options
 */
export function mountFileTotalsPanel(
  container,
  context,
  mb,
  palette,
  projectionPool,
  rollupControls,
  options,
) {
  let disposed = false;
  let controlsState = rollupControls.get();
  const path = context.path || "";
  const projection = projectionPool.acquire(path);
  /** @type {Parameters<typeof buildFolderTotalsComposition>[0]} */
  let rollupEnvelope = null;
  const totalsContainer = document.createElement("div");
  container.append(totalsContainer);
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
  // already on screen with a loading state. ``chooseFolderTotals`` owns the
  // rule and states why it changes once the index settles.
  /** @type {FolderTotals | null} */
  let indexedTotals = null;
  /** @type {FolderTotals | null} */
  let rollupTotals = null;
  let rollupSettled = false;

  function applyBestTotals() {
    const best = chooseFolderTotals(indexedTotals, rollupTotals, rollupSettled);
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
      );
      totalsView.updateComposition(composition, palette);
    } catch (error) {
      totalsView.updateComposition(null, null);
      console.warn("Could not compose folder population bars.", error);
    }
  }

  const unsubscribeProjection = projection.subscribe((raw) => {
    rollupEnvelope = /** @type {Parameters<typeof buildFolderTotalsComposition>[0]} */ (raw);
    const fromRollup = totalsFromRollupProjection(raw);
    if (fromRollup.state === "complete") {
      rollupTotals = fromRollup;
      // Whether the index has stopped moving is a fact the server reports, so
      // read it rather than inferring it from which number is larger.
      rollupSettled = isSettledIndexStatus(raw);
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
    totalsView.dispose();
    projection.release();
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
 * Whether a rollup projection reports an index that has stopped moving.
 *
 * ``truncated`` counts: the crawl stopped at the file cap and will not add
 * more, so its totals are as final as they are going to get.
 *
 * @param {unknown} raw
 */
function isSettledIndexStatus(raw) {
  const envelope =
    raw && typeof raw === "object" ? /** @type {Record<string, unknown>} */ (raw) : {};
  return envelope.indexStatus === "done" || envelope.indexStatus === "truncated";
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
