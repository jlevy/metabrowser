// Browserless session: a multi-file diff's Diff summary, through the production code.
//
// The summary's words, its rows, and its tree are three production modules, loaded as they
// ship: the shell's changed-files tree (static/changed-files-tree.js), which the Pulls tab's
// tree of a pull request's files is drawn on too, for the header's words, the roll-ups, and
// the rows a reader sees; builtin_plugins/diff/diff-model.js for what each change of a File
// Diff Format manifest is as a row (`changeSummaryRow`); and
// builtin_plugins/diff/diff-summary.js for the tree's decisions without a DOM
// (`createSummaryTree`): which folders are open, the row that takes Tab, and what a key or
// a press does.
//
// Each story prints what a reader would see: a header as its words, and the visible rows, a
// folder as "v" open or ">" closed with its files and its line counts rolled up, a file as
// its change letter, its name, and its line counts; a key's step names the key, what it did,
// the row that takes Tab after it, and a jump's path. The manifests are built here, each file
// as a comparison's manifest lists it, since what is under test is what the summary makes of
// any manifest: the header the reader asked for, "35 changed files (2 added, 3 removed, 30
// modified)  +1,234 −3,423", one of every change kind a comparison can hold, binary files that
// carry no counts, a change set whose totals are not exact, and a change set of no files.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const shared = require("./changed-files-tree-fixture.js").changedFilesTree();
// The shell's number format is the browser's own grouping; a session fixes the locale.
const english = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const formatCount = (count) => english.format(count);

/** How many changes have been made, for each one's id. */
let changes = 0;

/** A side of a change, as a manifest has it. */
const side = (file) => ({ path: file, mode: "100644", entry_type: "file", oid: null });

/**
 * One change of a manifest.
 *
 * @param {string} kind
 * @param {string} file The path it has now, or had, for a deletion.
 * @param {number | null} additions
 * @param {number | null} deletions
 * @param {string} [from] The path a rename or a copy came from.
 */
function change(kind, file, additions, deletions, from) {
  const binary = additions === null && deletions === null && kind !== "unmerged";
  changes += 1;
  return {
    id: `f${changes}`,
    kind,
    old: kind === "added" ? null : side(from ?? file),
    new: kind === "deleted" ? null : side(file),
    similarity: kind === "renamed" || kind === "copied" ? 90 : null,
    binary,
    availability: binary ? "binary" : kind === "unmerged" ? "unsupported" : "ready",
    additions,
    deletions,
  };
}

/** A visible row as one line. */
function line(row) {
  const indent = "  ".repeat(row.depth);
  const counts =
    row.additions === null && row.deletions === null
      ? ""
      : ` +${row.additions ?? "?"} -${row.deletions ?? "?"}`;
  if (row.kind === "folder") {
    const unknown = row.unknown > 0 ? `, ${row.unknown} without counts` : "";
    return `${indent}${row.expanded ? "v" : ">"} ${row.name}/ (${row.files}${unknown})${counts}`;
  }
  const from = row.previousName === null ? "" : ` (from ${row.previousName})`;
  return `${indent}${row.badge} ${row.name}${from}${counts}`;
}

/** The header of a manifest, as `renderDiffSummary` in diff-view.js asks for it. */
function header(model, manifest) {
  const rows = manifest.files.map(model.changeSummaryRow);
  const totals = manifest.totals;
  const said = shared.describeChanges(
    {
      files: totals.files,
      additions: totals.additions,
      deletions: totals.deletions,
      exact: totals.exact,
    },
    rows.map((row) => row.status),
    formatCount,
  );
  return { text: said.text, label: said.label, estimated: said.estimated };
}

/** A manifest of *files*, with totals summed as the comparison sums them. */
function manifestOf(files, exact = true) {
  const sum = (key) => files.reduce((total, file) => total + (file[key] ?? 0), 0);
  return {
    files,
    totals: {
      files: files.length,
      additions: exact ? sum("additions") : null,
      deletions: exact ? sum("deletions") : null,
      exact,
    },
    truncated: false,
  };
}

