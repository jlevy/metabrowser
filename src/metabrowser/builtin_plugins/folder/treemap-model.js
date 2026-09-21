/** @param {string} path */
export function parentPath(path) {
  const index = path.lastIndexOf("/");
  return index === -1 ? "" : path.slice(0, index);
}

/**
 * @param {string} path
 * @param {"filesystem" | "git_revision"=} sourceKind
 */
function identityDisplay(path, sourceKind) {
  const displayPath = globalThis.window?.MetabrowserNavigationRoute?.displayPath;
  if (typeof displayPath === "function") {
    return displayPath(path, sourceKind);
  }
  return path;
}

/**
 * Visible parent target for Treemap zoom-out navigation.
 * Canonical navigation paths are root-relative and use an empty string
 * for the served root, so the target path is empty there while the
 * button still reads `/`.
 *
 * The served source kind is an argument rather than a global read, so this
 * model stays callable without a window and the caller keeps one answer for
 * which subject it is rendering.
 *
 * @param {string} path
 * @param {"filesystem" | "git_revision"=} sourceKind
 * @returns {{path: string, label: string} | null}
 */
export function parentNavigation(path, sourceKind) {
  if (!path) {
    return null;
  }
  const parent = parentPath(path);
  if (!parent) {
    return { path: "", label: "/" };
  }
  const displayed = identityDisplay(parent, sourceKind);
  const segment = displayed.slice(displayed.lastIndexOf("/") + 1);
  return { path: parent, label: `${segment}/` };
}
