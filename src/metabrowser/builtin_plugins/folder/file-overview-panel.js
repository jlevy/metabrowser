// File Overview: what a folder holds, as one section.
//
// The totals and the type breakdown were two panels with two headings, and a
// reader had to collapse or scroll past the first to reach the second even
// though both answer the same question at different resolutions — how much is
// here, and what is it. Worse, they split one set of controls: the
// files-versus-bytes measure sat in the first and the show-ignored switch in
// the second, so changing what you were measuring and changing what was
// counted happened in two places, and each one silently moved the other's
// numbers.
//
// One section, one control row above both bodies. The measure and the
// gitignore switch are the same kind of choice about the same data, so they
// belong side by side, and every number under them answers to both.
//
// The bodies stay in their own modules. They have genuinely different data
// lifecycles — the breakdown owns the rollup fetch and projects its result to
// the totals (see rollup-projection.js) — and merging their code would have
// entangled that for the sake of a heading.

import { mountFileTotalsPanel } from "./file-totals-panel.js";
import { mountFileTypeSummary } from "./file-type-summary.js";

/** @typedef {{mount: (container: HTMLElement) => () => void, get: () => {metric: "size" | "files", includeIgnored: boolean}, subscribe: (listener: (state: {metric: "size" | "files", includeIgnored: boolean}) => void) => () => void}} FolderRollupControls */

/** Why a folder the inventory leaves out has no totals, by the envelope's `dir.not_indexed`. */
const NOT_INDEXED_STATEMENTS = Object.freeze({
  hidden: "Metabrowser does not index hidden folders, so this one has no file totals.",
  symlink:
    "Metabrowser does not follow symbolic links when it indexes, so this folder has no file totals here.",
});

/**
 * @param {unknown} raw The folder envelope.
 * @returns {string | null}
 */
function notIndexedStatement(raw) {
  const dir = /** @type {{dir?: {not_indexed?: "hidden" | "symlink"}} | null | undefined} */ (raw)
    ?.dir;
  return dir?.not_indexed ? NOT_INDEXED_STATEMENTS[dir.not_indexed] : null;
}

/**
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown}} context
 * @param {MetabrowserPublicSdk} mb
 * @param {{classFor: (key: string) => string, styleFor: (key: string) => string, paint: (element: HTMLElement, key: string) => void}} palette
 * @param {any} projectionPool
 * @param {FolderRollupControls} rollupControls
 * @param {{signal?: AbortSignal}} options
 */
export function mountFileOverviewPanel(
  container,
  context,
  mb,
  palette,
  projectionPool,
  rollupControls,
  options,
) {
  // Nothing can answer for such a folder, so nothing is asked and nothing waits.
  const statement = notIndexedStatement(context.raw);
  if (statement) {
    const note = document.createElement("div");
    note.className = "file-type-summary-empty";
    note.textContent = statement;
    container.append(note);
    return Object.freeze({ dispose() {} });
  }
  const controls = document.createElement("div");
  const totalsContainer = document.createElement("div");
  const breakdownContainer = document.createElement("div");
  container.append(controls, totalsContainer, breakdownContainer);
  // This row is both halves of the rollup controls, which is the whole point
  // of the section.
  const unmountControls = rollupControls.mount(controls);

  // Totals first, then the breakdown that refines them — the same order a
  // reader asks the two questions in. The breakdown mounts second but drives
  // the rollup fetch both bodies read.
  const totals = mountFileTotalsPanel(
    totalsContainer,
    context,
    mb,
    palette,
    projectionPool,
    rollupControls,
    options,
  );
  const breakdown = mountFileTypeSummary(
    breakdownContainer,
    context,
    mb,
    palette,
    projectionPool,
    rollupControls,
    {
      ...options,
      onNoTotals: () => totals.stopLoading(),
      onTotalsPending: () => totals.resumeLoading(),
    },
  );

  let disposed = false;
  function dispose() {
    if (disposed) {
      return;
    }
    disposed = true;
    // Bodies first, then the controls they subscribe to.
    breakdown.dispose();
    totals.dispose();
    unmountControls();
  }
  return Object.freeze({ dispose });
}

/**
 * @param {MetabrowserPublicSdk} mb
 * @param {{classFor: (key: string) => string, styleFor: (key: string) => string, paint: (element: HTMLElement, key: string) => void}} palette
 * @param {any} projectionPool
 * @param {FolderRollupControls} rollupControls
 */
export function createFileOverviewPanel(mb, palette, projectionPool, rollupControls) {
  return Object.freeze({
    label: "File Overview",
    placement: /** @type {const} */ ("summary"),
    presentation: /** @type {const} */ ("surface"),
    required: false,
    collapsible: true,
    defaultExpanded: true,
    printable: false,
    /** @param {{path?: string, raw?: unknown}} context */
    resolve: (context) => {
      const raw =
        context.raw && typeof context.raw === "object"
          ? /** @type {Record<string, unknown>} */ (context.raw)
          : {};
      // Git dir tallies omit mtime. File Overview mounts once sizes exist so
      // /api/rollup can answer without inventing recency.
      if (!raw.dir || typeof raw.dir !== "object") {
        return null;
      }
      if (!("mtime" in raw.dir) && !("total_size" in raw.dir)) {
        return null;
      }
      return Object.freeze({ key: context.path || "", data: null });
    },
    /** @param {HTMLElement} container @param {{path?: string, raw?: unknown}} context @param {unknown} _data @param {{signal?: AbortSignal}} options */
    mount: (container, context, _data, options) =>
      mountFileOverviewPanel(
        container,
        context,
        mb,
        palette,
        projectionPool,
        rollupControls,
        options,
      ),
  });
}
