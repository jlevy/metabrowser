/** @typedef {{metric: "size" | "files", includeIgnored: boolean}} TreemapState */

/** @type {Readonly<TreemapState>} */
export const DEFAULT_TREEMAP_STATE = Object.freeze({
  metric: "files",
  includeIgnored: false,
});

/**
 * Normalize the two controls the streamlined Treemap still exposes.
 * Old preferences are intentionally read once here. Their three-state
 * ignored setting has no exact equivalent, so the redesigned control
 * starts from its requested unchecked default; an explicit new boolean
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
  const metric = saved.metric === "size" ? "size" : DEFAULT_TREEMAP_STATE.metric;
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

/**
 * Visible parent target for Treemap zoom-out navigation.
 * Canonical folder paths are root-relative and use an empty string for
 * the served root. The route uses `/` for that root because openPath
 * reserves the empty string for invalid input.
 *
 * @param {string} path
 * @returns {{path: string, label: string} | null}
 */
export function parentNavigation(path) {
  if (!path) {
    return null;
  }
  const parent = parentPath(path);
  if (!parent) {
    return { path: "/", label: "/" };
  }
  const segment = parent.slice(parent.lastIndexOf("/") + 1);
  return { path: parent, label: `${segment}/` };
}
