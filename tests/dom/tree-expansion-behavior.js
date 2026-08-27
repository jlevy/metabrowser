const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const sandbox = {};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/tree-expansion.js"),
  "utf-8",
);
vm.runInContext(source, sandbox, { filename: "tree-expansion.js" });

const expansion = sandbox.MetabrowserTreeExpansion;
const failures = [];

function assertEqual(label, actual, expected) {
  if (actual !== expected) {
    failures.push(`${label}: expected ${JSON.stringify(expected)} got ${JSON.stringify(actual)}`);
  }
}

function assertSet(label, actual, expected) {
  assertEqual(label, JSON.stringify(Array.from(actual).sort()), JSON.stringify(expected.sort()));
}

function fakeClassList(initial) {
  const classes = new Set(initial);
  return {
    contains: (name) => classes.has(name),
    toggle: (name, force) => {
      const want = force === undefined ? !classes.has(name) : force;
      if (want) {
        classes.add(name);
      } else {
        classes.delete(name);
      }
    },
  };
}

function folderElements(expanded) {
  return {
    // Disclosure is class-driven (the shared motion primitive), so the
    // fixture models the collapsed class, not inline display.
    children: {
      classList: fakeClassList(expanded ? [] : ["tree-children-collapsed"]),
    },
    row: {
      classList: fakeClassList(["tree-folder", expanded ? "expanded" : "collapsed"]),
    },
  };
}

function file(name, parent = "") {
  return {
    name,
    path: parent ? `${parent}/${name}` : name,
    type: "file",
  };
}

function directory(name, children, options = {}, parent = "") {
  const nodePath = parent ? `${parent}/${name}` : name;
  return {
    name,
    path: nodePath,
    type: "dir",
    children,
    ...options,
  };
}

function files(count, parent) {
  return Array.from({ length: count }, (_, index) => file(`file-${index}.txt`, parent));
}

const rootNodes = [
  directory("tests", files(50, "tests")),
  directory("docs", files(2, "docs")),
  directory("images", files(1, "images")),
  file("README.md"),
];

assertSet(
  "small folders expand before a large folder",
  expansion.chooseDefaultExpandedPaths(rootNodes, 7, 200),
  ["docs", "images"],
);
assertSet(
  "tight budget expands only the cheapest folder",
  expansion.chooseDefaultExpandedPaths(rootNodes, 5, 200),
  ["images"],
);

const mutedNodes = [
  directory("ignored", files(1, "ignored"), { gitignored: true }),
  directory("empty", [], { empty: true }),
  directory("visible", files(1, "visible")),
];
assertSet(
  "muted folders do not consume the budget",
  expansion.chooseDefaultExpandedPaths(mutedNodes, 4, 200),
  ["visible"],
);

const explicitNodes = [
  directory("already-open", files(3, "already-open"), { expanded: true }),
  directory("tiny", files(1, "tiny")),
];
assertSet(
  "explicit expansion consumes visible rows before defaults",
  expansion.chooseDefaultExpandedPaths(explicitNodes, 5, 200),
  [],
);

const logs = directory(".logs", files(1, "project/.logs"), {}, "project");
const nestedNodes = [
  directory("project", [logs, directory("other", files(1, "other"), {}, "project")]),
];
assertSet(
  "special nested folders expand only after their parent fits",
  expansion.chooseDefaultExpandedPaths(nestedNodes, 4, 200),
  ["project", "project/.logs"],
);

assertEqual(
  "viewport height determines the row budget",
  expansion.visibleRowBudget(600, 24, 18),
  25,
);
assertEqual("invalid measurements use the fallback", expansion.visibleRowBudget(0, 0, 18), 18);

const closedFolder = folderElements(false);
assertEqual(
  "activating a closed folder reports expanded",
  expansion.toggleFolderExpanded(closedFolder.row, closedFolder.children),
  true,
);
assertEqual(
  "expanding reveals children",
  closedFolder.children.classList.contains("tree-children-collapsed"),
  false,
);
assertEqual("expanding sets the row class", closedFolder.row.classList.contains("expanded"), true);
assertEqual(
  "expanding clears the opposite row class",
  closedFolder.row.classList.contains("collapsed"),
  false,
);

assertEqual(
  "activating the open folder reports collapsed",
  expansion.toggleFolderExpanded(closedFolder.row, closedFolder.children),
  false,
);
assertEqual(
  "collapsing hides children",
  closedFolder.children.classList.contains("tree-children-collapsed"),
  true,
);
assertEqual(
  "collapsing clears the row class",
  closedFolder.row.classList.contains("expanded"),
  false,
);
assertEqual(
  "collapsing sets the opposite row class",
  closedFolder.row.classList.contains("collapsed"),
  true,
);

if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}

process.stdout.write("OK tree expansion\n");
