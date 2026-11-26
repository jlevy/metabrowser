// View file and View on branch: open the file a change makes in the app's own viewer.
//
// A File Diff Format document whose snapshots are commits says which commit each side
// of a change belongs to; `resolved.right` is the commit `change.new` is at (a commit, or
// a pull request's head). Each file bar offers that side, and only that side, in the
// main UI: with the tree, the tabs, and the ref selector around it. The old side has no
// such place: a commit's parent is a bare commit, and a pull request's is the merge base,
// which no branch is at.
//
// A commit's diff, on a pinned revision, offers "View file". A page reaches a file at a
// commit by its `/view/` address while the server's pin is that commit, so at the commit
// the page shows the control is a link to that address, which the browser follows as it
// follows any link: a new tab, a copied link, and back and forward are the browser's own.
// At another commit it is a button that asks the server to switch its pin with the ref
// selector's own request, `POST /api/source/pin`, naming the address so the answer says
// where the page goes.
//
// A pull request's Changes offers "View on branch", by the same rule, when the diff shows
// the pull request's head: the pull request's page names its head ref (`branch`), a
// switch names that ref (`under`) beside the commit, and the page lands on the pull
// request's code as Browse code lands on it. Beside a checkout, which has no pin, the
// control is a link to the working-tree file when the checkout's HEAD is the diff's
// head, and absent otherwise. A control with no target is absent, never disabled.
//
// The pin is the server's, shared by every tab. When this page learns another tab
// switched it (`metabrowser:pin-changed`), its links would open the same path at the
// other pin, so each link becomes the button that switches back first.
//
// Only a regular file's side gets a control. A submodule's side is a commit of another
// repository, which the view has nothing to show for. A symbolic link's side would open
// the file the link points at, while the diff shows the link's own text, so it is left
// out rather than opened as something the diff did not show.
//
// One switch runs at a time on a page, whoever asks for it: the diff's controls and the
// pull request page's Browse code share `createPinSwitch`, which owns the request and
// what a refusal says. Every decision lives here without a DOM. `viewFileSide` reads the
// document, `describeViewFile` says what a control is and does, and
// `createViewFileOpener` owns a mounted diff's controls. diff-view.js paints them, and
// tests/dom/diff-view-file-session.js runs all of it from the command line.

/**
 * @typedef {object} ViewFileSide
 * @property {string} commit The full ID of the commit the change's new side is at.
 * @property {string} path The side's path, as the diff shows it.
 * @property {string | Uint8Array} address The path as an address is built from it: its
 *   bytes when the name is not UTF-8, since `path` then holds replacement characters.
 */

/**
 * @typedef {object} ViewFileAction
 * @property {string} commit
 * @property {string} path
 * @property {string} href The file's address in the main UI.
 * @property {"link" | "switch"} mode A link opens an address the page already has; a
 *   switch changes the served pin first.
 * @property {string} label The control's text.
 * @property {string} detail What following it does, for its tooltip and accessible name.
 * @property {boolean} [commitOnly] Open the comparison's pinned commit without selecting a ref.
 */

/**
 * A request to switch the served pin: a commit, the ref it is served under when it is
 * that ref's tip, and the `/view/` address the page goes to.
 *
 * @typedef {{oid: string, under?: string, view?: string}} PinSelection
 */

/**
 * @typedef {{kind: "switched", href: string | null} | {kind: "busy"} | {kind: "abandoned"} | {kind: "refused", message: string}} PinSwitchOutcome
 *   *href* is where the server says the page goes on the new pin, when it said.
 */

/** @typedef {ReturnType<typeof createPinSwitch>} PinSwitch */

/**
 * What the diff view needs of the page it is mounted in. The plugin supplies it on a
 * pinned revision, and for a pull request beside a checkout at its head; anywhere else
 * the diff shows no controls.
 *
 * @typedef {object} ViewFileHost
 * @property {"pin" | "checkout"} kind
 * @property {string} pin The full ID of the commit the page shows: the served pin, or
 *   the checkout's HEAD.
 * @property {string | null} branch The pull request's head ref on its Changes, and null
 *   on a commit's diff.
 * @property {(path: string | Uint8Array) => string | null} href The file's address at
 *   the page's commit; null for a path the page has no address for.
 * @property {PinSwitch} pinSwitch The page's one switch.
 * @property {(href: string) => void} navigate Load an address, as a link does.
 * @property {(changed: () => void) => () => void} onPinChanged Call *changed* when the
 *   page learns the server serves another pin; returns how to stop.
 */

/**
 * @typedef {{kind: "navigated", href: string} | {kind: "busy"} | {kind: "abandoned"} | {kind: "refused", message: string}} ViewFileOutcome
 */

/** @typedef {ReturnType<typeof createViewFileOpener>} ViewFileOpener */

/**
 * What makes a page's opener. The plugin holds the page's host, and the diff view supplies
 * *released*, which closes over the mounted view, and *changed*, which repaints its
 * controls.
 *
 * @typedef {(options?: {released?: () => void, changed?: () => void}) => ViewFileOpener} ViewFileOpenerFactory
 */

