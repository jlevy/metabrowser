// A pull request's changed files as a tree, the way a folder expands in the Files tab.
//
// Every decision lives here without a DOM, and the tree is built from the list of files the
// `pull-files` route answers, never from hydrated diff documents. `holdFileList` keeps the rows
// of one list as its pages arrive and says which window to ask for next; `buildFileTree` makes
// folders of their paths; `visibleRows` flattens the folders a reader has expanded into rows,
// drawing a folder whose only child is a folder as one row, `src/metabrowser`, as GitHub's file
// tree does, with which folders are open decided by `initialExpansion` and a reader's toggles;
// `describeFileList` says what the list is and how much of it has arrived.
//
// `createFileTreeController` is one pull request's tree in its row: reading and asking for the
// list, the folders a reader opens, the row that takes Tab, the keys, and the jump of the diff
// to a file; `createRowExpansion` says which rows are open and why; `windowRange` which rows of
// a long tree are in the document. pull-files-view.js is the paint, and
// tests/dom/github-pull-files-tree-session.js runs the rest from the command line on what the
// server answered.
//
// A path is text whoever opened the pull request wrote. It is a row's identity, and the path
// the diff view's jump is given, a rename's new path; what is painted is the row's `display`,
// the server's display rule (control and invisible characters shown as U+FFFD), and a name
// never reaches markup or a filesystem call. A folder's identity ends in "/", so a file and a
// folder of one name, as a file replaced by a directory lists them, are two rows.
//
// Measured 2026-11-03 with Node 24.19 on real lists as the route answered them, the median of
// 25 runs twice at a load average of 4.5: building the tree and flattening it with every folder
// expanded took 1.3 ms for the first 1,183 files of django/django#15387 (1,503 rows) and 3.7 ms
// for the 3,000 nodejs/node#65161 lists (3,346 rows), so the whole tree is built again as each
// page arrives. Which folders start expanded is a file count
// the panel measures in a real browser and passes in.

/**
 * One row of the route's answer.
 *
 * @typedef {{
 *   path: string,
 *   previous_path: string | null,
 *   status: string,
 *   additions: number | null,
 *   deletions: number | null,
 *   display: string,
 *   previous_display: string | null,
 * }} FileRow
 */

/**
 * The route's envelope, as far as the tree reads it.
 *
 * @typedef {{
 *   state: "absent" | "pending" | "current" | "stale",
 *   reason: string | null,
 *   number: number,
 *   listed_from: "github" | "comparison" | null,
 *   fetched_at: string | null,
 *   reader: string | null,
 *   head: string | null,
 *   base: string | null,
 *   fresh_for_s: number,
 *   refreshing: boolean,
 *   last_refresh: {outcome: string, message: string | null, reset_at: string | null, at: string} | null,
 *   fetched: number,
 *   pages: number,
 *   last_page: number | null,
 *   complete: boolean,
 *   capped: boolean,
 *   truncated: boolean,
 *   offset: number,
 *   limit: number,
 *   rows: FileRow[],
 * }} FilesEnvelope
 */

/**
 * @typedef {{kind: "folder", id: string, name: string, files: number, children: TreeNode[]}} FolderNode
 * @typedef {{kind: "file", id: string, name: string, row: FileRow}} FileNode
 * @typedef {FolderNode | FileNode} TreeNode
 * @typedef {{root: FolderNode, files: number, folderIds: string[]}} FileTree
 */

/**
 * One visible row. A folder row stands for its chain: `ids` are the chain's folders, top
 * first, and `id` the deepest, whose children follow it when it is expanded.
 *
 * `position` and `setSize` are its place among its parent's children, a chain counting as
 * one, for `aria-posinset` and `aria-setsize`: a row out of view is not in the document.
 *
 * @typedef {{
 *   kind: "folder",
 *   id: string,
 *   ids: string[],
 *   name: string,
 *   depth: number,
 *   position: number,
 *   setSize: number,
 *   expanded: boolean,
 *   files: number,
 * } | {
 *   kind: "file",
 *   id: string,
 *   name: string,
 *   depth: number,
 *   position: number,
 *   setSize: number,
 *   path: string,
 *   display: string,
 *   badge: string,
 *   statusLabel: string,
 *   additions: number | null,
 *   deletions: number | null,
 *   previousName: string | null,
 *   current: boolean,
 * }} TreeRow
 */

/** The one-letter badge a patch's children carry, by GitHub's status. */
export const STATUS_BADGES = Object.freeze({
  added: "A",
  removed: "D",
  modified: "M",
  renamed: "R",
  copied: "C",
  changed: "T",
  unchanged: "M",
});

/** What a badge's tooltip and accessible name say, by GitHub's status. */
export const STATUS_LABELS = Object.freeze({
  added: "Added",
  removed: "Deleted",
  modified: "Modified",
  renamed: "Renamed",
  copied: "Copied",
  changed: "Type changed",
  unchanged: "Unchanged",
});

/**
 * The same order wherever it runs: by name without case, then by the name itself, so no
 * locale's collation decides it.
 *
 * @param {TreeNode} left
 * @param {TreeNode} right
 */
function byName(left, right) {
  if (left.kind !== right.kind) {
    return left.kind === "folder" ? -1 : 1;
  }
  const a = left.name.toLowerCase();
  const b = right.name.toLowerCase();
  if (a !== b) {
    return a < b ? -1 : 1;
  }
  return left.name < right.name ? -1 : left.name > right.name ? 1 : 0;
}