async function main() {
  const model = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-model.js")).href
  );
  const summary = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-summary.js")).href
  );
  const stories = {};

  // The reader's own example: 35 files, 2 added, 3 removed, and 30 modified.
  const example = [
    change("added", "docs/diff-summary.md", 120, 0),
    change("added", "src/viewer/shell/changed-files-tree.js", 400, 0),
    change("deleted", "src/viewer/legacy/summary-line.js", 0, 900),
    change("deleted", "src/viewer/legacy/summary-line.css", 0, 1400),
    change("deleted", "tests/legacy-summary.js", 0, 300),
    ...Array.from({ length: 30 }, (_, at) =>
      change(
        "modified",
        `src/viewer/plugins/diff/part-${String(at).padStart(2, "0")}.js`,
        at < 29 ? 24 : 18,
        at < 29 ? 28 : 11,
      ),
    ),
  ];
  const exampleManifest = manifestOf(example);
  stories["the reader's example"] = header(model, exampleManifest);

  // One of every kind a comparison holds, two binary files with no counts, and a deep chain.
  const kinds = [
    change("modified", "README.md", 3, 1),
    change("added", "src/app/new.py", 40, 0),
    change("deleted", "src/app/old.py", 0, 22),
    change("renamed", "src/app/views/main.py", 5, 2, "src/app/main.py"),
    change("copied", "src/app/views/copy.py", 1, 0, "src/app/views/main.py"),
    change("type_changed", "tools/run", 0, 0),
    change("unmerged", "src/app/conflict.py", null, null),
    change("added", "assets/logo.png", null, null),
    change("modified", "assets/icon.png", null, null),
    change("modified", "src/viewer/plugins/diff/diff-view.js", 220, 35),
    change("added", "src/viewer/plugins/diff/diff-summary.js", 400, 0),
  ];
  const kindsManifest = manifestOf(kinds);
  stories["every kind, in the header's order"] = header(model, kindsManifest);
  stories["each change as a row"] = kinds.map((entry) => {
    const row = model.changeSummaryRow(entry);
    return `${entry.kind} -> ${row.status} ${row.path}${row.previous_path === null ? "" : ` (from ${row.previous_path})`}`;
  });
  stories["a change set whose totals are not exact"] = header(model, manifestOf(kinds, false));
  stories["one status, one file of it"] = header(
    model,
    manifestOf([change("modified", "a.txt", 1, 1), change("modified", "b/c.txt", 1, 0)]),
  );
  stories["no files"] = header(model, manifestOf([]));

  // The tree as it opens: every folder open, a chain of single folders as one row, and each
  // folder with the counts of its files rolled up, the binary ones left out and counted.
  const kindRows = kinds.map(model.changeSummaryRow);
  const tree = summary.createSummaryTree(shared, kindRows);
  stories["the tree as it opens"] = tree.rows().map(line);

  // Past the threshold only the top level shows, with the same roll-ups.
  const compact = summary.createSummaryTree(shared, kindRows, { autoExpandFiles: 5 });
  stories["past the threshold only the top level shows"] = compact.rows().map(line);

  // The keys, from the row that takes Tab, which is the first.
  const walk = summary.createSummaryTree(shared, kindRows);
  const steps = [];
  const press = (name, action) => {
    const anchor = walk.anchor();
    const at = walk.indexOf(anchor);
    steps.push({
      key: name,
      did: action === null ? "not the tree's" : action.kind,
      ...(action?.kind === "jump" ? { path: action.path } : {}),
      anchor: at === undefined ? null : line(walk.rows()[at]).trim(),
    });
  };
  for (const key of [
    "ArrowDown",
    "ArrowRight",
    "ArrowDown",
    "ArrowDown",
    "Enter",
    "ArrowRight",
    "ArrowRight",
    "ArrowLeft",
    "ArrowLeft",
    "ArrowLeft",
    "End",
    " ",
    "Home",
    "ArrowUp",
    "ArrowRight",
    "Escape",
  ]) {
    press(key, walk.key(key));
  }
  stories["the keys move along the rows, and only Enter, Space, or a press jumps"] = steps;
  stories["after the walk"] = walk.rows().map(line);

  // A press on a folder toggles it, and the row that took Tab inside it goes to the folder.
  const pressed = summary.createSummaryTree(shared, kindRows);
  pressed.focused("src/viewer/plugins/diff/diff-view.js");
  const chain = pressed.rows().find((row) => row.name === "viewer/plugins/diff");
  const closed = pressed.press(chain.id);
  stories["closing a folder keeps the row that takes Tab, on the folder"] = {
    did: closed.kind,
    anchor: pressed.anchor(),
    rows: pressed.rows().map(line),
    file: pressed.press("README.md"),
  };

  // Relations a reviewer can break the model against.
  const exampleRows = example.map(model.changeSummaryRow);
  const built = shared.buildFileTree(kindRows);
  const nodes = [];
  const collect = (folder) => {
    for (const child of folder.children) {
      if (child.kind === "folder") {
        nodes.push(child);
        collect(child);
      }
    }
  };
  collect(built.root);
  const known = (rows, key) => {
    const counted = rows.filter((row) => row[key] !== null);
    return counted.length === 0 ? null : counted.reduce((sum, row) => sum + row[key], 0);
  };
  const invariants = {
    "the breakdown counts every file once":
      shared
        .statusBreakdown(exampleRows.map((row) => row.status))
        .reduce((sum, entry) => sum + entry.count, 0) === example.length,
    "each folder's lines are the sum of its files' known lines": nodes.every((node) => {
      const under = kindRows.filter((row) => row.path.startsWith(node.id));
      return (
        node.additions === known(under, "additions") &&
        node.deletions === known(under, "deletions") &&
        node.unknown ===
          under.filter((row) => row.additions === null && row.deletions === null).length
      );
    }),
    "the root's lines are the manifest's totals": (() => {
      const root = shared.buildFileTree(exampleRows).root;
      return (
        root.additions === exampleManifest.totals.additions &&
        root.deletions === exampleManifest.totals.deletions
      );
    })(),
    "every file row jumps to a path the diff finds it by": kinds.every((entry) => {
      const row = model.changeSummaryRow(entry);
      return row.path === (entry.new ?? entry.old).path;
    }),
    "a closed tree's rows are the top level": compact.rows().every((row) => row.depth === 0),
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
