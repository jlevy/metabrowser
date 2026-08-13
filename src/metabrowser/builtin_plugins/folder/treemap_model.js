/** @type {Readonly<Record<string, string>>} */
export const DEFAULT_TREEMAP_STATE = Object.freeze({
  metric: "size",
  grouping: "folder",
  color: "type",
  ignored: "dimmed",
});

/** @type {Readonly<Record<string, ReadonlyArray<string>>>} */
const VALID_STATE_VALUES = Object.freeze({
  metric: Object.freeze(["size", "files"]),
  grouping: Object.freeze(["folder", "type"]),
  color: Object.freeze(["type", "age"]),
  ignored: Object.freeze(["shown", "dimmed", "hidden"]),
});

/** @param {unknown} raw */
export function sanitizeTreemapState(raw) {
  /** @type {Record<string, string>} */
  const state = { ...DEFAULT_TREEMAP_STATE };
  if (raw && typeof raw === "object") {
    for (const key of Object.keys(VALID_STATE_VALUES)) {
      const value = /** @type {Record<string, unknown>} */ (raw)[key];
      if (typeof value === "string" && VALID_STATE_VALUES[key].includes(value)) {
        state[key] = value;
      }
    }
  }
  return state;
}

/** @param {string} path */
export function parentPath(path) {
  const index = path.lastIndexOf("/");
  return index === -1 ? "" : path.slice(0, index);
}
