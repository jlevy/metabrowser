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
 * @property {string} wire The path's GitPath wire, as `/view/` addresses it on a pin.
 */

/**
 * @typedef {object} ViewFileAction
 * @property {"base" | "head"} side
 * @property {string} commit
 * @property {string} path
 * @property {string} wire
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
 * @property {(wire: string) => string} href The `/view/` address of a GitPath wire.
 * @property {(body: {oid: string, view: string}) => Promise<{status: number, body: unknown}>} switchPin
 *   `POST /api/source/pin`.
 * @property {(href: string) => void} navigate Load an address, as a link does.
 */

/**
 * @typedef {{kind: "navigated", href: string} | {kind: "busy"} | {kind: "refused", message: string}} ViewFileOutcome
 */

const FULL_COMMIT = /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/;
const VIEW_PREFIX = "/view/";
const SLASH = 0x2f;

/** @param {string} commit */
function short(commit) {
  return commit.slice(0, 12);
}

/**
 * One path segment's bytes as a GitPath wire token.
 *
 * @param {Uint8Array} bytes
 */
function wireToken(bytes) {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return `g1-${btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "")}`;
}

/**
 * The GitPath wire of one side's path: `g1-` and the unpadded base64url of each
 * segment's bytes. A path that is not UTF-8 carries its bytes in `path_b64`, and the
 * wire is built from those rather than from the replacement characters `path` shows.
 * `null` for a path with no segment or an empty one, which no tree entry has.
 *
 * @param {{path?: unknown, path_b64?: unknown}} side
 * @returns {string | null}
 */
export function sidePathWire(side) {
  /** @type {Uint8Array} */
  let bytes;
  if (typeof side.path_b64 === "string") {
    let binary;
    try {
      binary = atob(side.path_b64);
    } catch {
      return null;
    }
    bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  } else if (typeof side.path === "string") {
    bytes = new TextEncoder().encode(side.path);
  } else {
    return null;
  }
  const tokens = [];
  let start = 0;
  for (let index = 0; index <= bytes.length; index += 1) {
    if (index < bytes.length && bytes[index] !== SLASH) {
      continue;
    }
    if (index === start) {
      return null;
    }
    tokens.push(wireToken(bytes.subarray(start, index)));
    start = index + 1;
  }
  return tokens.join("/");
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
 * The sides of one change that are files at a commit, base before head.
 *
 * A deleted file has only its base side and an added one only its head side; a renamed
 * or copied file's base side is its old path. A comparison whose snapshots are not
 * commits, as a patch file's are not, has none, and neither has a root commit's base.
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
    const record = /** @type {{path?: unknown, path_b64?: unknown}} */ (entry);
    const wire = sidePathWire(record);
    if (wire !== null && typeof record.path === "string") {
      sides.push({ side, role, commit, path: record.path, wire });
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
 * @param {{pin: string}} page The commit the page shows.
 * @returns {ViewFileAction}
 */
export function describeViewFile(side, page) {
  const mode = side.commit === page.pin ? "link" : "switch";
  const label = side.side === "head" ? "View file" : `View at ${side.role}`;
  const at = short(side.commit);
  return {
    side: side.side,
    commit: side.commit,
    path: side.path,
    wire: side.wire,
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
 * first is on its way would race it.
 *
 * @param {ViewFileHost} host
 */
export function createViewFileOpener(host) {
  let switching = false;

  /**
   * @param {Record<string, unknown>} change
   * @param {Record<string, unknown>} resolved
   * @returns {ViewFileAction[]}
   */
  function actions(change, resolved) {
    return viewFileSides(change, resolved).map((side) => describeViewFile(side, host));
  }

  /**
   * Switch the served pin to an action's commit and go to its file there.
   *
   * @param {ViewFileAction} action
   * @returns {Promise<ViewFileOutcome>}
   */
  async function switchTo(action) {
    if (switching) {
      return { kind: "busy" };
    }
    switching = true;
    const address = host.href(action.wire);
    try {
      const response = await host.switchPin({ oid: action.commit, view: address });
      if (response.status !== 200) {
        return {
          kind: "refused",
          message: switchRefusal(action.commit, response.status, response.body),
        };
      }
      const answer = /** @type {{view_href?: unknown} | null} */ (response.body);
      const href = answer?.view_href;
      // The server says where the page goes on the new pin; the address asked for
      // stands in when it says nothing.
      const target = typeof href === "string" && href.startsWith(VIEW_PREFIX) ? href : address;
      host.navigate(target);
      return { kind: "navigated", href: target };
    } catch {
      return { kind: "refused", message: "The switch request failed." };
    } finally {
      // Also after a switch: a page the browser restores from its history cache must
      // not come back with every control held.
      switching = false;
    }
  }

  return Object.freeze({ actions, href: host.href, switchTo });
}