/**
 * Folders of the rows' paths. Each path is split on "/", and each segment is named by the
 * same segment of `display`, which the server's rule keeps one for one.
 *
 * @param {FileRow[]} rows
 * @returns {FileTree}
 */
export function buildFileTree(rows) {
  /** @type {FolderNode} */
  const root = { kind: "folder", id: "", name: "", files: 0, children: [] };
  /** @type {Map<string, FolderNode>} */
  const folders = new Map([["", root]]);
  /** @type {Set<string>} */
  const seen = new Set();
  for (const row of rows) {
    if (seen.has(row.path)) {
      continue;
    }
    seen.add(row.path);
    const segments = row.path.split("/");
    const names = row.display.split("/");
    let parent = root;
    parent.files += 1;
    let prefix = "";
    for (let index = 0; index < segments.length - 1; index += 1) {
      prefix += `${segments[index]}/`;
      let folder = folders.get(prefix);
      if (folder === undefined) {
        folder = {
          kind: "folder",
          id: prefix,
          name: names[index] ?? "�",
          files: 0,
          children: [],
        };
        folders.set(prefix, folder);
        parent.children.push(folder);
      }
      folder.files += 1;
      parent = folder;
    }
    parent.children.push({
      kind: "file",
      id: row.path,
      name: names[segments.length - 1] ?? "�",
      row,
    });
  }
  for (const folder of folders.values()) {
    folder.children.sort(byName);
  }
  folders.delete("");
  return { root, files: root.files, folderIds: [...folders.keys()] };
}

/**
 * Which folders are open: `all` says whether a folder no reader has touched is, and `toggled`
 * holds the ones a reader opened or closed, by id, so a folder a later page brings follows the
 * same rule as those before it.
 *
 * @typedef {{all: boolean, toggled: ReadonlyMap<string, boolean>}} Expansion
 */

/** The page size of GitHub's list, which its `Link` header counts in. */
const PAGE_FILES = 100;

/**
 * How folders start: all open when the list will hold at most *autoExpandFiles* files, and
 * otherwise all closed, so only the top level shows. A list still filling is judged by the
 * pages GitHub's `Link` header counted, so its folders do not start open on the first page
 * and closed after the last.
 *
 * @param {FilesEnvelope} envelope
 * @param {number} autoExpandFiles
 * @returns {Expansion}
 */
export function initialExpansion(envelope, autoExpandFiles) {
  const expected =
    !envelope.complete && envelope.last_page !== null
      ? Math.max(envelope.fetched, envelope.last_page * PAGE_FILES)
      : envelope.fetched;
  return { all: expected <= autoExpandFiles, toggled: new Map() };
}

/**
 * @param {Expansion} expansion
 * @param {string} id
 */
export function isOpen(expansion, id) {
  return expansion.toggled.get(id) ?? expansion.all;
}

/**
 * *expansion* with every folder above *path* open, so the row of the file the page shows can
 * be marked current where a reader sees it.
 *
 * @param {Expansion} expansion
 * @param {string} path
 * @returns {Expansion}
 */
export function revealPath(expansion, path) {
  const toggled = new Map(expansion.toggled);
  const segments = path.split("/");
  let prefix = "";
  for (let index = 0; index < segments.length - 1; index += 1) {
    prefix += `${segments[index]}/`;
    toggled.set(prefix, true);
  }
  return { all: expansion.all, toggled };
}

/**
 * *expansion* with a folder row toggled: every folder of its chain together, so a chain that a
 * later page splits keeps the state a reader gave it.
 *
 * @param {Expansion} expansion
 * @param {{ids: string[], expanded: boolean}} row
 * @returns {Expansion}
 */
export function toggleFolder(expansion, row) {
  const toggled = new Map(expansion.toggled);
  for (const id of row.ids) {
    toggled.set(id, !row.expanded);
  }
  return { all: expansion.all, toggled };
}

/**
 * The rows a reader sees: each open folder's children after it, one level deeper.
 *
 * @param {FileTree} tree
 * @param {Expansion} expansion
 * @param {{current?: string | null}} [options]
 * @returns {TreeRow[]}
 */
export function visibleRows(tree, expansion, options = {}) {
  const current = options.current ?? null;
  /** @type {TreeRow[]} */
  const rows = [];
  /**
   * @param {TreeNode[]} children
   * @param {number} depth
   */
  const walk = (children, depth) => {
    const setSize = children.length;
    for (const [index, node] of children.entries()) {
      const position = index + 1;
      if (node.kind === "file") {
        const status = /** @type {keyof typeof STATUS_BADGES} */ (node.row.status);
        rows.push({
          kind: "file",
          id: node.id,
          name: node.name,
          depth,
          position,
          setSize,
          path: node.row.path,
          display: node.row.display,
          badge: STATUS_BADGES[status] ?? "M",
          statusLabel: STATUS_LABELS[status] ?? node.row.status,
          additions: node.row.additions,
          deletions: node.row.deletions,
          previousName: node.row.previous_display,
          current: node.row.path === current,
        });
        continue;
      }
      let folder = node;
      const ids = [folder.id];
      const names = [folder.name];
      while (folder.children.length === 1 && folder.children[0].kind === "folder") {
        folder = folder.children[0];
        ids.push(folder.id);
        names.push(folder.name);
      }
      const open = isOpen(expansion, folder.id);
      rows.push({
        kind: "folder",
        id: folder.id,
        ids,
        name: names.join("/"),
        depth,
        position,
        setSize,
        expanded: open,
        files: folder.files,
      });
      if (open) {
        walk(folder.children, depth + 1);
      }
    }
  };
  walk(tree.root.children, 0);
  return rows;
}

