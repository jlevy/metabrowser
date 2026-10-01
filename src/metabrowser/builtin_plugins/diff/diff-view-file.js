// View file: open a changed file at either side of the comparison a diff shows.
//
// A File Diff Format document whose snapshots are commits says which commit each side
// of a change belongs to: `resolved.left` for `change.old` (a commit's parent, or a
// comparison's base) and `resolved.right` for `change.new` (the commit, or the head).
// A page on a pinned revision reaches a file at a commit by its `/view/` address while
// the server's pin is that commit. So a side at the commit the page shows is a link to
// that address, which the browser follows as it follows any link: a new tab, a copied
// link, and back and forward are the browser's own. A side at another commit has no
// address yet, so it is a button that asks the server to switch its pin with the ref
// selector's own request, `POST /api/source/pin`, naming the address so the answer
// says where the page goes.
//
// Only a regular file's side gets a control. A submodule's side is a commit of another
// repository, which the view has nothing to show for. A symbolic link's side would open
// the file the link points at, while the diff shows the link's own text, so it is left
// out rather than opened as something the diff did not show.
//
// Every decision lives here without a DOM. `viewFileSides` reads the document,
// `describeViewFile` says what each control is and does, and `createViewFileOpener`
// owns the switch and what a refusal says. diff-view.js paints the controls, and
// tests/dom/diff-view-file-session.js runs all of it from the command line.

/**
 * @typedef {object} ViewFileSide
 * @property {"base" | "head"} side
 * @property {"parent" | "base" | "head"} role What the side is to the comparison.
 * @property {string} commit The full ID of the commit the side belongs to.
 * @property {string} path The side's path, as the diff shows it.
 * @property {string | Uint8Array} address The path as an address is built from it: its
 *   bytes when the name is not UTF-8, since `path` then holds replacement characters.
 */

/**
 * @typedef {object} ViewFileAction
 * @property {"base" | "head"} side
 * @property {string} commit
 * @property {string} path
 * @property {string} href The file's `/view/` address on a pin.
 * @property {"link" | "switch"} mode A link opens an address the page already has; a
 *   switch changes the served pin first.
 * @property {string} label The control's text.
 * @property {string} detail What following it does, for its tooltip and accessible name.
 */

/**
 * What the diff view needs of the page it is mounted in. The plugin supplies it on a
 * pinned revision; a served folder has none, and the diff shows no controls.
 *
 * @typedef {object} ViewFileHost
 * @property {string} pin The full ID of the commit the page shows.
 * @property {(path: string | Uint8Array) => string | null} href The `/view/` address of
 *   a path on a pin; null for a path no tree entry has.
 * @property {(body: {oid: string, view: string}) => Promise<{status: number, body: unknown}>} switchPin
 *   `POST /api/source/pin`.
 * @property {(href: string) => void} navigate Load an address, as a link does.
 * @property {(restored: () => void) => () => void} onRestored Call *restored* when the
 *   browser brings the page back from its back/forward cache; returns how to stop.
 */

/**
 * @typedef {{kind: "navigated", href: string} | {kind: "busy"} | {kind: "abandoned"} | {kind: "refused", message: string}} ViewFileOutcome
 */

const FULL_COMMIT = /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/;
const VIEW_PREFIX = "/view/";

/** @param {string} commit */
function short(commit) {
  return commit.slice(0, 12);
}

/**
 * One side's path as an address is built from it: the bytes in `path_b64` for a name
 * that is not UTF-8, else the path itself. Null when the entry names no path.
 *
 * @param {{path?: unknown, path_b64?: unknown}} entry
 * @returns {string | Uint8Array | null}
 */
export function sidePathForAddress(entry) {
  if (typeof entry.path_b64 === "string") {
    try {
      return Uint8Array.from(atob(entry.path_b64), (character) => character.charCodeAt(0));
    } catch {
      return null;
    }
  }
  return typeof entry.path === "string" ? entry.path : null;
}

/**
 * @param {unknown} snapshot
 * @returns {string | null} The snapshot's commit, when it is one.
 */
function snapshotCommit(snapshot) {
  const record = /** @type {{kind?: unknown, id?: unknown} | null} */ (
    snapshot !== null && typeof snapshot === "object" ? snapshot : null
  );
  return record !== null &&
    record.kind === "commit" &&
    typeof record.id === "string" &&
    FULL_COMMIT.test(record.id)
    ? record.id
    : null;
}

/**
 * The sides of one change that are regular files at a commit, base before head.
 *
 * A deleted file has only its base side and an added one only its head side; a renamed
 * or copied file's base side is its old path. A comparison whose snapshots are not
 * commits, as a patch file's are not, has none, and neither has a root commit's base.
 * A submodule's or a symbolic link's side is left out (see the head of this file).
 *
 * @param {Record<string, unknown>} change A manifest entry of the document.
 * @param {Record<string, unknown>} resolved The document's resolved comparison.
 * @returns {ViewFileSide[]}
 */
