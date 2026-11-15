// Browserless session: the Pulls tab grouped by stack, through the production code.
//
// builtin_plugins/github/pulls-panel.js's controller decides the rows the list draws and the
// keys walk, and builtin_plugins/github/pull-stacks.js how they group: each stack with a pull
// request in the list has a "Stack #N" row, open by default, with its pull requests under it
// in the stack menu's order, top of the stack first; pull requests in no stack follow, in the
// list's order; one in two stacks sits once, under the first; and with no stacks known for
// the list's reader the list stays flat and the Group by stack option says why. Its answers
// are the server's: the lists in tests/fixtures/github-pulls-panel-responses.json and the
// stack snapshots in tests/fixtures/github-stacks-responses.json, which
// tests/test_github_pulls_panel_session.py records from the real routes.
//
// The page's stack menu (pull-page.js, `createStackMenu`) is mounted over a stand-in for the
// DOM, and its member links are read back: the groups list a stack's pull requests in the
// order the menu does. Each step prints the option, the rows, the row marks, and what opened;
// `invariants` are relations every grouped step holds.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { FakeElement } = require("./pulls-test-dom.js");

const root = path.resolve(__dirname, "../..");
const GITHUB = path.join(root, "src/metabrowser/builtin_plugins/github");
const lists = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/github-pulls-panel-responses.json"), "utf8"),
);
const stacks = require("../fixtures/github-stacks-responses.json");
// The recording holds each distinct window of rows once; `same_as` names the answer that has it.
const rowsOf = (rows) =>
  Array.isArray(rows)
    ? rows.map((row) => JSON.parse(row))
    : [rows.same_as].flat().flatMap((holder) => rowsOf(lists[holder].body.rows));
const windows = Object.values(lists).filter((answer) => answer.body?.rows !== undefined);
const resolved = windows.map((answer) => rowsOf(answer.body.rows));
for (const [at, answer] of windows.entries()) {
  answer.body.rows = resolved[at];
}

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