/**
 * Which list an envelope's rows belong to. A list filling page by page keeps one identity,
 * since each page is published with the moment its read began; a new read is a new list.
 *
 * @param {FilesEnvelope} envelope
 */
function listIdentity(envelope) {
  return [
    envelope.listed_from,
    envelope.fetched_at,
    envelope.reader,
    envelope.base,
    envelope.head,
  ].join("|");
}

/**
 * The rows of one pull request's list, held as its pages arrive.
 *
 * `query()` is the window to ask for next: from the first row held, or past what is held
 * while the same list fills, so a poll carries only the new rows. `accept` takes an answer
 * and says whether the rows changed; an answer for another list, or one that does not start
 * where the rows held end, is not joined to them, and the next query starts again at 0.
 *
 * @param {number} number
 */
export function holdFileList(number) {
  /** @type {FileRow[]} */
  let rows = [];
  /** @type {string | null} */
  let identity = null;
  let restart = true;
  return {
    query() {
      const offset = restart ? 0 : rows.length;
      return `number=${number}&offset=${offset}`;
    },
    /** @param {FilesEnvelope} envelope */
    accept(envelope) {
      const same = identity !== null && listIdentity(envelope) === identity;
      if (envelope.listed_from === null) {
        const had = rows.length > 0;
        rows = [];
        identity = null;
        restart = true;
        return had;
      }
      if (envelope.offset === 0) {
        rows = envelope.rows.slice();
        identity = listIdentity(envelope);
        restart = false;
        return true;
      }
      if (!same || envelope.offset !== rows.length) {
        restart = true;
        return false;
      }
      if (envelope.rows.length === 0) {
        return false;
      }
      rows = rows.concat(envelope.rows);
      return true;
    },
    rows() {
      return rows;
    },
  };
}

/**
 * @param {number} count
 * @param {string} one
 */
function plural(count, one) {
  return `${count.toLocaleString("en-US")} ${one}${count === 1 ? "" : "s"}`;
}

/**
 * What a list is, and how much of it has arrived. Pure.
 *
 * `status` is `absent`, `pending` (asked for, nothing yet), `filling` (pages still arriving),
 * `stopped` (a read ended part-way), `stale`, or `current`. `count` is honest: the files the
 * server holds, and while GitHub's list fills, how many of the pages its `Link` header counted
 * have been read, since that counts pages and not files. `failure` is the last refresh when it
 * did not succeed, for the panel to word as it words a list's.
 *
 * @param {FilesEnvelope} envelope
 */
export function describeFileList(envelope) {
  const failed =
    envelope.last_refresh !== null &&
    envelope.last_refresh.outcome !== "succeeded" &&
    !envelope.refreshing
      ? envelope.last_refresh
      : null;
  if (envelope.listed_from === null) {
    return {
      status: envelope.state === "pending" ? "pending" : "absent",
      reason: envelope.reason,
      count: null,
      capped: false,
      truncated: false,
      failure: failed,
    };
  }
  const files = plural(envelope.fetched, "file");
  const pagesRead =
    envelope.last_page !== null ? `, ${envelope.pages} of ${envelope.last_page} pages` : "";
  /** @type {string} */
  let status = envelope.state;
  let count = files;
  if (!envelope.complete) {
    status = envelope.refreshing ? "filling" : "stopped";
    count = `${files} so far${pagesRead}`;
  } else if (envelope.capped) {
    count = `${files}, the most GitHub lists`;
  }
  return {
    status,
    reason: null,
    count,
    capped: envelope.capped,
    truncated: envelope.truncated,
    failure: failed,
  };
}

// ── The tree in a pull request's row ────────────────────────────

const FILES_ROUTE = "/api/plugin/github/pull-files";
const FILES_REFRESH_ROUTE = "/api/plugin/github/pull-files-refresh";

// How often a list that is filling is asked again: a page of GitHub's list took 1.2 to 1.6 s
// on the 1,183-file pull request, so a second shows each page about as it lands. Settled
// lists are read again once a freshness window, and a stale cached list asks for refresh
// only while its tree and panel are shown. An absent list needs a reader's own expansion.
export const FILES_POLL_MS = 1000;
// How long a walk of the files waits for a next key before the address names the file it
// rests on, once a key is repeating; a key's release names it at once. The diff jumps on every
// key, with no wait; only the history entry waits, so a held key does not replace it thirty
// times a second, past Safari's limit on `replaceState`. The same wait as a walk of the pull
// requests (WALK_SETTLE_MS in pulls-panel.js), past macOS's default key repeat of 90 ms.
export const FILE_WALK_SETTLE_MS = 120;

/** What a failed listing says to a reader, in what they can do about it. */
/** @type {Readonly<Record<string, string>>} */
const FILE_FAILURES = Object.freeze({
  gh_missing:
    "Metabrowser could not find GitHub CLI (gh). Install it from https://cli.github.com/, then run gh auth login --hostname github.com.",
  gh_too_old:
    "This GitHub CLI cannot report the active account. Update gh from https://cli.github.com/, then run gh auth status --hostname github.com.",
  not_logged_in:
    "GitHub CLI is not signed in to github.com. Run gh auth login --hostname github.com, then retry.",
  network_error: "Offline, or GitHub could not be reached. The files are as they were last listed.",
  not_found_or_private:
    "The pull request was not found, or the signed-in account cannot read its files.",
});

/** @type {Readonly<Record<string, string>>} */
const FILE_ABSENCE = Object.freeze({
  not_github: "This server serves no GitHub repository.",
  not_cached: "Its changed files have not been listed yet.",
  schema_mismatch: "The saved list of files is from another version.",
  unreadable: "The saved list of files could not be read.",
});

