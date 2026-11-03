// Browserless session: a pull request's changed files as a tree, through the production code.
//
// Every answer here is one the route gave while a fake gh replayed full-size pages of changed
// files, recorded in tests/fixtures/github-pull-files-responses.json by
// tests/test_github_pull_files_tree_session.py, which fails when the recording drifts. A list
// filling was read between its pages, as a tree polling while it fills reads it.
//
// builtin_plugins/github/pull-files-tree.js loads whole, and pulls-panel.js for the words a
// failed refresh is given. Each story prints what the tree would show: the window it asks for
// next, the count, the state, and its visible rows, a folder as "v" open or ">" closed with the
// files under it, a file as its change badge, its name, and its line counts. A long run of
// files in one folder is shown by its ends.

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/github-pull-files-responses.json"), "utf8"),
);
// The recording holds each row as one line of JSON.
for (const envelope of Object.values(recorded)) {
  envelope.rows = envelope.rows.map((row) => JSON.parse(row));
}
const treePath = path.join(repoRoot, "src/metabrowser/builtin_plugins/github/pull-files-tree.js");
const panelPath = path.join(repoRoot, "src/metabrowser/builtin_plugins/github/pulls-panel.js");
// Open every folder up to this many files. The panel's measured threshold is the next step's;
// here one list is under the first and over the second.
const LARGE = 300;
const AUTO_EXPAND_FILES = 150;

/** A path with every character outside printable ASCII spelled as its code point. */
function escaped(text) {
  return [...text]
    .map((ch) =>
      /^[\x20-\x7e]$/.test(ch)
        ? ch
        : `<U+${ch.codePointAt(0).toString(16).toUpperCase().padStart(4, "0")}>`,
    )
    .join("");
}

function line(row) {
  const indent = "  ".repeat(row.depth);
  if (row.kind === "folder") {
    return `${indent}${row.expanded ? "v" : ">"} ${row.name}/ (${row.files})`;
  }
  const from = row.previousName === null ? "" : ` (from ${row.previousName})`;
  const counts = `+${row.additions ?? "?"} -${row.deletions ?? "?"}`;
  return `${indent}${row.badge} ${row.name}${from} ${counts}${row.current ? "  <- current" : ""}`;
}

/** Visible rows as lines, a run of more than six files at one depth shown by its ends. */
function show(rows) {
  const lines = [];
  let index = 0;
  while (index < rows.length) {
    let end = index;
    while (
      end < rows.length &&
      rows[end].kind === "file" &&
      rows[end].depth === rows[index].depth &&
      !rows[end].current
    ) {
      end += 1;
    }
    if (end - index > 6) {
      lines.push(...rows.slice(index, index + 3).map(line));
      lines.push(`${"  ".repeat(rows[index].depth)}… ${end - index - 5} more`);
      lines.push(...rows.slice(end - 2, end).map(line));
      index = end;
    } else {
      lines.push(line(rows[index]));
      index += 1;
    }
  }
  return lines;
}

