/** @param {string} path */
export function parentPath(path) {
  const index = path.lastIndexOf("/");
  return index === -1 ? "" : path.slice(0, index);
}

/**
 * Visible parent target for Treemap zoom-out navigation.
 * Canonical navigation paths are root-relative and use an empty string
 * for the served root, so the target path is empty there while the
 * button still reads `/`.
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
    return { path: "", label: "/" };
  }
  const segment = parent.slice(parent.lastIndexOf("/") + 1);
  return { path: parent, label: `${segment}/` };
}