/**
 * What a list's last refresh says to a reader, or null when it says nothing: one that
 * succeeded, or one still running. A rate limit holds a reader's Retry too, since each
 * request GitHub refuses moves its time on. Pure.
 *
 * @param {FilesEnvelope} envelope
 * @param {(iso: string) => string} formatTime
 * @returns {{text: string, retry: boolean, help?: "install" | "update"} | null}
 */
export function fileListFailure(envelope, formatTime) {
  const last = describeFileList(envelope).failure;
  if (last === null) {
    return null;
  }
  if (last.outcome === "rate_limited") {
    return {
      text:
        last.reset_at === null
          ? "GitHub's rate limit was reached. No automatic attempt runs until it lifts."
          : `GitHub's rate limit lifts at ${formatTime(last.reset_at)}. No automatic attempt runs before then.`,
      retry: false,
    };
  }
  // What the job recorded is a clause; here it stands as a sentence of its own.
  const setup = ["gh_missing", "gh_too_old", "not_logged_in"].includes(last.outcome);
  const said = setup
    ? (last.message ?? FILE_FAILURES[last.outcome])
    : (FILE_FAILURES[last.outcome] ?? last.message ?? last.outcome.replaceAll("_", " "));
  const sentence = `${said.charAt(0).toUpperCase()}${said.slice(1)}`;
  const help =
    last.outcome === "gh_missing"
      ? "install"
      : last.outcome === "gh_too_old"
        ? "update"
        : undefined;
  const message = sentence.endsWith(".") ? sentence : `${sentence}.`;
  return {
    text:
      message + (setup ? " You can still browse local files and any cached pull requests." : ""),
    retry: true,
    ...(help === undefined ? {} : { help }),
  };
}

/**
 * What a pull request's row shows of its changed files.
 *
 * `line` is the honest count where it says more than the rows do: while the list fills, for
 * a list that stopped part-way, at GitHub's cap, or for a list that may be out of date;
 * `label` names the group for a screen reader, with the count. `notice` is a failure, a
 * list that is not there, or one cut short, with the action a reader can take: `retry`, or
 * `fetch` for a list nothing has asked for.
 *
 * @typedef {{
 *   number: number,
 *   expanded: boolean,
 *   rows: TreeRow[],
 *   rowsVersion: number,
 *   label: string,
 *   line: string | null,
 *   notice: {severity: "warning" | "error" | null, text: string, action: "retry" | "fetch" | null, help?: "install" | "update"} | null,
 *   skeleton: boolean,
 *   live: string,
 * }} FileTreeModel
 */

/**
 * @param {FilesEnvelope | null} envelope
 * @param {{
 *   number: number,
 *   expanded: boolean,
 *   rows: TreeRow[],
 *   rowsVersion: number,
 *   asked: boolean,
 *   error: string | null,
 *   formatTime: (iso: string) => string,
 * }} held
 * @returns {FileTreeModel}
 */
export function describeFileTree(envelope, held) {
  /** @type {FileTreeModel} */
  const model = {
    number: held.number,
    expanded: held.expanded,
    rows: held.rows,
    rowsVersion: held.rowsVersion,
    label: `Changed files of #${held.number}`,
    line: null,
    notice: null,
    skeleton: false,
    live: "",
  };
  if (envelope === null) {
    model.skeleton = held.error === null;
    if (held.error !== null) {
      model.notice = { severity: "error", text: held.error, action: "retry" };
    }
    return model;
  }
  const said = describeFileList(envelope);
  const failure = fileListFailure(envelope, held.formatTime);
  if (said.count !== null) {
    model.label = `${model.label}: ${said.count}`;
  }
  if (said.status === "absent" || said.status === "pending") {
    const waiting = said.status === "pending" || (held.asked && envelope.refreshing);
    model.skeleton = waiting && failure === null;
    const reason = said.reason === null ? undefined : FILE_ABSENCE[said.reason];
    if (failure !== null) {
      model.notice = {
        severity: "warning",
        text: failure.text,
        action: failure.retry ? "retry" : null,
        ...(failure.help === undefined ? {} : { help: failure.help }),
      };
    } else if (!waiting && reason !== undefined) {
      model.notice = {
        severity: null,
        text: reason,
        action: said.reason === "not_github" ? null : "fetch",
      };
    }
    model.live = waiting ? "Listing the changed files…" : (model.notice?.text ?? "");
  } else {
    if (said.status === "filling") {
      model.line = said.count;
    } else if (said.status === "stopped") {
      model.line = said.count;
      model.notice ??= {
        severity: "warning",
        text: "The list stopped part-way.",
        action: "retry",
      };
    } else if (envelope.fetched === 0) {
      model.line = "No changed files.";
    } else if (said.capped) {
      model.line = said.count;
    } else if (said.status === "stale") {
      model.line = `${said.count} · may be out of date`;
    }
    if (failure !== null) {
      model.notice = {
        severity: "warning",
        text: failure.text,
        action: failure.retry ? "retry" : null,
        ...(failure.help === undefined ? {} : { help: failure.help }),
      };
    } else if (said.truncated && model.notice === null) {
      model.notice = {
        severity: "warning",
        text: "Some files could not be read and are left out.",
        action: null,
      };
    }
    // The count, whether or not anything changed: a refresh that changes nothing says nothing.
    model.live = model.notice?.text ?? model.label;
  }
  if (held.error !== null) {
    model.notice = { severity: "error", text: held.error, action: null };
    model.live = held.error;
  }
  return model;
}