async function main() {
  const tree = await import(pathToFileURL(treePath).href);
  const panel = await import(pathToFileURL(panelPath).href);
  const formatTime = (iso) => iso;
  const describe = (envelope) => {
    const model = tree.describeFileList(envelope);
    const failure = panel.refreshFailure(envelope, formatTime);
    return { ...model, failure: model.failure?.outcome ?? null, says: failure?.text ?? null };
  };
  const stories = {};

  // A first list fills page by page; the tree asks only for the rows it does not hold.
  const holder = tree.holdFileList(106);
  let expansion = null;
  const fill = [];
  for (const name of ["absent", "filling 0", "filling 1", "filling 2", "filled"]) {
    const asked = holder.query();
    const envelope = recorded[name];
    const changed = holder.accept(envelope);
    const built = tree.buildFileTree(holder.rows());
    // How folders start is decided once, when the first rows arrive, by the list's own count.
    if (expansion === null && built.files > 0) {
      expansion = tree.initialExpansion(envelope, LARGE);
    }
    const rows = tree.visibleRows(built, expansion ?? tree.initialExpansion(envelope, LARGE));
    fill.push({
      answer: name,
      asked,
      window: `offset ${envelope.offset}, ${envelope.rows.length} rows`,
      changed,
      ...describe(envelope),
      rows: show(rows),
    });
  }
  stories["a list fills page by page"] = fill;
  const whole = tree.buildFileTree(holder.rows());

  // The chain a reader closes stays closed for every folder in it.
  const chain = tree.visibleRows(whole, expansion).find((row) => row.name === "src/metabrowser");
  const closed = tree.toggleFolder(expansion, chain);
  const reopened = tree.toggleFolder(closed, { ...chain, expanded: false });
  stories["a chain row toggles as one"] = {
    closed: show(tree.visibleRows(whole, closed)),
    reopened: show(tree.visibleRows(whole, reopened)).slice(0, 8),
  };

  // Past the threshold, only the top level shows, from the first page on, since GitHub's Link
  // said three pages; the page's file is revealed and current.
  const top = tree.initialExpansion(recorded["filling 1"], AUTO_EXPAND_FILES);
  const shown = "weird/bell\u0007name.txt";
  stories["past the threshold only the top level shows"] = show(tree.visibleRows(whole, top));
  stories["the file a page shows is revealed and current"] = show(
    tree.visibleRows(whole, tree.revealPath(top, shown), { current: shown }),
  );
  stories["a name is the server's display, and its path the identity"] = tree
    .visibleRows(whole, tree.revealPath(top, shown))
    .filter((row) => row.kind === "file" && row.path.startsWith("weird/"))
    .map((row) => ({
      path: escaped(row.path),
      name: row.name,
      badge: row.badge,
      label: row.statusLabel,
    }));

  // Other lists, and each way a refresh can end.
  const local = recorded.comparison;
  stories["a list from the local comparison"] = {
    ...describe(local),
    rows: show(tree.visibleRows(tree.buildFileTree(local.rows), tree.initialExpansion(local, 150))),
  };
  stories["GitHub stops at 3,000 files"] = describe(recorded.capped);
  stories["a list asked for and not yet arrived"] = describe(recorded.pending);
  stories["a list that stopped part-way"] = describe(recorded.stopped);
  stories["a list the pull request has changed since"] = describe(recorded.stale);
  stories["a server with no GitHub repository"] = describe(recorded.not_github);
  stories["each way a refresh can fail"] = Object.fromEntries(
    Object.keys(recorded)
      .filter((name) => name.startsWith("failed "))
      .map((name) => [name.slice("failed ".length), describe(recorded[name])]),
  );

  // An answer for another read is not joined to what is held.
  const other = { ...recorded["filling 2"], fetched_at: "2026-09-17T12:30:00Z" };
  const restarted = tree.holdFileList(106);
  restarted.accept(recorded["filling 1"]);
  const joined = restarted.accept(other);
  stories["an answer for another read starts again at 0"] = {
    joined,
    asked: restarted.query(),
    held: restarted.rows().length,
  };

  // Relations a reviewer can break the model against.
  const listRows = [
    ...recorded["filling 1"].rows,
    ...recorded["filling 2"].rows,
    ...recorded.filled.rows,
  ];
  const nodes = new Map();
  const walk = (folder) => {
    nodes.set(folder.id, folder);
    for (const child of folder.children) {
      if (child.kind === "folder") {
        walk(child);
      }
    }
  };
  walk(whole.root);
  const everything = tree.visibleRows(whole, { all: true, toggled: new Map() });
  const displayOf = new Map(listRows.map((row) => [row.path, row.display.split("/").at(-1)]));
  const invariants = {
    "filled rows are the list's rows":
      JSON.stringify(holder.rows().map((row) => row.path)) ===
        JSON.stringify(listRows.map((row) => row.path)) &&
      holder.rows().length === recorded.filled.fetched,
    "no single-child folder is its own row": everything
      .filter((row) => row.kind === "folder")
      .every((row) => {
        const node = nodes.get(row.id);
        return !(node.children.length === 1 && node.children[0].kind === "folder");
      }),
    "each folder counts the files under it": whole.folderIds.every(
      (id) => nodes.get(id).files === listRows.filter((row) => row.path.startsWith(id)).length,
    ),
    "every name is the server's display": everything
      .filter((row) => row.kind === "file")
      .every((row) => row.name === displayOf.get(row.path)),
    "a list for another read starts again at 0":
      !joined && restarted.query() === "number=106&offset=0",
  };
  for (const [name, holds] of Object.entries(invariants)) {
    if (holds !== true) {
      throw new Error(`invariant broken: ${name}`);
    }
  }
  process.stdout.write(`${JSON.stringify({ stories, invariants }, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
