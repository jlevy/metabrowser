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
  const formatTime = (iso) => iso;
  const describe = (envelope) => {
    const model = tree.describeFileList(envelope);
    const failure = tree.fileListFailure(envelope, formatTime);
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
  const replacement = tree.holdFileList(106);
  replacement.accept(recorded["same second before"]);
  const atOldEnd = replacement.query();
  if (replacement.accept(recorded["same second continuation"])) {
    throw Error("a replacement continuation must not append");
  }
  const restart = replacement.query();
  if (restart !== "number=106&offset=0" || replacement.rows()[0].path !== "before.js") {
    throw Error("a same-second replacement must restart at zero while retaining the old rows");
  }
  replacement.accept(recorded["same second after"]);
  if (replacement.rows()[0].path !== "after.js" || replacement.rows().length !== 1) {
    throw Error("the replacement's first window must replace the old rows");
  }
  for (const owner of [{ source: "https://github.com/other/repo" }, { reader: "gh:other" }]) {
    const owned = tree.holdFileList(106);
    owned.accept(recorded["filling 1"]);
    if (
      owned.accept({ ...recorded["filling 2"], ...owner }) ||
      owned.query() !== "number=106&offset=0"
    ) {
      throw Error("different source or reader rows must not join the held list");
    }
  }
  stories["same-second equally sized refreshes replace the held list"] = {
    atOldEnd,
    restart,
    rows: replacement.rows().map((row) => row.path),
  };
  const sameRead = tree.holdFileList(106);
  sameRead.accept(recorded["filling 1"]);
  if (
    !sameRead.accept({ ...recorded["filling 2"], fetched_at: "2026-09-17T12:30:00Z" }) ||
    sameRead.rows().length !== 200
  ) {
    throw Error("timestamps must not split the same progressive generation");
  }
  const rowExpansion = tree.createRowExpansion();
  const expandedRows = [rowExpansion.shown(7, "a.py"), rowExpansion.shown(8, "b.py")];
  rowExpansion.expand(8);
  expandedRows.push(rowExpansion.shown(9, "c.py"));
  if (!rowExpansion.isExpanded(8)) {
    throw Error("a reader's expansion must survive page replacement");
  }
  stories["only file-address expansions close when the page moves"] = expandedRows;
  const routes = tree.createRowExpansion();
  routes.shown(7, "a.py");
  routes.shown(7, null);
  if (!routes.isExpanded(7)) {
    throw Error("returning to the same PR preview preserves disclosure");
  }
  routes.collapse(7);
  routes.shown(7, "a.py");
  routes.collapse(7);
  if (routes.shown(7, "a.py").expand.length !== 0) {
    throw Error("a repeated file notification must respect manual collapse");
  }
  if (routes.shown(7, "b.py").expand[0] !== 7) {
    throw Error("a different file address must reveal its collapsed owner");
  }
  routes.expand(7);
  if (routes.shown(8, "c.py").collapse.length !== 0 || !routes.isExpanded(7)) {
    throw Error("reader-owned expansion survives navigation to another PR");
  }

  stories["a long tree draws only its viewport and overscan"] = [0, 12000, 200000].map((top) =>
    tree.windowRange({
      count: 4539,
      rowHeight: 24,
      viewTop: top,
      viewBottom: top + 700,
      listTop: 0,
      overscan: 40,
    }),
  );
  const whole = tree.buildFileTree(holder.rows());

  // The chain a reader closes stays closed for every folder in it.
  const chain = tree.visibleRows(whole, expansion).find((row) => row.name === "src/app");
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
  const localHolder = tree.holdFileList(local.number);
  localHolder.accept(local);
  const changedBase = {
    ...local,
    base: local.base === "b".repeat(40) ? "c".repeat(40) : "b".repeat(40),
    offset: local.rows.length,
    rows: [],
  };
  if (localHolder.accept(changedBase)) {
    throw Error("rows from a different local base must not append");
  }
  if (!localHolder.query().endsWith("offset=0")) {
    throw Error("a changed local base must restart the window");
  }
  stories["an unchanged head with a different local base starts again at zero"] =
    localHolder.query();
  stories["a list from the local comparison"] = {
    ...describe(local),
    rows: show(tree.visibleRows(tree.buildFileTree(local.rows), tree.initialExpansion(local, 150))),
  };
  stories["GitHub stops at 3,000 files"] = describe(recorded.capped);
  stories["a list asked for and not yet arrived"] = describe(recorded.pending);
  stories["a list that stopped part-way"] = describe(recorded.stopped);
  stories["a list the pull request has changed since"] = describe(recorded.stale);
  // Rows already listed are never covered by progress, and a stale list says nothing of being
  // stale: its refresh, asked for or running, is `refreshing`, which the paint breathes on the
  // names, with no line; the spinner (`loading`) is only for a list with no rows yet.
  const shownRows = tree.visibleRows(whole, tree.initialExpansion(recorded.filled, LARGE));
  const quietStale = { ...recorded.stale, last_refresh: null };
  const shows = (envelope, rows, asking) => {
    const model = tree.describeFileTree(envelope, {
      number: 106,
      expanded: true,
      rows,
      rowsVersion: 1,
      asking,
      error: null,
      formatTime,
    });
    return {
      line: model.line,
      loading: model.loading,
      refreshing: model.refreshing,
      notice: model.notice?.text ?? null,
    };
  };
  stories["a stale list's rows are never covered by progress"] = {
    "its refresh about to be asked for": shows(quietStale, shownRows, false),
    "its refresh asked for": shows(quietStale, shownRows, true),
    "its refresh running": shows({ ...quietStale, refreshing: true }, shownRows, false),
    "no rows yet, while listing": shows(recorded.pending, [], true),
  };
  stories["a server with no GitHub repository"] = describe(recorded.not_github);
  stories["each way a refresh can fail"] = Object.fromEntries(
    Object.keys(recorded)
      .filter((name) => name.startsWith("failed "))
      .map((name) => [name.slice("failed ".length), describe(recorded[name])]),
  );

  // An answer for another read is not joined to what is held.
  const other = { ...recorded["filling 2"], generation: "f".repeat(32) };
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
  process.stdout.write(
    `${JSON.stringify({ stories, controller: await controllerStory(tree), invariants }, null, 2)}\n`,
  );
}

