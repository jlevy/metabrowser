// A pull request's changed files as a tree, the way a folder expands in the Files tab.
//
// Every decision lives here without a DOM, and the tree is built from the list of files the
// `pull-files` route answers, never from hydrated diff documents. `holdFileList` keeps the rows
// of one list as its pages arrive and says which window to ask for next; `buildFileTree` makes
// folders of their paths; `visibleRows` flattens the folders a reader has expanded into rows,
// drawing a folder whose only child is a folder as one row, `src/metabrowser`, as GitHub's file
// tree does, with which folders are open decided by `initialExpansion` and a reader's toggles;
// `describeFileList` says what the list is and how much of it has arrived. Painting,
// the gesture, and the keyboard are the panel's. tests/dom/github-pull-files-tree-session.js
// runs these functions from the command line on what the server answered.
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
 * @typedef {{
 *   kind: "folder",
 *   id: string,
 *   ids: string[],
 *   name: string,
 *   depth: number,
 *   expanded: boolean,
 *   files: number,
 * } | {
 *   kind: "file",
 *   id: string,
 *   name: string,
 *   depth: number,
 *   path: string,
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
    for (const node of children) {
      if (node.kind === "file") {
        const status = /** @type {keyof typeof STATUS_BADGES} */ (node.row.status);
        rows.push({
          kind: "file",
          id: node.id,
          name: node.name,
          depth,
          path: node.row.path,
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
  return [envelope.listed_from, envelope.fetched_at, envelope.reader, envelope.head].join("|");
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
