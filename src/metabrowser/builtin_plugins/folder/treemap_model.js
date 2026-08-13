/** @typedef {{metric: "size" | "files", includeIgnored: boolean}} TreemapState */

/** @type {Readonly<TreemapState>} */
export const DEFAULT_TREEMAP_STATE = Object.freeze({
  metric: "size",
  includeIgnored: true,
});

/**
 * Normalize the two controls the streamlined Treemap still exposes.
 * Old preferences are intentionally read once here. Their three-state
 * ignored setting has no exact equivalent, so the redesigned control
 * starts from its requested checked default; an explicit new boolean
 * is preserved. Obsolete grouping and color keys are discarded on the
 * next save.
 *
 * @param {unknown} raw
 * @returns {TreemapState}
 */
export function sanitizeTreemapState(raw) {
  if (!raw || typeof raw !== "object") {
    return { ...DEFAULT_TREEMAP_STATE };
  }
  const saved = /** @type {Record<string, unknown>} */ (raw);
  const metric = saved.metric === "files" ? "files" : "size";
  let includeIgnored = DEFAULT_TREEMAP_STATE.includeIgnored;
  if (typeof saved.includeIgnored === "boolean") {
    includeIgnored = saved.includeIgnored;
  }
  return { metric, includeIgnored };
}

/** @param {string} path */
export function parentPath(path) {
  const index = path.lastIndexOf("/");
  return index === -1 ? "" : path.slice(0, index);
}
