// A change set's files as a tree: the one model behind every tree of changed files.
//
// Two surfaces draw it. The Pulls tab hangs a pull request's changed files under its row
// (builtin_plugins/github/pull-files-tree.js and pull-files-view.js), from the list the
// `pull-files` route answers; a multi-file diff opens with its Diff summary
// (builtin_plugins/diff/diff-summary.js), from the files its comparison holds. They are two
// plugins, so the model is the shell's: this is the `changed-files-tree` on-demand bundle,
// which a plugin reaches through the SDK, `metabrowser.loadChangedFilesTree()`, and never by
// a URL into another plugin. Nothing here touches the DOM, so the sessions that pin both
// trees (tests/dom/github-pull-files-tree-session.js, tests/dom/diff-summary-session.js)
// run this file as it ships.
//
// `buildFileTree` makes folders of a list's paths and rolls each folder's line counts up
// from the files under it; `visibleRows` flattens the folders a reader has open into rows,
// drawing a folder whose only child is a folder as one row, `src/metabrowser`, as GitHub's
// file tree does; `isOpen`, `toggleFolder`, `revealPath`, and `expansionFor` are which
// folders are open; `parentIndex` and `windowRange` are what a tree's keys and its windowed
// paint ask of its rows; `statusBreakdown`, `describeChanges`, and `changeStats` say what a
// change set and a row hold, in the words and signs a reader sees.
//
// A path is text whoever made the change wrote. It is a row's identity and the path a jump
// is given, a rename's new path; what is painted is the row's `display`, and a name never
// reaches markup. A folder's identity ends in "/", so a file and a folder of one name, as a
// file replaced by a directory lists them, are two rows.
//
// Measured 2026-11-03 with Node 24.19 on real lists as the route answered them, the median
// of 25 runs twice at a load average of 4.5: building the tree and flattening it with every
// folder expanded took 1.3 ms for the first 1,183 files of django/django#15387 (1,503 rows)
// and 3.7 ms for the 3,000 nodejs/node#65161 lists (3,346 rows), so a tree is built again
// whenever its list changes. The roll-ups add one sum per folder on a file's path, in the
// same walk.