export function viewFileSides(change, resolved) {
  /** @type {ViewFileSide[]} */
  const sides = [];
  /** @param {"base" | "head"} side @param {ViewFileSide["role"]} role @param {unknown} snapshot @param {unknown} entry */
  const add = (side, role, snapshot, entry) => {
    const commit = snapshotCommit(snapshot);
    if (commit === null || entry === null || typeof entry !== "object") {
      return;
    }
    const record = /** @type {{path?: unknown, path_b64?: unknown, entry_type?: unknown}} */ (
      entry
    );
    const address = sidePathForAddress(record);
    if (record.entry_type === "file" && address !== null && typeof record.path === "string") {
      sides.push({ side, role, commit, path: record.path, address });
    }
  };
  add(
    "base",
    resolved.base_policy === "first_parent" ? "parent" : "base",
    resolved.left,
    change.old ?? null,
  );
  add("head", "head", resolved.right, change.new ?? null);
  return sides;
}

/**
 * What one side's control is. Pure.
 *
 * @param {ViewFileSide} side
 * @param {string} href The side's `/view/` address.
 * @param {{pin: string}} page The commit the page shows.
 * @returns {ViewFileAction}
 */
export function describeViewFile(side, href, page) {
  const mode = side.commit === page.pin ? "link" : "switch";
  const label = side.side === "head" ? "View file" : `View at ${side.role}`;
  const at = short(side.commit);
  return {
    side: side.side,
    commit: side.commit,
    path: side.path,
    href,
    mode,
    label,
    detail:
      mode === "link"
        ? `Open ${side.path} at ${at}, the commit this page shows`
        : `Switch to ${at} and open ${side.path}`,
  };
}

/**
 * Why a switch did not happen, in the ref selector's words for the same answers.
 *
 * @param {string} commit
 * @param {number} status
 * @param {unknown} body
 */
function switchRefusal(commit, status, body) {
  const record = /** @type {{code?: unknown} | null} */ (
    body !== null && typeof body === "object" ? body : null
  );
  const code = record !== null && typeof record.code === "string" ? record.code : "";
  const at = short(commit);
  if (code === "selection_pending") {
    return `The mirror is fetching ${at}; try again when the fetch ends.`;
  }
  if (code === "selection_not_found") {
    return `Commit ${at} is not in the mirror, and its origin does not have it.`;
  }
  if (code === "selection_fetch_failed") {
    return `Commit ${at} is not in the mirror, and fetching it failed.`;
  }
  return `Could not switch to ${at} (${code || `HTTP ${status}`}).`;
}

/**
 * The controls of one mounted diff and what following one does.
 *
 * One switch runs at a time: the pin is the server's, so a second request while the
 * first is on its way would race it. A switch the server made keeps the hold while the
 * page leaves, as the ref selector's does, so nothing else is asked of a page that is
 * going away; the hold ends if the browser brings the page back from its back/forward
 * cache with the pin it shows served again. A diff that was unmounted while its switch
 * was on the way does not take the page anywhere.
 *
 * @param {ViewFileHost} host
 * @param {{released?: () => void}} [options] *released* is called when a restored page
 *   lets go of the hold.
 */
export function createViewFileOpener(host, options = {}) {
  let switching = false;
  let disposed = false;
  const stopListening = host.onRestored(() => {
    if (switching) {
      switching = false;
      options.released?.();
    }
  });

  /**
   * @param {Record<string, unknown>} change
   * @param {Record<string, unknown>} resolved
   * @returns {ViewFileAction[]}
   */
  function actions(change, resolved) {
    /** @type {ViewFileAction[]} */
    const found = [];
    for (const side of viewFileSides(change, resolved)) {
      const href = host.href(side.address);
      if (href !== null) {
        found.push(describeViewFile(side, href, host));
      }
    }
    return found;
  }

  /**
   * Switch the served pin to an action's commit and go to its file there.
   *
   * @param {ViewFileAction} action
   * @returns {Promise<ViewFileOutcome>}
   */
  async function switchTo(action) {
    if (switching || disposed) {
      return { kind: disposed ? "abandoned" : "busy" };
    }
    switching = true;
    let response;
    try {
      response = await host.switchPin({ oid: action.commit, view: action.href });
    } catch {
      switching = false;
      return disposed
        ? { kind: "abandoned" }
        : { kind: "refused", message: "The switch request failed." };
    }
    if (disposed) {
      // The diff is gone, and with it the reader's reason to leave this page. The
      // server may have switched; the freshness row says so.
      switching = false;
      return { kind: "abandoned" };
    }
    if (response.status !== 200) {
      switching = false;
      return {
        kind: "refused",
        message: switchRefusal(action.commit, response.status, response.body),
      };
    }
    const answer = /** @type {{view_href?: unknown} | null} */ (response.body);
    const href = answer?.view_href;
    // The server says where the page goes on the new pin; the address asked for stands
    // in when it says nothing.
    const target = typeof href === "string" && href.startsWith(VIEW_PREFIX) ? href : action.href;
    host.navigate(target);
    return { kind: "navigated", href: target };
  }

  return Object.freeze({
    actions,
    switchTo,
    switching: () => switching,
    dispose() {
      disposed = true;
      stopListening();
    },
  });
}