/** The production controller's network, timers, keys, and address changes without a DOM. */
async function controllerStory(tree) {
  const timers = new Map();
  const reads = [];
  const requests = [];
  const jumps = [];
  // Each jump says whether a walk will settle there, and a cancelled walk says so.
  const settling = [];
  let cancelled = 0;
  // Paths the route cannot encode, as `tab.fileHref` answers null for them.
  const unroutable = new Set();
  const opens = [];
  let model = null;
  let nextTimer = 0;
  let visible = true;
  const controller = tree.createFileTreeController(
    {
      request: async (method, route, options) => {
        requests.push(
          `${method} ${route}${options.body ? ` ${JSON.stringify(options.body)}` : ""}`,
        );
        if (method === "POST") {
          return { status: 202, etag: null, body: { files: recorded["filling 0"] } };
        }
        const answer = reads.shift();
        if (answer === "failure") {
          throw Error("connection failed");
        }
        if (answer === undefined) {
          throw Error("no read scripted");
        }
        return { status: 200, etag: null, body: recorded[answer] };
      },
      schedule: (callback, delay) => {
        const key = ++nextTimer;
        timers.set(key, { callback, delay });
        return key;
      },
      cancel: (key) => timers.delete(key),
      now: () => Date.parse("2026-09-17T12:00:30Z"),
      isVisible: () => visible,
      formatTime: (iso) => iso,
      render: (next) => {
        model = next;
      },
      markAnchor() {},
      markCurrent() {},
      markMuted() {},
      page: () => ({
        fileForPath: () => ({ kind: "file" }),
        showFile: (path, how) => {
          jumps.push(path);
          settling.push(how?.settling === true);
          return { kind: "jumped" };
        },
        walkCancelled: () => {
          cancelled += 1;
        },
      }),
      open: (route) => opens.push(route),
      routable: (path) => !unroutable.has(path),
      leave() {},
    },
    { number: 106, autoExpandFiles: 300 },
  );
  const settle = async () => {
    for (let at = 0; at < 10; at += 1) {
      await new Promise((resolve) => setImmediate(resolve));
    }
  };
  const fire = async (delay) => {
    const entry = [...timers].find(([, timer]) => timer.delay === delay);
    if (entry === undefined) {
      throw Error(`no timer at ${delay}`);
    }
    timers.delete(entry[0]);
    entry[1].callback();
    await settle();
  };
  const story = [];
  const look = (step) =>
    story.push({
      step,
      requests: requests.splice(0),
      held: controller.snapshot().held,
      current: controller.current(),
      notice: model.notice?.text ?? null,
      timers: [...timers.values()].map((timer) => timer.delay),
    });
  reads.push("failure");
  controller.expand();
  await settle();
  if (model.notice?.action !== "retry") {
    throw Error("a failed read needs Retry");
  }
  look("a failed first read offers Retry and keeps reading");
  reads.push("absent");
  await controller.retry();
  if (requests.filter((line) => line.startsWith("POST")).length !== 1) {
    throw Error("an expanded tree with a missing cache must ask exactly once");
  }
  if (!model.loading || model.notice !== null) {
    throw Error("an expanded tree lists automatically while showing progress");
  }
  look("Retry reads the cache and automatically lists missing files");
  for (const name of ["filling 1", "filling 2", "filled"]) {
    reads.push(name);
    await fire(tree.FILES_POLL_MS);
    look(name);
  }
  const file = model.rows.find((row) => row.kind === "file");
  controller.focused(file.id);
  const beforeWalk = requests.length;
  for (let at = 0; at < 8; at += 1) {
    controller.move(1, { repeat: true });
  }
  if (requests.length !== beforeWalk || opens.length !== 0) {
    throw Error("a held key moved the address or read");
  }
  controller.released();
  if (opens.length !== 1 || !opens[0].replace || !opens[0].jumped) {
    throw Error("a key's stop must replace one entry");
  }
  if (settling.length === 0 || settling.some((will) => !will) || cancelled !== 0) {
    throw Error("a walk's jumps will settle, and its stop cancels nothing");
  }
  story.push({
    step: "held keys jump every file but replace history once on release",
    jumps: jumps.length,
    opens: opens.splice(0),
  });
  controller.activateAnchor();
  if (opens.length !== 1 || opens[0].replace) {
    throw Error("Enter must push the file's address");
  }
  story.push({ step: "Enter pushes the focused file", opens: opens.splice(0) });
  const shown = "weird/bell\u0007name.txt";
  controller.followCurrent(shown);
  if (controller.current() !== shown || !model.rows.some((row) => row.id === shown)) {
    throw Error("a scrolled file must be revealed");
  }
  look("a file reported by the page is revealed without moving its address");
  const pairAt = model.rows.findIndex(
    (row, at) => row.kind === "file" && model.rows[at + 1]?.kind === "file",
  );
  const startWalk = () => {
    controller.focused(model.rows[pairAt].id);
    controller.move(1, { repeat: true });
    if (controller.snapshot().walking === null) {
      throw Error("the probe needs a pending file walk");
    }
  };
  startWalk();
  const target = controller.snapshot().walking;
  controller.followCurrent(target);
  controller.released();
  if (opens.length !== 1 || opens[0].file !== target) {
    throw Error("scroll feedback cancelled the active walk");
  }
  story.push({
    step: "the walk's own scroll report does not cancel its final address",
    opens: opens.splice(0),
  });
  startWalk();
  controller.setCurrent(shown);
  controller.released();
  if (controller.snapshot().walking !== null || opens.length !== 0) {
    throw Error("a later route must cancel the old walk");
  }
  if (cancelled !== 1) {
    throw Error("a cancelled walk must tell the page it will not settle");
  }
  look("a later route cancels a pending file walk");
  startWalk();
  controller.setShown(false);
  controller.released();
  if (controller.snapshot().walking !== null || opens.length !== 0) {
    throw Error("a hidden panel must cancel the old walk");
  }
  if (cancelled !== 2) {
    throw Error("hiding the panel must tell the page the walk will not settle");
  }
  startWalk();
  controller.activateAnchor();
  if (cancelled !== 2 || opens.length !== 1) {
    throw Error("Enter during a walk opens the file, which the page then owns");
  }
  opens.length = 0;
  look("hiding the panel cancels a pending file walk");
  controller.collapse();
  if (timers.size !== 0) {
    throw Error("a collapsed tree must stop polling");
  }
  visible = false;
  controller.onVisibilityChange();
  look("a closed or hidden tree has no timer");
  // A walk's other endings tell the page too: the page hidden, the tree collapsed, and the
  // tree disposed. A walk onto a file the route cannot encode claims no settling at all,
  // since no address will confirm it.
  const walkOn = () => {
    const at = model.rows.findIndex(
      (row, index) => row.kind === "file" && model.rows[index + 1]?.kind === "file",
    );
    controller.focused(model.rows[at].id);
    controller.move(1, { repeat: true });
    if (controller.snapshot().walking === null) {
      throw Error("the probe needs a pending file walk");
    }
    return model.rows[at + 1].path;
  };
  visible = true;
  controller.setShown(true);
  reads.push("filled");
  controller.expand();
  await settle();
  walkOn();
  visible = false;
  controller.onVisibilityChange();
  if (cancelled !== 3) {
    throw Error("a hidden page must tell the page the walk will not settle");
  }
  visible = true;
  reads.push("filled");
  controller.onVisibilityChange();
  await settle();
  walkOn();
  controller.collapse();
  if (cancelled !== 4) {
    throw Error("collapsing the tree must tell the page the walk will not settle");
  }
  reads.push("filled");
  controller.expand();
  await settle();
  const at = model.rows.findIndex(
    (row, index) => row.kind === "file" && model.rows[index + 1]?.kind === "file",
  );
  unroutable.add(model.rows[at + 1].path);
  settling.length = 0;
  walkOn();
  if (settling.at(-1) !== false) {
    throw Error("a walk onto a file the route cannot encode must claim no settling");
  }
  unroutable.clear();
  walkOn();
  controller.dispose();
  if (cancelled !== 5) {
    throw Error("disposing the tree must tell the page the walk will not settle");
  }
  return story;
}

main().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