/**
 * @param {unknown} value
 * @returns {value is FilesEnvelope}
 */
function isFilesEnvelope(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const envelope = /** @type {Record<string, unknown>} */ (value);
  return (
    typeof envelope.state === "string" &&
    typeof envelope.refreshing === "boolean" &&
    typeof envelope.offset === "number" &&
    Array.isArray(envelope.rows)
  );
}

/**
 * The page a file row jumps in, when it is this pull request's and holds the pane: the
 * pull-request page's handle, typed as far as the tree reads it.
 *
 * @typedef {{
 *   fileForPath(path: string): {kind: string},
 *   showFile(path: string): {kind: string},
 * }} FilePage
 */

/**
 * @typedef {{
 *   request(
 *     method: "GET" | "POST",
 *     route: string,
 *     options: {body?: unknown, signal?: AbortSignal},
 *   ): Promise<{status: number, etag: string | null, body: unknown}>,
 *   schedule(callback: () => void, delayMs: number): unknown,
 *   cancel(handle: unknown): void,
 *   now(): number,
 *   isVisible(): boolean,
 *   formatTime(iso: string): string,
 *   render(model: FileTreeModel): void,
 *   markAnchor(previous: string | null, next: string | null, focus: boolean): void,
 *   markCurrent(previous: string | null, next: string | null): void,
 *   markMuted(id: string): void,
 *   page(): FilePage | null,
 *   open(route: {file: string, replace: boolean, jumped: boolean}): void,
 *   leave(): void,
 * }} FileTreeDependencies
 */

/**
 * One pull request's changed files in its row: the list as it arrives, which folders are
 * open, which row takes Tab and which file the page shows, the keys, and the jump.
 *
 * Reading never fetches: a list is asked for (`POST pull-files-refresh`) only on a reader's
 * expansion or press of Fetch or Retry, or, for a list already cached that may be out of
 * date, once a window, which the server holds it to as well. While a list fills it is asked
 * again every FILES_POLL_MS, from the rows held on, and only while its row is expanded and
 * the panel shown.
 *
 * A walk with the keys moves the anchor and the current file at once. When the page holds
 * this pull request, every key jumps the diff to the file (`showFile`, after `fileForPath`
 * says the comparison has it), with no wait of its own, and the address names the file only
 * once the walk stops (FILE_WALK_SETTLE_MS), so a skim replaces one history entry. When it
 * does not, the page is opened at the file, at once for a single press and when the walk
 * stops for a held key. A click or Enter opens the file's address and pushes it. A folder
 * row opens nothing.
 *
 * @param {FileTreeDependencies} deps
 * @param {{number: number, autoExpandFiles: number, current?: string | null, shown?: boolean}} options
 */