const FULL_COMMIT = /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/;
const VIEW_PREFIX = "/view/";
export const VIEW_FILE_LABEL = "View file";
export const VIEW_ON_BRANCH_LABEL = "View on branch";

/**
 * A commit as every line names one, in this module's tooltips and refusals, which are
 * text: the SDK's `shortCommit` (docs/design-system.md, "Short Commit IDs").
 *
 * @param {string} commit
 */
function short(commit) {
  return window.metabrowser.shortCommit(commit);
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
 * The side of one change a control opens: its new side, when that is a regular file at a
 * commit. Null for a deleted file, a comparison whose right snapshot is not a commit, as a
 * patch file's is not, and a submodule's or a symbolic link's side (see the head of this
 * file).
 *
 * @param {Record<string, unknown>} change A manifest entry of the document.
 * @param {Record<string, unknown>} resolved The document's resolved comparison.
 * @returns {ViewFileSide | null}
 */
export function viewFileSide(change, resolved) {
  const commit = snapshotCommit(resolved.right);
  const entry = change.new ?? null;
  if (commit === null || entry === null || typeof entry !== "object") {
    return null;
  }
  const record = /** @type {{path?: unknown, path_b64?: unknown, entry_type?: unknown}} */ (entry);
  const address = sidePathForAddress(record);
  return record.entry_type === "file" && address !== null && typeof record.path === "string"
    ? { commit, path: record.path, address }
    : null;
}

/**
 * What one side's control is. Pure.
 *
 * @param {ViewFileSide} side
 * @param {string} href The side's address in the main UI.
 * @param {{kind: ViewFileHost["kind"], pin: string, branch: string | null, pinChanged?: boolean}} page
 *   The commit the page shows, the pull request's head ref on its Changes, and whether
 *   the page learned that the server serves another pin.
 * @returns {ViewFileAction}
 */
export function describeViewFile(side, href, page) {
  const label = page.branch === null ? VIEW_FILE_LABEL : VIEW_ON_BRANCH_LABEL;
  const at = short(side.commit);
  if (page.kind === "checkout") {
    return {
      commit: side.commit,
      path: side.path,
      href,
      mode: "link",
      label,
      detail: `Open your working-tree copy of ${side.path}, in this checkout whose HEAD is this pull request's head`,
    };
  }
  const mode = side.commit === page.pin && page.pinChanged !== true ? "link" : "switch";
  return {
    commit: side.commit,
    path: side.path,
    href,
    mode,
    label,
    detail:
      mode === "link"
        ? `Open ${side.path} at ${at}, the commit this page shows`
        : page.branch === null
          ? `Switch to ${at} and open ${side.path}`
          : `Switch to ${at}, this pull request's head, and open ${side.path}`,
  };
}

/**
 * Why a switch did not happen, in the ref selector's words for the same answers.
 *
 * @param {unknown} body
 */
export function switchRefusal(body) {
  const record = /** @type {{code?: unknown} | null} */ (
    body !== null && typeof body === "object" ? body : null
  );
  const code = record !== null && typeof record.code === "string" ? record.code : "";
  // The sentence names no commit and no code: the control says which commit, and the
  // answer's code is an agent's (docs/design-system-messages.md).
  if (code === "selection_pending") {
    return "This commit is still being fetched. Try again shortly.";
  }
  if (code === "selection_not_found") {
    return "This commit is not on the origin.";
  }
  if (code === "selection_fetch_failed") {
    return "This commit could not be fetched. Try again.";
  }
  if (code === "ref_moved") {
    // Only a pull request's switch names the ref it is served under (`under`), and the
    // server says it moved when the page was drawn for an earlier head than its ref's.
    return "This pull request's head has moved; reload the page to see the newer changes.";
  }
  // The answer's status and code are in its JSON, which the network panel and
  // `metab --api` show.
  return "Could not open this commit. Try again.";
}

/**
 * A page's one switch of the served pin, which every control that switches it shares: a
 * diff's View file and View on branch, and the pull request page's Browse code and its
 * offer of a newer head.
 *
 * One switch runs at a time: the pin is the server's, so a second request while the first
 * is on its way would race it. A switch the server made keeps the hold while the page
 * leaves, as the ref selector's does, so nothing else is asked of a page that is going
 * away; the hold ends if the browser brings the page back from its back/forward cache,
 * and each listener of `onReleased` hears so. A caller that no longer wants the answer
 * when it comes, such as a diff unmounted meanwhile, says so with *wanted*: the hold then
 * ends and nothing is said.
 *
 * @param {{
 *   post: (selection: PinSelection) => Promise<{status: number, body: unknown}>,
 *   onRestored: (restored: () => void) => () => void,
 * }} host *post* is `POST /api/source/pin`; *onRestored* calls back when the browser
 *   brings the page back from its back/forward cache.
 */