(async () => {
  const stackModule = await import(pathToFileURL(path.join(GITHUB, "pull-stacks.js")).href);
  const panel = await import(pathToFileURL(path.join(GITHUB, "pulls-panel.js")).href);
  const page = await import(pathToFileURL(path.join(GITHUB, "pull-page.js")).href);
  const { createStackIndex, stackCaption, stackMenuOrder } = stackModule;
  const index = (name) => createStackIndex(stacks[name].body);

  /** One panel's controller over recorded answers, with every effect it asks for logged. */
  function mount({ filter = "all", list = "current", groupByStack = null } = {}) {
    const log = { opened: [], marks: [], choices: [] };
    let model = null;
    let anchor = null;
    const timers = new Map();
    let nextTimer = 1;
    const controller = panel.createPullsController(
      {
        request(method, route) {
          if (method === "GET" && route.startsWith("/api/plugin/github/pulls?")) {
            const answer = route.includes("&after=") ? lists.more_window : lists[list];
            return Promise.resolve({ status: answer.status, etag: answer.etag, body: answer.body });
          }
          // A refresh is the list's business (github-pulls-panel-session.js), and a row's
          // record the page's: only the list each story reads and what opened count here.
          return Promise.resolve({ status: 404, etag: null, body: null });
        },
        schedule(callback, delayMs) {
          timers.set(nextTimer, { callback, delayMs });
          return nextTimer++;
        },
        cancel: (handle) => timers.delete(handle),
        now: () => Date.parse("2026-09-17T12:00:30Z"),
        isVisible: () => true,
        formatTime: (iso) => iso,
        render(next) {
          model = next;
        },
        markCurrent() {},
        markAnchor(_previous, next, focus) {
          anchor = next;
          if (focus) {
            log.marks.push(next < 0 ? `focus Stack #${-next}` : `focus #${next}`);
          }
        },
        reveal() {},
        open(route) {
          log.opened.push(route.number);
        },
        filterChanged() {},
        groupingChanged(on) {
          log.choices.push(on);
        },
      },
      { filter, current: null, groupByStack },
    );
    /** Run the timers the opening of a row waits on: its record's read already answered. */
    async function runTimers() {
      for (const [handle, timer] of [...timers]) {
        if (timer.delayMs === panel.OPEN_WAIT_MS) {
          timers.delete(handle);
          timer.callback();
        }
      }
      await settle();
    }
    const body = lists[list].body;
    return {
      identity: { source: body.source, reader: body.reader },
      controller,
      log,
      model: () => model,
      anchor: () => anchor,
      runTimers,
      async key(name, how) {
        const handled = {
          J: () => controller.move(1, how),
          K: () => controller.move(-1, how),
          Right: () => controller.enterStack(),
          Left: () => controller.leaveToStack(),
          Enter: () => controller.activateAnchor(),
        }[name]();
        await settle();
        await runTimers();
        return handled;
      },
    };
  }

  /** What a reader sees of the rows: every stack and the rows under it, then the ends. */
  function drawn(model, identity, stackIndex) {
    const caption = (number, under) =>
      stackCaption(stackIndex, identity, number, under)?.text ?? "";
    if (model.stacks.rows === null) {
      const rows = model.rows.map((row) => `#${row.number} ${caption(row.number, null)}`.trim());
      return rows.length > 4 ? [...rows.slice(0, 3), "…", rows.at(-1)] : rows;
    }
    const lines = [];
    const rest = [];
    for (const row of model.stacks.rows) {
      if (row.kind === "stack") {
        lines.push(
          `${row.expanded ? "▾" : "▸"} ${row.label} (${row.count}) [${row.posinset}/${row.setsize}] · ${row.hint}`,
        );
      } else if (row.level === 2) {
        lines.push(
          `    #${row.number} ${caption(row.number, row.stack)} [${row.posinset}/${row.setsize}]`,
        );
      } else {
        rest.push(`#${row.number} [${row.posinset}/${row.setsize}]`);
      }
    }
    return [...lines, ...(rest.length > 3 ? [...rest.slice(0, 2), "…", rest.at(-1)] : rest)];
  }

  /** The relations a grouped list holds against the list it groups. */
  function holds(model, identity, stackIndex) {
    const rows = model.stacks.rows;
    if (rows === null) {
      return true;
    }
    const listed = model.rows.map((row) => row.number);
    const placed = rows.filter((row) => row.kind === "pull").map((row) => row.number);
    const hidden = rows.flatMap((row) =>
      row.kind === "stack" && !row.expanded ? row.members : [],
    );
    // Every listed pull request is drawn once, or held by its closed stack's row.
    assert.deepEqual([...placed, ...hidden].sort(), [...listed].sort());
    for (const row of rows) {
      if (row.kind === "stack") {
        // Members are the stack menu's order, of the pull requests the list has.
        const order = stackMenuOrder(row.stack).filter((number) => row.members.includes(number));
        assert.deepEqual(row.members, order);
        for (const number of row.members) {
          assert.ok(stackModule.stackMembership(stackIndex, identity, number).includes(row.stack));
        }
      }
    }
    // Pull requests in no stack keep the list's order, after every stack.
    const rest = rows.filter((row) => row.kind === "pull" && row.level === 1);
    assert.deepEqual(
      rest.map((row) => row.number),
      listed.filter((number) => rest.some((row) => row.number === number)),
    );
    const firstRest = rows.findIndex((row) => row.kind === "pull" && row.level === 1);
    assert.ok(firstRest < 0 || rows.slice(firstRest).every((row) => row.kind !== "stack"));
    return true;
  }

  const steps = [];
  const record = (step, story, stackIndex, extra = {}) => {
    const model = story.model();
    steps.push({
      step,
      option: {
        available: model.stacks.available,
        on: model.stacks.on,
        tip: model.stacks.tip,
      },
      rows: drawn(model, story.identity, stackIndex),
      ...(story.log.marks.length > 0 ? { marks: story.log.marks.splice(0) } : {}),
      ...(story.log.opened.length > 0 ? { opened: story.log.opened.splice(0) } : {}),
      ...extra,
    });
    holds(model, story.identity, stackIndex);
  };

  // ── The default: grouped as soon as the stacks are known, and flat until then.
  const story = mount();
  await story.controller.start({ shown: true });
  await settle();
  record("the list arrives before any stacks: flat", story, createStackIndex(null));
  for (const name of ["absent", "missing"]) {
    story.controller.setStacks(index(name));
    record(`stacks ${name}: flat, and the option says why`, story, index(name));
  }
  const current = index("current");
  story.controller.setStacks(current);
  record("stacks known: Stack #286 first, open, top of the stack first", story, current, {
    tabStop: story.anchor(),
  });

  // ── Keys: a stack's row is a stop of its own, as a folder's is.
  for (const name of ["J", "J", "J", "J", "K"]) {
    await story.key(name);
  }
  record("J walks into the stack and out past it, K steps back; only pulls open", story, current);
  await story.key("Left");
  record("Left on a pull request in a stack goes to the stack's row", story, current);
  await story.key("Left");
  record("Left on the stack's row closes it", story, current);
  await story.key("J");
  await story.key("K");
  record("J from a closed stack goes past it, and K comes back to it", story, current);
  await story.key("Right");
  record("Right opens it", story, current);
  await story.key("Right");
  record("Right again goes to its first pull request, which opens", story, current);
  await story.key("K");
  await story.key("Enter");
  record("Enter on the stack's row closes it", story, current, {
    closed: story.controller.snapshot().closedStacks,
  });
  story.controller.setCurrent(7);
  record("an address that names #7 opens the stack that holds it", story, current, {
    closed: story.controller.snapshot().closedStacks,
    tabStop: story.anchor(),
  });

  // ── The option, and the choice that persists.
  story.controller.setGroupByStack(false);
  record("Group by stack off: flat, and the choice is kept", story, current, {
    kept: story.log.choices.slice(),
  });
  story.controller.setGroupByStack(true);
  record("on again", story, current, { kept: story.log.choices.splice(0) });
  const kept = mount({ groupByStack: false });
  kept.controller.setStacks(current);
  await kept.controller.start({ shown: true });
  await settle();
  record("a panel mounted with the kept choice off starts flat", kept, current);

  // ── A filter, shared membership, a snapshot kept through a failed refresh, and none.
  const open = mount({ filter: "open", list: "open_current" });
  open.controller.setStacks(current);
  await open.controller.start({ shown: true });
  await settle();
  record("Open: #8 is closed, so Stack #286 holds 2 of its 3", open, current);
  const shared = index("shared");
  story.controller.setStacks(shared);
  record(
    "#8 in two stacks: once, under the first listed, its badge naming the other",
    story,
    shared,
  );
  const closed = mount({ filter: "closed", list: "closed_current" });
  closed.controller.setStacks(shared);
  await closed.controller.start({ shown: true });
  await settle();
  record(
    "Closed: #286's one listed pull request sits under #290, so #286 has no row",
    closed,
    shared,
  );
  const retained = index("failed_retained");
  story.controller.setStacks(retained);
  record("a failed refresh keeps the snapshot, which still groups", story, retained);
  story.controller.setStacks(index("empty"));
  record("a repository with no stacks: flat", story, index("empty"));
  const other = mount({ filter: "open", list: "another_reader" });
  other.controller.setStacks(current);
  await other.controller.start({ shown: true });
  await settle();
  record("stacks read for another account: flat", other, current);

  // ── The page's stack menu lists the members in the groups' order, under one label.
  const listeners = new Map();
  globalThis.HTMLElement = FakeElement;
  globalThis.document = {
    activeElement: null,
    createElement: (tag) => new FakeElement(tag),
    createTextNode: (text) => text,
    addEventListener: (type, listener) => listeners.set(type, listener),
  };
  const stack = shared.byPull.get(9)[0];
  const menu = page.createStackMenu(stack, 9, {
    link(number) {
      const link = new FakeElement("a");
      link.dataset.number = String(number);
      return link;
    },
    icon: null,
    currentTitle: "",
    onOpen() {},
  });
  menu.element.open = true;
  menu.element.listeners.get("toggle")();
  const group = menu.element.childNodes
    .find((node) => node.classList.contains("github-pull-stack-menu"))
    .childNodes.find((node) => node.classList.contains("menu-group"));
  const [heading, ...links] = group.childNodes;
  const menuOrder = links.map((link) => Number(link.dataset.number));
  story.controller.setStacks(shared);
  const groupRow = story
    .model()
    .stacks.rows.find((row) => row.kind === "stack" && row.stack.number === stack.number);
  assert.deepEqual(menuOrder, groupRow.members, "the menu and the group list one order");
  menu.dispose();

  process.stdout.write(
    `${JSON.stringify(
      {
        steps,
        menu: {
          heading: heading.textContent,
          headingClasses: heading.className,
          trigger: menu.element.childNodes[0].getAttribute("aria-label"),
          triggerTip: menu.element.childNodes[0].dataset.tipText,
          members: menuOrder,
          groupRow: { label: groupRow.label, members: groupRow.members },
        },
        invariants: true,
      },
      null,
      2,
    )}\n`,
  );
})().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