export function createFileTreeController(deps, options) {
  const number = options.number;
  const holder = holdFileList(number);
  /** @type {FilesEnvelope | null} */
  let envelope = null;
  /** @type {Expansion | null} */
  let expansion = null;
  /** @type {FileTree | null} */
  let tree = null;
  /** @type {TreeRow[]} */
  let rows = [];
  /** @type {Map<string, number>} */
  let index = new Map();
  let version = 0;
  let expanded = false;
  let shown = options.shown !== false;
  let disposed = false;
  /** The row that takes Tab. @type {string | null} */
  let anchor = null;
  /** The file the page shows, or a walk rests on. @type {string | null} */
  let current = options.current ?? null;
  /** @type {unknown} */
  let timer = null;
  /** @type {AbortController | null} */
  let inflight = null;
  let polling = false;
  let generation = 0;
  /** When this asked for a refresh of its own, a reader's or one a window. */
  /** @type {number | null} */
  let askedAt = null;
  let asked = false;
  /** @type {string | null} */
  let error = null;
  /** @type {string | null} */
  let painted = null;
  /** @type {unknown} */
  let walkTimer = null;
  /** The file a walk rests on, whose address waits for the walk to stop. @type {string | null} */
  let walkPath = null;
  let walkJumped = false;
  /** Rows the comparison does not hold, which the page cannot jump to. @type {Set<string>} */
  const muted = new Set();

  function live() {
    return expanded && shown && !disposed && deps.isVisible();
  }

  function model() {
    return describeFileTree(envelope, {
      number,
      expanded,
      rows,
      rowsVersion: version,
      asked,
      error,
      formatTime: deps.formatTime,
    });
  }

  // Compared without its rows, which their version stands for.
  function render() {
    if (disposed) {
      return;
    }
    const next = model();
    const key = JSON.stringify({ ...next, rows: null });
    if (key !== painted) {
      painted = key;
      deps.render(next);
    }
  }

  /**
   * The nearest row a reader can see that holds *id*: itself, or the folder it is in.
   *
   * @param {string} id
   */
  function nearestShown(id) {
    if (index.has(id)) {
      return id;
    }
    const segments = id.replace(/\/$/, "").split("/");
    for (let end = segments.length - 1; end > 0; end -= 1) {
      const folder = `${segments.slice(0, end).join("/")}/`;
      if (index.has(folder)) {
        return folder;
      }
    }
    return null;
  }

  /** The anchor stays on its row, or the folder that now holds it, or the current file. */
  function settleAnchor() {
    const next =
      (anchor === null ? null : nearestShown(anchor)) ??
      (current !== null && index.has(current) ? current : null) ??
      rows[0]?.id ??
      null;
    if (next !== anchor) {
      const previous = anchor;
      anchor = next;
      deps.markAnchor(previous, next, false);
    }
  }

  /** The rows a reader sees, from the tree and the folders open. */
  function restate() {
    rows = tree === null || expansion === null ? [] : visibleRows(tree, expansion);
    index = new Map(rows.map((row, at) => [row.id, at]));
    version += 1;
    settleAnchor();
  }

  /** The tree again, from the rows held: the first rows decide which folders start open. */
  function rebuild() {
    const held = holder.rows();
    if (expansion === null && held.length > 0 && envelope !== null) {
      expansion = initialExpansion(envelope, options.autoExpandFiles);
      if (current !== null) {
        expansion = revealPath(expansion, current);
      }
    }
    tree = held.length > 0 ? buildFileTree(held) : null;
    restate();
  }

  function clearTimer() {
    if (timer !== null) {
      deps.cancel(timer);
      timer = null;
    }
  }

  // Replies belong to one visible visit. Cancellation releases the GET immediately even
  // when its transport takes time to abort; an old finally cannot release a newer read.
  function cancelRequests() {
    generation += 1;
    inflight?.abort();
    inflight = null;
    polling = false;
  }

  /** @param {boolean} [now] */
  function scheduleNext(now = false) {
    clearTimer();
    if (!live()) {
      return;
    }
    if (envelope === null) {
      timer = deps.schedule(() => {
        timer = null;
        void poll();
      }, FILES_POLL_MS);
      return;
    }
    timer = deps.schedule(
      () => {
        timer = null;
        void poll();
      },
      now
        ? 0
        : envelope.refreshing || envelope.state === "pending"
          ? FILES_POLL_MS
          : Math.max(FILES_POLL_MS, envelope.fresh_for_s * 1000),
    );
  }

  /** Read the rows past those held. @param {boolean} [reader] */
  async function poll(reader = false) {
    if (!live() || polling) {
      return;
    }
    polling = true;
    const controller = new AbortController();
    inflight = controller;
    let again = false;
    try {
      const response = await deps.request("GET", `${FILES_ROUTE}?${holder.query()}`, {
        signal: controller.signal,
      });
      if (inflight !== controller || controller.signal.aborted || !live()) {
        return;
      }
      if (response.status === 200 && isFilesEnvelope(response.body)) {
        envelope = response.body;
        error = null;
        const changed = holder.accept(envelope);
        if (changed) {
          rebuild();
        } else if (envelope.offset !== 0 && holder.query().endsWith("offset=0")) {
          // The rows did not follow those held: another list, read again from its start.
          again = true;
        }
      } else {
        error = `The list of files is unavailable (HTTP ${response.status}).`;
      }
    } catch {
      if (inflight !== controller || controller.signal.aborted || !live()) {
        return;
      }
      error = "The server did not answer.";
    } finally {
      if (inflight === controller) {
        inflight = null;
        polling = false;
      }
    }
    render();
    if (!again) {
      askIfDue(reader);
    }
    scheduleNext(again);
  }

  /**
   * Ask for the list's refresh: a reader's action, or a cached list that may be out of date.
   *
   * @param {boolean} retry A press of Retry or Fetch, which the server's window does not hold.
   */
  async function ask(retry) {
    if (!live()) {
      return;
    }
    const mine = generation;
    asked = true;
    askedAt = deps.now();
    try {
      const response = await deps.request("POST", FILES_REFRESH_ROUTE, {
        body: { number, retry },
      });
      if (mine !== generation || !live()) {
        return;
      }
      const answer = /** @type {{files?: unknown, error?: unknown} | null} */ (response.body);
      if (
        (response.status === 202 || response.status === 200) &&
        answer !== null &&
        isFilesEnvelope(answer.files)
      ) {
        // Its envelope has no rows: it says how the list stands, and the rows held stay.
        envelope = { ...answer.files, rows: [] };
        error = null;
      } else {
        const said = answer !== null && typeof answer.error === "string" ? answer.error : null;
        error = `The list of files was not asked for (${said ?? `HTTP ${response.status}`}).`;
      }
    } catch {
      if (mine !== generation || !live()) {
        return;
      }
      error = "The request to list the files failed.";
    }
    render();
    scheduleNext();
  }

  /**
   * Ask when a reader expanded the row and the list is not whole and current, or once a
   * window for a cached list that may be out of date. An absent list is asked for only by a
   * reader: an address alone adds nothing to the cache.
   *
   * @param {boolean} reader
   */
  function askIfDue(reader) {
    if (disposed || !expanded || (!reader && !live()) || envelope === null || envelope.refreshing) {
      return;
    }
    if (envelope.reason === "not_github") {
      return;
    }
    if (envelope.state === "current" && envelope.complete) {
      return;
    }
    if (!reader && envelope.listed_from === null) {
      return;
    }
    const windowMs = envelope.fresh_for_s * 1000;
    if (askedAt !== null && deps.now() - askedAt < windowMs) {
      return;
    }
    void ask(false);
  }

  function clearWalk() {
    if (walkTimer !== null) {
      deps.cancel(walkTimer);
      walkTimer = null;
    }
    walkPath = null;
    walkJumped = false;
  }

  /** @param {string} path */
  function mute(path) {
    if (!muted.has(path)) {
      muted.add(path);
      deps.markMuted(path);
    }
  }

  /** @param {string | null} path */
  function markCurrent(path) {
    if (path !== current) {
      const previous = current;
      current = path;
      deps.markCurrent(previous, path);
    }
  }

  /**
   * @param {string} id
   * @param {boolean} focus
   */
  function setAnchor(id, focus) {
    const previous = anchor;
    anchor = id;
    deps.markAnchor(previous, id, focus);
  }

  /**
   * Jump the diff of this pull request's page to a file, when the comparison has it.
   *
   * @param {FilePage} page
   * @param {string} path
   */
  function jumpInPage(page, path) {
    if (page.fileForPath(path).kind === "not_in_comparison") {
      mute(path);
      return;
    }
    if (page.showFile(path).kind === "not_in_comparison") {
      mute(path);
    }
  }

  /** The walk stopped: the address names the file it rests on. */
  function settleWalk() {
    const path = walkPath;
    const jumped = walkJumped;
    clearWalk();
    if (path !== null && !disposed) {
      deps.open({ file: path, replace: true, jumped });
    }
  }

  /**
   * A key moved to a file.
   *
   * @param {string} path
   * @param {boolean} repeat
   */
  function walkTo(path, repeat) {
    markCurrent(path);
    const page = deps.page();
    if (page !== null) {
      jumpInPage(page, path);
    }
    if (walkTimer !== null) {
      deps.cancel(walkTimer);
      walkTimer = null;
    }
    walkPath = path;
    walkJumped = page !== null;
    if (repeat) {
      walkTimer = deps.schedule(settleWalk, FILE_WALK_SETTLE_MS);
    } else {
      settleWalk();
    }
  }

  /**
   * Open a file's address, as a click or Enter does: it pushes.
   *
   * @param {string} path
   */
  function openFile(path) {
    clearWalk();
    markCurrent(path);
    const page = deps.page();
    if (page !== null && page.fileForPath(path).kind === "not_in_comparison") {
      mute(path);
    }
    deps.open({ file: path, replace: false, jumped: false });
  }

  /** @param {TreeRow} row */
  function toggle(row) {
    if (row.kind !== "folder" || expansion === null) {
      return;
    }
    expansion = toggleFolder(expansion, row);
    restate();
    render();
  }

  /**
   * The row that holds the row at *at*, a level up, or null at the top.
   *
   * @param {number} at
   */
  function parentOf(at) {
    const depth = rows[at].depth;
    for (let row = at - 1; row >= 0; row -= 1) {
      if (rows[row].depth < depth) {
        return row;
      }
    }
    return null;
  }

  /** Follow a file already shown by the page, without invalidating an active walk. @param {string | null} path */
  function followCurrent(path) {
    if (disposed) {
      return;
    }
    markCurrent(path);
    if (path !== null && expansion !== null && !index.has(path)) {
      expansion = revealPath(expansion, path);
      restate();
      render();
    }
  }

  return Object.freeze({
    /**
     * The row was expanded. *reader* is a reader's own: a click, a key, or opening a file of it.
     *
     * @param {{reader?: boolean}} [how]
     */
    expand(how = {}) {
      if (disposed) {
        return;
      }
      const reader = how.reader === true;
      const opening = !expanded;
      if (opening) {
        expanded = true;
        render();
      }
      if (opening || envelope === null) {
        void poll(reader);
      } else {
        askIfDue(reader);
        scheduleNext();
      }
    },
    collapse() {
      if (disposed || !expanded) {
        return;
      }
      expanded = false;
      clearTimer();
      cancelRequests();
      clearWalk();
      render();
    },
    /** @param {boolean} visible */
    setShown(visible) {
      if (disposed || visible === shown) {
        return;
      }
      shown = visible;
      if (!visible) {
        clearTimer();
        cancelRequests();
        clearWalk();
      } else if (expanded) {
        void poll();
      }
    },
    onVisibilityChange() {
      if (disposed) {
        return;
      }
      if (!deps.isVisible()) {
        clearTimer();
        cancelRequests();
        clearWalk();
      } else if (expanded && shown) {
        void poll();
      }
    },
    /** A route selected this file; any earlier delayed keyboard open is obsolete. @param {string | null} path */
    setCurrent(path) {
      clearWalk();
      followCurrent(path);
    },
    /** The diff reported its position; this can be feedback from the active walk itself. */
    followCurrent,
    /** Another route, focused tree, or panel owns the next navigation. */
    cancelWalk: clearWalk,
    /**
     * Move by a key, over the rows a reader sees, folders and files alike. Clamped at the ends,
     * where it opens nothing again.
     *
     * @param {-1 | 1} delta
     * @param {{repeat?: boolean}} [how]
     * @returns {boolean} Whether the key was the tree's.
     */
    move(delta, how = {}) {
      if (disposed || !expanded || rows.length === 0) {
        return false;
      }
      const at = anchor === null ? -1 : (index.get(anchor) ?? -1);
      const target =
        at < 0
          ? delta > 0
            ? 0
            : rows.length - 1
          : Math.max(0, Math.min(rows.length - 1, at + delta));
      if (target === at) {
        return true;
      }
      const row = rows[target];
      setAnchor(row.id, true);
      if (row.kind === "file") {
        walkTo(row.path, how.repeat === true);
      }
      return true;
    },
    /** The key that was walking was let go: the address names the file it rests on. */
    released() {
      if (walkTimer !== null) {
        deps.cancel(walkTimer);
        walkTimer = null;
        settleWalk();
      }
    },
    /** Left: a folder that is open closes; anything else goes to the row that holds it. */
    left() {
      const at = anchor === null ? undefined : index.get(anchor);
      if (disposed || at === undefined) {
        return false;
      }
      const row = rows[at];
      if (row.kind === "folder" && row.expanded) {
        toggle(row);
        return true;
      }
      const parent = parentOf(at);
      if (parent === null) {
        deps.leave();
      } else {
        setAnchor(rows[parent].id, true);
      }
      return true;
    },
    /** Right: a closed folder opens, and an open one goes to its first row. */
    right() {
      const at = anchor === null ? undefined : index.get(anchor);
      if (disposed || at === undefined) {
        return false;
      }
      const row = rows[at];
      if (row.kind !== "folder") {
        return true;
      }
      if (!row.expanded) {
        toggle(row);
      } else if (rows[at + 1] !== undefined && rows[at + 1].depth > row.depth) {
        const child = rows[at + 1];
        setAnchor(child.id, true);
        if (child.kind === "file") {
          walkTo(child.path, false);
        }
      }
      return true;
    },
    /** Enter or Space on the row that holds focus: a folder toggles, and a file opens. */
    activateAnchor() {
      const at = anchor === null ? undefined : index.get(anchor);
      if (disposed || at === undefined) {
        return false;
      }
      const row = rows[at];
      if (row.kind === "folder") {
        toggle(row);
      } else {
        openFile(row.path);
      }
      return true;
    },
    /**
     * A pointer chose a row: a folder toggles, as in the Files tab, and a file opens.
     *
     * @param {string} id
     */
    activate(id) {
      const at = index.get(id);
      if (disposed || at === undefined) {
        return;
      }
      if (anchor !== id) {
        setAnchor(id, false);
      }
      const row = rows[at];
      if (row.kind === "folder") {
        toggle(row);
      } else {
        openFile(row.path);
      }
    },
    /**
     * Focus reached a row by Tab or the pointer: it takes the anchor, and nothing opens.
     *
     * @param {string} id
     */
    focused(id) {
      if (!disposed && anchor !== id && index.has(id)) {
        setAnchor(id, false);
      }
    },
    /** Focus the row that takes Tab, as Right from the pull request's row does. */
    enter() {
      if (disposed || !expanded || anchor === null) {
        return false;
      }
      deps.markAnchor(anchor, anchor, true);
      return true;
    },
    /** A press of Retry, or of Fetch for a list nothing has asked for. */
    retry() {
      if (disposed) {
        return Promise.resolve();
      }
      error = null;
      return envelope === null ? poll() : ask(true);
    },
    /** Whether a row is one the comparison lacks. @param {string} id */
    isMuted: (id) => muted.has(id),
    current: () => current,
    anchor: () => anchor,
    dispose() {
      disposed = true;
      clearTimer();
      clearWalk();
      cancelRequests();
    },
    snapshot: () => ({
      expanded,
      rows: rows.length,
      held: holder.rows().length,
      anchor,
      current,
      walking: walkTimer !== null ? walkPath : null,
      timer: timer === null ? null : "poll",
      muted: [...muted],
      asked,
    }),
  });
}

