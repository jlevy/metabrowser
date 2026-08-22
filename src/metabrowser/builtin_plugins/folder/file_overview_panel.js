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
// the totals (see rollup_projection.js) — and merging their code would have
// entangled that for the sake of a heading.

import { mountFileTotalsPanel } from "./file_totals_panel.js";
import { mountFileTypeSummary } from "./file_type_summary.js";

/** @typedef {{mount: (container: HTMLElement, parts?: {metric?: boolean, ignored?: boolean}) => () => void, get: () => {metric: "size" | "files", includeIgnored: boolean}, subscribe: (listener: (state: {metric: "size" | "files", includeIgnored: boolean}) => void) => () => void}} FolderRollupControls */

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
  const controls = document.createElement("div");
  const totalsContainer = document.createElement("div");
  const breakdownContainer = document.createElement("div");
  container.append(controls, totalsContainer, breakdownContainer);
  // No parts argument: this row is both halves of the rollup controls, which
  // is the whole point of the section.
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
    options,
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
    required: true,
    collapsible: true,
    defaultExpanded: true,
    printable: false,
    /** @param {{path?: string}} context */
    resolve: (context) => Object.freeze({ key: context.path || "", data: null }),
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