(() => {
  /**
   * The one-letter badge a file carries in place of an icon, by status. The statuses are
   * GitHub's, which the `pull-files` route answers, and `unmerged`, which a local comparison
   * can hold (docs/design-system.md, "File Change Status").
   */
  const STATUS_BADGES = Object.freeze({
    added: "A",
    removed: "D",
    modified: "M",
    renamed: "R",
    copied: "C",
    changed: "T",
    unchanged: "M",
    unmerged: "U",
  });

  /** What a badge's tooltip and accessible name say, by status. */
  const STATUS_LABELS = Object.freeze({
    added: "Added",
    removed: "Deleted",
    modified: "Modified",
    renamed: "Renamed",
    copied: "Copied",
    changed: "Type changed",
    unchanged: "Unchanged",
    unmerged: "Unmerged",
  });

  /**
   * What a change set's header calls each status, in the order it lists them: added,
   * removed, modified, and renamed first, as the reader asked, then the rest in this order,
   * then any status this does not know, by name.
   */
  const STATUS_WORDS = Object.freeze({
    added: "added",
    removed: "removed",
    modified: "modified",
    renamed: "renamed",
    copied: "copied",
    changed: "type changed",
    unmerged: "unmerged",
    unchanged: "unchanged",
  });
  const STATUS_ORDER = Object.freeze(Object.keys(STATUS_WORDS));

  /** U+2212, the minus sign every change stat is written with. */
  const MINUS = "−";

  /**
   * The same order wherever it runs: folders first, then by name without case, then by the
   * name itself, so no locale's collation decides it.
   *
   * @param {MetabrowserChangedFilesNode} left
   * @param {MetabrowserChangedFilesNode} right
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
   * One side's count added to a folder's: a count no file under it knows stays unknown
   * (null), and once any file knows its count the folder's is the sum of those that do.
   *
   * @param {number | null} total
   * @param {number | null} count
   * @returns {number | null}
   */
  function rollUp(total, count) {
    if (count === null) {
      return total;
    }
    return (total ?? 0) + count;
  }

  /**
   * Folders of the rows' paths, each with its files and its line counts rolled up from them.
   * Each path is split on "/", and each segment is named by the same segment of `display`,
   * which a display rule keeps one for one. A path listed twice counts once.
   *
   * A folder's `additions` and `deletions` are the sums of the counts its files know, and
   * null only when none of them knows one; `unknown` is how many of its files know neither,
   * as a binary file does, so a reader can be told the sum leaves them out.
   *
   * @param {ReadonlyArray<MetabrowserChangedFileRow>} rows
   * @returns {MetabrowserChangedFilesTreeModel}
   */
  function buildFileTree(rows) {
    /** @type {MetabrowserChangedFilesFolder} */
    const root = {
      kind: "folder",
      id: "",
      name: "",
      files: 0,
      additions: null,
      deletions: null,
      unknown: 0,
      children: [],
    };
    /** @type {Map<string, MetabrowserChangedFilesFolder>} */
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
      const unknown = row.additions === null && row.deletions === null ? 1 : 0;
      /** @param {MetabrowserChangedFilesFolder} folder */
      const count = (folder) => {
        folder.files += 1;
        folder.additions = rollUp(folder.additions, row.additions);
        folder.deletions = rollUp(folder.deletions, row.deletions);
        folder.unknown += unknown;
      };
      let parent = root;
      count(parent);
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
            additions: null,
            deletions: null,
            unknown: 0,
            children: [],
          };
          folders.set(prefix, folder);
          parent.children.push(folder);
        }
        count(folder);
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
   * How folders start: every folder open when the list holds at most *autoExpandFiles*
   * files, and otherwise every folder closed, so only the top level shows. Neither is a
   * reader's choice, so `toggled` starts empty.
   *
   * @param {number} files
   * @param {number} autoExpandFiles
   * @returns {MetabrowserChangedFilesExpansion}
   */
  function expansionFor(files, autoExpandFiles) {
    return { all: files <= autoExpandFiles, toggled: new Map() };
  }

  /**
   * @param {MetabrowserChangedFilesExpansion} expansion
   * @param {string} id
   */
  function isOpen(expansion, id) {
    return expansion.toggled.get(id) ?? expansion.all;
  }

  /**
   * *expansion* with every folder above *path* open, so the row of the file a page shows can
   * be marked where a reader sees it.
   *
   * @param {MetabrowserChangedFilesExpansion} expansion
   * @param {string} path
   * @returns {MetabrowserChangedFilesExpansion}
   */
  function revealPath(expansion, path) {
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
   * *expansion* with a folder row toggled: every folder of its chain together, so a chain
   * that a later list splits keeps the state a reader gave it.
   *
   * @param {MetabrowserChangedFilesExpansion} expansion
   * @param {{ids: ReadonlyArray<string>, expanded: boolean}} row
   * @returns {MetabrowserChangedFilesExpansion}
   */
  function toggleFolder(expansion, row) {
    const toggled = new Map(expansion.toggled);
    for (const id of row.ids) {
      toggled.set(id, !row.expanded);
    }
    return { all: expansion.all, toggled };
  }

  /**
   * The rows a reader sees: each open folder's children after it, one level deeper.
   *
   * A folder row stands for its chain: `ids` are the chain's folders, top first, and `id`
   * the deepest, whose children follow it when it is open. Its `files`, `additions`,
   * `deletions`, and `unknown` are the chain's, which are its deepest folder's, since every
   * file under the chain is under that folder. `position` and `setSize` are a row's place
   * among its parent's children, a chain counting as one, for `aria-posinset` and
   * `aria-setsize`: a row out of view is not in the document.
   *
   * @param {MetabrowserChangedFilesTreeModel} tree
   * @param {MetabrowserChangedFilesExpansion} expansion
   * @param {{current?: string | null}} [options]
   * @returns {MetabrowserChangedFilesRow[]}
   */
  function visibleRows(tree, expansion, options = {}) {
    const current = options.current ?? null;
    /** @type {MetabrowserChangedFilesRow[]} */
    const rows = [];
    /**
     * @param {MetabrowserChangedFilesNode[]} children
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
            badge: STATUS_BADGES[status] ?? "?",
            status: node.row.status,
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
          additions: folder.additions,
          deletions: folder.deletions,
          unknown: folder.unknown,
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
   * The row that holds the row at *at*, a level up, or null at the top: where Left goes.
   *
   * @param {ReadonlyArray<{depth: number}>} rows
   * @param {number} at
   * @returns {number | null}
   */
  function parentIndex(rows, at) {
    const depth = rows[at]?.depth ?? 0;
    for (let row = at - 1; row >= 0; row -= 1) {
      if (rows[row].depth < depth) {
        return row;
      }
    }
    return null;
  }

  /**
   * Which rows of a list of *count* rows *rowHeight* tall to draw: those in the view, from
   * *viewTop* to *viewBottom*, and *overscan* more each way, with the list's own top at
   * *listTop*, all on one axis. A list at GitHub's cap is 3,346 rows, so only these are in
   * the document, and a step of a key or a scroll changes a few of them.
   *
   * @param {{count: number, rowHeight: number, viewTop: number, viewBottom: number, listTop: number, overscan: number}} where
   * @returns {{start: number, end: number}}
   */
  function windowRange({ count, rowHeight, viewTop, viewBottom, listTop, overscan }) {
    if (count <= 0 || !(rowHeight > 0)) {
      return { start: 0, end: 0 };
    }
    const first = Math.floor((viewTop - listTop) / rowHeight) - overscan;
    const last = Math.ceil((viewBottom - listTop) / rowHeight) + overscan;
    const start = Math.max(0, Math.min(count, first));
    const end = Math.max(start, Math.min(count, last));
    return { start, end };
  }

  /**
   * How many files have each status, in the header's order, leaving out the statuses no
   * file has.
   *
   * @param {Iterable<string>} statuses One per file.
   * @returns {Array<{status: string, count: number, word: string}>}
   */
  function statusBreakdown(statuses) {
    /** @type {Map<string, number>} */
    const counts = new Map();
    for (const status of statuses) {
      counts.set(status, (counts.get(status) ?? 0) + 1);
    }
    const known = STATUS_ORDER.filter((status) => counts.has(status));
    const others = [...counts.keys()]
      .filter((status) => !STATUS_ORDER.includes(status))
      .sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
    return [...known, ...others].map((status) => ({
      status,
      count: counts.get(status) ?? 0,
      word: STATUS_WORDS[/** @type {keyof typeof STATUS_WORDS} */ (status)] ?? status,
    }));
  }

  /**
   * What a change set's header says, in its parts: the file count, which statuses make it
   * up, and its line totals, each written with *formatCount*, the shell's number format.
   *
   * `files` is "35 changed files"; `breakdown` is "2 added, 3 removed, 30 modified", or ""
   * for no files; `additions` and `deletions` are "+1,234" and "−3,423", with "?" for a
   * total the change set does not know; `estimated` is whether the totals are not exact,
   * which the header says as "(estimated)"; `text` is the whole line as it reads; and
   * `label` is what a screen reader is told, with the signs said as words.
   *
   * @param {{files: number, additions: number | null, deletions: number | null, exact: boolean}} totals
   * @param {Iterable<string>} statuses One per file listed.
   * @param {(count: number) => string} formatCount
   * @returns {MetabrowserChangedFilesSummary}
   */
  function describeChanges(totals, statuses, formatCount) {
    const files = `${formatCount(totals.files)} changed ${totals.files === 1 ? "file" : "files"}`;
    const breakdown = statusBreakdown(statuses)
      .map((entry) => `${formatCount(entry.count)} ${entry.word}`)
      .join(", ");
    const added = totals.additions === null ? "?" : formatCount(totals.additions);
    const deleted = totals.deletions === null ? "?" : formatCount(totals.deletions);
    const additions = `+${added}`;
    const deletions = `${MINUS}${deleted}`;
    const estimated = !totals.exact;
    const said = breakdown === "" ? files : `${files} (${breakdown})`;
    const text = `${said}  ${additions} ${deletions}${estimated ? " (estimated)" : ""}`;
    const lines =
      totals.additions === null && totals.deletions === null
        ? "line counts unknown"
        : `${added} ${totals.additions === 1 ? "line" : "lines"} added, ${deleted} deleted`;
    const named = breakdown === "" ? files : `${files}: ${breakdown}`;
    const label = `${named}; ${lines}${estimated ? ", estimated" : ""}`;
    return { files, breakdown, additions, deletions, estimated, text, label };
  }

  /**
   * A row's `+A −D`, written with *formatCount*: null when the row knows neither count, as
   * a binary file does, and "?" for the one it does not know.
   *
   * @param {{additions: number | null, deletions: number | null}} row
   * @param {(count: number) => string} formatCount
   * @returns {{additions: string, deletions: string} | null}
   */
  function changeStats(row, formatCount) {
    if (row.additions === null && row.deletions === null) {
      return null;
    }
    return {
      additions: `+${row.additions === null ? "?" : formatCount(row.additions)}`,
      deletions: `${MINUS}${row.deletions === null ? "?" : formatCount(row.deletions)}`,
    };
  }

  /** @type {MetabrowserChangedFilesTree} */
  const api = Object.freeze({
    STATUS_BADGES,
    STATUS_LABELS,
    STATUS_WORDS,
    buildFileTree,
    changeStats,
    describeChanges,
    expansionFor,
    isOpen,
    parentIndex,
    revealPath,
    statusBreakdown,
    toggleFolder,
    visibleRows,
    windowRange,
  });
  /** @type {{MetabrowserChangedFilesTree?: MetabrowserChangedFilesTree}} */ (
    /** @type {unknown} */ (typeof window === "undefined" ? globalThis : window)
  ).MetabrowserChangedFilesTree = api;
})();