/**
 * Which pull requests' rows are expanded, and why: a reader's own click or key, or the row of
 * the page the pane shows, which is expanded for the reader and closed again when the pane
 * moves on, unless a reader opened it. Pure.
 */
export function createRowExpansion() {
  /** @type {Map<number, "reader" | "shown">} */
  const by = new Map();
  /** @type {number | null} */
  let shownNumber = null;
  return Object.freeze({
    /** @param {number} number */
    isExpanded: (number) => by.has(number),
    /**
     * A reader's click on the row: it opens its files, or closes them.
     *
     * @param {number} number
     * @returns {boolean} Whether the row is now expanded.
     */
    toggle(number) {
      if (by.has(number)) {
        by.delete(number);
        return false;
      }
      by.set(number, "reader");
      return true;
    },
    /**
     * A reader's Right, or opening a file of it: it opens, and stays open.
     *
     * @param {number} number
     * @returns {boolean} Whether it changed.
     */
    expand(number) {
      const had = by.has(number);
      by.set(number, "reader");
      return !had;
    },
    /** @param {number} number @returns {boolean} Whether it changed. */
    collapse(number) {
      return by.delete(number);
    },
    /**
     * The page of *number* holds the pane, or none does. Its row opens; the row of the page
     * before it closes again if only the page had opened it.
     *
     * @param {number | null} number
     * @returns {{expand: number[], collapse: number[]}}
     */
    shown(number) {
      /** @type {{expand: number[], collapse: number[]}} */
      const changes = { expand: [], collapse: [] };
      if (number === shownNumber) {
        return changes;
      }
      if (shownNumber !== null && by.get(shownNumber) === "shown") {
        by.delete(shownNumber);
        changes.collapse.push(shownNumber);
      }
      shownNumber = number;
      if (number !== null && !by.has(number)) {
        by.set(number, "shown");
        changes.expand.push(number);
      }
      return changes;
    },
    snapshot: () => Object.fromEntries(by),
  });
}

/**
 * Which rows of a list of *count* rows *rowHeight* tall to draw: those in the view, from
 * *viewTop* to *viewBottom*, and *overscan* more each way, with the list's own top at
 * *listTop*, all on one axis. A list at the cap is 3,346 rows, so only these are in the
 * document, and a step of a key or a scroll changes a few of them. Pure.
 *
 * @param {{count: number, rowHeight: number, viewTop: number, viewBottom: number, listTop: number, overscan: number}} where
 * @returns {{start: number, end: number}}
 */
export function windowRange({ count, rowHeight, viewTop, viewBottom, listTop, overscan }) {
  if (count <= 0 || !(rowHeight > 0)) {
    return { start: 0, end: 0 };
  }
  const first = Math.floor((viewTop - listTop) / rowHeight) - overscan;
  const last = Math.ceil((viewBottom - listTop) / rowHeight) + overscan;
  const start = Math.max(0, Math.min(count, first));
  const end = Math.max(start, Math.min(count, last));
  return { start, end };
}