export function createPinSwitch(host) {
  let holding = false;
  /** @type {Set<() => void>} */
  const released = new Set();
  host.onRestored(() => {
    if (holding) {
      holding = false;
      for (const listener of [...released]) {
        listener();
      }
    }
  });

  /**
   * @param {PinSelection} selection
   * @param {() => boolean} [wanted]
   * @returns {Promise<PinSwitchOutcome>}
   */
  async function switchTo(selection, wanted = () => true) {
    if (holding) {
      return { kind: "busy" };
    }
    holding = true;
    let response;
    try {
      response = await host.post(selection);
    } catch {
      holding = false;
      return wanted()
        ? { kind: "refused", message: "The switch request failed." }
        : { kind: "abandoned" };
    }
    if (!wanted()) {
      // The caller's reason to leave the page is gone. The server may have switched; the
      // freshness row says so.
      holding = false;
      return { kind: "abandoned" };
    }
    if (response.status !== 200) {
      holding = false;
      return {
        kind: "refused",
        message: switchRefusal(response.body),
      };
    }
    const answer = /** @type {{view_href?: unknown} | null} */ (response.body);
    const href = answer?.view_href;
    return {
      kind: "switched",
      href: typeof href === "string" && href.startsWith(VIEW_PREFIX) ? href : null,
    };
  }

  return Object.freeze({
    switchTo,
    switching: () => holding,
    /** @param {() => void} listener @returns {() => void} */
    onReleased(listener) {
      released.add(listener);
      return () => {
        released.delete(listener);
      };
    },
  });
}

/**
 * The controls of one mounted diff and what following one does.
 *
 * A switch that this diff made keeps the page's hold (`createPinSwitch`), and *released*
 * is called if the browser brings the page back with it let go. A diff that was unmounted
 * while its switch was on the way does not take the page anywhere. *changed* is called
 * once, when the page learns the server serves another pin, so the view asks `actions`
 * again and paints each link as the switch it now is.
 *
 * @param {ViewFileHost} host
 * @param {{released?: () => void, changed?: () => void}} [options]
 */
export function createViewFileOpener(host, options = {}) {
  let disposed = false;
  let pinChanged = false;
  // Whether the page's hold is this diff's switch, so a release is this diff's to show.
  let mine = false;
  const stopReleased = host.pinSwitch.onReleased(() => {
    if (mine) {
      mine = false;
      options.released?.();
    }
  });
  const stopPinChanged =
    host.kind === "pin"
      ? host.onPinChanged(() => {
          if (!pinChanged && !disposed) {
            pinChanged = true;
            options.changed?.();
          }
        })
      : () => {};

  /**
   * @param {Record<string, unknown>} change
   * @param {Record<string, unknown>} resolved
   * @returns {ViewFileAction[]}
   */
  function actions(change, resolved) {
    const side = viewFileSide(change, resolved);
    // A checkout shows its working tree, which is the diff's head only at its HEAD.
    if (side === null || (host.kind === "checkout" && side.commit !== host.pin)) {
      return [];
    }
    const href = host.href(side.address);
    return href === null
      ? []
      : [
          describeViewFile(side, href, {
            kind: host.kind,
            pin: host.pin,
            branch: host.branch,
            pinChanged,
          }),
        ];
  }

  /** @param {Record<string, unknown>} change @param {Record<string, unknown>} resolved */
  function fullFileAction(change, resolved) {
    const side = viewFileSide(change, resolved);
    if (host.kind !== "pin" || side === null) {
      return null;
    }
    const href = host.href(side.address);
    return href === null
      ? null
      : {
          ...describeViewFile(side, href, {
            kind: host.kind,
            pin: host.pin,
            branch: null,
            // A notice can stay visible through a pin change in another tab. Always
            // open the comparison's commit, including when it is still the current pin.
            pinChanged: true,
          }),
          label: "Open full file",
          commitOnly: true,
        };
  }

  /**
   * Switch the served pin to an action's commit and go to its file there.
   *
   * @param {ViewFileAction} action
   * @returns {Promise<ViewFileOutcome>}
   */
  async function switchTo(action) {
    if (disposed) {
      return { kind: "abandoned" };
    }
    const outcome = await host.pinSwitch.switchTo(
      {
        oid: action.commit,
        ...(host.branch === null || action.commitOnly ? {} : { under: host.branch }),
        view: action.href,
      },
      () => !disposed,
    );
    if (outcome.kind !== "switched") {
      return outcome;
    }
    mine = true;
    // The server says where the page goes on the new pin; the address asked for stands
    // in when it says nothing.
    const target = outcome.href ?? action.href;
    host.navigate(target);
    return { kind: "navigated", href: target };
  }

  return Object.freeze({
    actions,
    fullFileAction,
    switchTo,
    switching: () => host.pinSwitch.switching(),
    dispose() {
      disposed = true;
      stopReleased();
      stopPinChanged();
    },
  });
}
