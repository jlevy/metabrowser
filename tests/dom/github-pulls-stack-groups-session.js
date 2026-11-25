// Browserless session: the Pulls tab grouped by stack, through the production code.
//
// builtin_plugins/github/pulls-panel.js's controller decides the rows the list draws and the
// keys walk, and builtin_plugins/github/pull-stacks.js how they group: each stack with a pull
// request in the list has a "Stack #N" row, open by default, with its pull requests under it
// in the stack menu's order, top of the stack first; pull requests in no stack follow, in the
// list's order; one in two stacks sits once, under the first; and with no stacks known for
// the list's reader the list stays flat. The tab always groups; there is no option. Its answers
// are the server's: the lists in tests/fixtures/github-pulls-panel-responses.json and the
// stack snapshots in tests/fixtures/github-stacks-responses.json, which
// tests/test_github_pulls_panel_session.py records from the real routes.
//
// The page's stack menu (pull-page.js, `createStackMenu`) is mounted over a stand-in for the
// DOM, and its member links are read back: the groups list a stack's pull requests in the
// order the menu does. Each step prints the rows, the row marks, and what opened;
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

/**
 * Mount the production panel over a stand-in for the DOM, on the recorded All list and
 * stack snapshot, and drive what its handle and its list do with a stack's row: Space's
 * toggle, Right and Left (a member's files open, then closed), and a press. Each step
 * prints the tree's drawn rows with their roles and places, and the mounted list each
 * member's muted line as drawn: its place in its stacks, its number, and its author.
 */
async function mountStory() {
  const panel = await import(pathToFileURL(path.join(GITHUB, "pulls-panel.js")).href);
  const { FakeNode } = require("./pulls-test-dom.js");
  /** The toolbar's markup: the filter chips it was drawn from. */
  let filterOptions = [];
  class PanelElement extends FakeElement {
    set innerHTML(markup) {
      super.innerHTML = markup;
      if (this.classList.contains("github-pulls-filters")) {
        for (const option of filterOptions) {
          const chip = new PanelElement("button");
          chip.dataset.chipValue = option.value;
          chip.append(option.label);
          this.append(chip);
        }
      }
    }
    querySelectorAll(selector) {
      return selector === "button" && this.classList.contains("github-pulls-filters")
        ? this.childNodes
        : super.querySelectorAll();
    }
  }
  const frames = [];
  const document = {
    activeElement: null,
    visibilityState: "visible",
    addEventListener() {},
    createElement: (tag) => new PanelElement(tag),
    createDocumentFragment: () => new FakeNode("#fragment"),
    importNode: (node) => new PanelElement(node.localName),
  };
  const answer = (body, status = 200) =>
    Promise.resolve({ status, headers: { get: () => null }, json: async () => body });
  const opened = [];
  /** Every route the mounted list fetches. */
  const requests = [];
  const globals = {
    document,
    window: {
      addEventListener() {},
      setTimeout: () => 0,
      clearTimeout() {},
      requestAnimationFrame(callback) {
        frames.push(callback);
        return frames.length;
      },
      cancelAnimationFrame() {},
    },
    getComputedStyle: () => ({ getPropertyValue: () => "24" }),
    HTMLElement: FakeElement,
    Element: FakeElement,
    MouseEvent: class {},
    DOMParser: class {
      parseFromString() {
        return { body: { firstElementChild: new PanelElement("svg") } };
      }
    },
    IntersectionObserver: class {
      takeRecords() {}
      observe() {}
      disconnect() {}
    },
    fetch(route) {
      requests.push(route);
      if (route.startsWith("/api/plugin/github/pulls?")) {
        return answer(route.includes("&after=") ? lists.more_window.body : lists.current.body);
      }
      if (route === "/api/plugin/github/stacks") {
        return answer(stacks.current.body);
      }
      if (route === "/api/plugin/github/pulls-prefetch") {
        return answer({ prefetch: "not_due" });
      }
      // A refresh, a record, or a pull request's files: nothing this story reads.
      return answer(null, 404);
    },
  };
  const saved = {};
  for (const [name, value] of Object.entries(globals)) {
    saved[name] = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, { value, configurable: true, writable: true });
  }
  const paint = async () => {
    await settle();
    for (const frame of frames.splice(0)) {
      frame();
    }
    await settle();
  };
  try {
    const container = new PanelElement("div");
    const handle = panel.mountPullsPanel(
      container,
      {
        kind: "pull-request-list",
        pullsNav: {
          filter: "all",
          current: null,
          shown: true,
          refreshAhead: false,
          scrollRoot: null,
          open: (route) => opened.push(route.number),
          file: null,
          fileHref: (number, file) => `/pull/${number}/files/${file}`,
          pageFor: () => null,
          onPageChange: () => () => {},
          filterChanged() {},
        },
      },
      {
        ...require("./sdk-ref-fixture.js").refHelpers(document),
        perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
        filterControls: {
          groupHtml({ options }) {
            filterOptions = options;
            return "<div></div>";
          },
          bind: () => () => {},
        },
        formatAge: () => ({ label: "1m", className: "age-min" }),
        formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
      },
    );
    await paint();
    const list = container.childNodes.find((node) => node.classList?.contains("github-pulls-list"));
    // A stack's row is its item's one line; a pull request's row leads its three lines' zone
    // (mb-1z7j).
    const rowOf = (item) =>
      item.childNodes[0].classList.contains("github-pulls-entry")
        ? item.childNodes[0].childNodes[0]
        : item.childNodes[0];
    const drawnRows = () =>
      list.childNodes.filter((item) => item.classList.contains("github-pulls-item")).map(rowOf);
    const stackRow = () => drawnRows().find((row) => row.dataset.stack === "286");
    // A pull request's change line, its third line, which carries the toggle of the changed
    // files its row owns (mb-1z7j).
    const changeOf = (row) =>
      row.parentNode.childNodes.find((node) => node.classList?.contains("github-pulls-change")) ??
      null;
    const pullRow = (number) => drawnRows().find((row) => row.dataset.number === String(number));
    /** The line under a row: hidden from assistive technology, its chevron turned or not. */
    const saidLine = (line, name) =>
      [
        name,
        line.getAttribute("aria-hidden") === "true" ? "hidden" : "exposed",
        `chevron ${line.classList.contains("expanded") ? "expanded" : "collapsed"}`,
        document.activeElement === line ? "focused" : null,
      ]
        .filter(Boolean)
        .join(" · ");
    /** One element as drawn: its name, role, level, place, expansion, Tab stop, and focus. */
    const said = (row, name) =>
      [
        name,
        row.getAttribute("role"),
        row.getAttribute("aria-level") === null ? null : `level ${row.getAttribute("aria-level")}`,
        row.getAttribute("aria-posinset") === null
          ? null
          : `${row.getAttribute("aria-posinset")}/${row.getAttribute("aria-setsize")}`,
        `expanded ${row.getAttribute("aria-expanded")}`,
        row.getAttribute("tabindex") === "0" ? "Tab stop" : null,
        document.activeElement === row ? "focused" : null,
      ]
        .filter(Boolean)
        .join(" · ");
    /** The tree as drawn, to the first pull request in no stack, with its roles and places:
     * each pull request's row, then the change line under it. */
    const tree = () => {
      const rows = drawnRows();
      const end = rows.findIndex(
        (row) => row.getAttribute("aria-level") === "1" && !row.dataset.stack,
      );
      return rows
        .slice(0, end + 1)
        .flatMap((row) =>
          row.dataset.stack
            ? [said(row, `Stack #${row.dataset.stack}`)]
            : [
                said(row, `#${row.dataset.number}`),
                saidLine(changeOf(row), `  #${row.dataset.number}'s change line`),
              ],
        );
    };
    const steps = [];
    const step = async (what, act) => {
      const handled = act();
      await paint();
      steps.push({
        step: what,
        ...(handled === undefined ? {} : { handled }),
        tree: tree(),
        ...(opened.length > 0 ? { opened: opened.splice(0) } : {}),
      });
    };
    await step("mounted: Stack #286 open, its pull requests a level in", () => undefined);
    // Each member's muted line as drawn (pulls-panel.js#paintPlace and #rowMeta): its place
    // before its number, "3/3 · #8", where another stack's glyph is written ⧉, and no
    // stack icon on its row, whose stack's row has it (mb-dzsi).
    const find = (node, name) =>
      node.classList?.contains(name)
        ? node
        : (node.childNodes ?? []).reduce((found, child) => found ?? find(child, name), null);
    const textOf = (node) =>
      node.data !== undefined
        ? node.data
        : node.classList?.contains("github-pull-stack-other")
          ? "⧉"
          : (node.childNodes ?? []).map(textOf).join("");
    const memberLines = drawnRows()
      .filter((row) => row.getAttribute("aria-level") === "2")
      .map((row) => {
        assert.equal(
          find(row, "github-pull-stack-icon"),
          null,
          "a member's row draws no stack icon",
        );
        const id = find(row, "github-pulls-id");
        assert.equal(
          id.childNodes[0],
          find(row, "github-pulls-place"),
          "the place leads the number",
        );
        return `#${row.dataset.number}: ${textOf(find(row, "github-pulls-line"))}`;
      });
    await step("Space on the stack's row (the handle's toggleStack) closes it", () =>
      handle.toggleStack(286),
    );
    await step("and again opens it", () => handle.toggleStack(286));
    await step("Right on the stack's row goes to its first pull request, which opens", () =>
      handle.expand(),
    );
    await step("Right on that pull request opens its files, as on a folder's", () =>
      handle.expand(),
    );
    const filesOpen = pullRow(8).getAttribute("aria-expanded");
    await step("Left first closes its files, keeping the pull request", () => handle.collapse());
    const filesClosed = pullRow(8).getAttribute("aria-expanded");
    await step("Left again goes to the stack's row", () => handle.collapse());
    await step("Left on the stack's row closes it", () => handle.collapse());
    // A press on the stack's label, in its heading, as a click lands: the row takes the
    // anchor and opens.
    const heading = stackRow().childNodes.find((node) =>
      node.classList?.contains("github-pulls-stack-heading"),
    );
    const label = heading.childNodes.find((node) =>
      node.classList?.contains("github-pull-stack-label"),
    );
    await step("a press on the stack's row opens it", () =>
      list.listeners.get("click")({ target: label, button: 0, preventDefault() {} }),
    );
    // Home (docs/design-system.md, "Home"): the list as a fresh load draws it. The reader
    // opens #8's files, walks to the first pull request in no stack, and closes the stack;
    // Home opens it, closes #8's files, and gives the Tab stop back to the stack's row. The
    // address it opens names no pull request, which the host tells the list next.
    await step("Right, Right: #8 opens, then its files", () => {
      handle.expand();
      return handle.expand();
    });
    await step("K back to #8's row, J past the stack, then Space on its row closes it", () => {
      handle.move(-1);
      for (let press = 0; press < 3; press += 1) {
        handle.move(1);
      }
      return handle.toggleStack(286);
    });
    const homeRequests = requests.length;
    await step("Home: every stack open, no files open, the Tab stop on the first row", () => {
      handle.home();
      handle.setCurrent(null);
    });
    const homed = steps.at(-1).tree;
    assert.ok(homed[0].startsWith("Stack #286") && homed[0].endsWith("Tab stop"), homed[0]);
    assert.ok(
      homed.every((row) => !row.includes("change line") || row.includes("chevron collapsed")),
      "no pull request's files are open",
    );
    assert.equal(pullRow(8).getAttribute("aria-expanded"), "false", "#8's files closed");
    assert.deepEqual(requests.slice(homeRequests), [], "Home reads nothing");
    handle.dispose();
    return {
      "member lines": memberLines,
      files: { "Right on #8": filesOpen, "then Left": filesClosed },
      label: { text: label.textContent, classes: label.className },
      steps,
    };
  } finally {
    for (const [name, descriptor] of Object.entries(saved)) {
      if (descriptor === undefined) {
        delete globalThis[name];
      } else {
        Object.defineProperty(globalThis, name, descriptor);
      }
    }
  }
}

(async () => {
  const stackModule = await import(pathToFileURL(path.join(GITHUB, "pull-stacks.js")).href);
  const panel = await import(pathToFileURL(path.join(GITHUB, "pulls-panel.js")).href);
  const page = await import(pathToFileURL(path.join(GITHUB, "pull-page.js")).href);
  const { createStackIndex, stackCaption, stackMenuOrder } = stackModule;
  const index = (name) => createStackIndex(stacks[name].body);

  /** One panel's controller over recorded answers, with every effect it asks for logged. */
  function mount({ filter = "all", list = "current" } = {}) {
    // `requests` counts every request, which Home's reset makes none of.
    const log = { opened: [], marks: [], prefetch: [], requests: 0 };
    let model = null;
    let anchor = null;
    const timers = new Map();
    let nextTimer = 1;
    const controller = panel.createPullsController(
      {
        request(method, route, options) {
          log.requests += 1;
          if (route === "/api/plugin/github/pulls-prefetch") {
            // What an open asks to read ahead: its neighbours as drawn, and the top.
            log.prefetch.push(options.body);
          }
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
        formatCount: (count) => count.toLocaleString("en-US"),
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
      },
      { filter, current: null },
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
    // A badge as drawn: another stack is the Layers glyph, written ⧉, before its number.
    const caption = (number, under) =>
      (stackCaption(stackIndex, identity, number, under)?.parts ?? [])
        .map((part) => (part.stack === null ? part.position : `⧉${part.stack} ${part.position}`))
        .join(" · ");
    if (model.stacks.rows === null) {
      const rows = model.rows.map((row) => `#${row.number} ${caption(row.number, null)}`.trim());
      return rows.length > 4 ? [...rows.slice(0, 3), "…", rows.at(-1)] : rows;
    }
    const lines = [];
    const rest = [];
    for (const row of model.stacks.rows) {
      if (row.kind === "stack") {
        lines.push(
          `${row.expanded ? "▾" : "▸"} ${row.label} [${row.posinset}/${row.setsize}] · ${row.hint}`,
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
      grouped: model.stacks.rows !== null,
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
    record(`stacks ${name}: flat`, story, index(name));
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
  // The last open, #6, reads ahead its neighbours as drawn, #7 above it and #106 below, a
  // stack's row passed over, and the top: the stack's pull requests first.
  const ahead = story.log.prefetch.at(-1);
  story.log.prefetch.length = 0;
  record("J walks into the stack and out past it, K steps back; only pulls open", story, current, {
    "read ahead after the last open": ahead?.records ?? null,
  });
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
  // Home (docs/design-system.md, "Home"): the rows as a fresh load draws them, from the rows
  // held. The reader closes the stack and walks past it; Home opens it again and gives the
  // Tab stop back to the first row, and the address it opens, /view/, names no pull request.
  await story.key("Left");
  await story.key("Left");
  await story.key("J");
  record("the reader closes the stack and walks past it", story, current, {
    closed: story.controller.snapshot().closedStacks,
    tabStop: story.anchor(),
  });
  const homeReads = story.log.requests;
  story.controller.home();
  story.controller.setCurrent(null);
  await settle();
  record("Home: every stack open, and the Tab stop on the first row", story, current, {
    closed: story.controller.snapshot().closedStacks,
    tabStop: story.anchor(),
    requests: story.log.requests - homeReads,
  });
  assert.deepEqual(story.controller.snapshot().closedStacks, [], "Home opens every stack");
  assert.equal(story.anchor(), story.model().stacks.rows[0].key, "the Tab stop is the first row's");

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

  // ── The mounted panel: the keys' routing through its handle, a press on a stack's row,
  // and the tree's roles, over a stand-in for the DOM (as github-pulls-panel-session.js
  // mounts it). Layout, focus rings, and scrolling stay the paint row's, measured in Chrome.
  const mounted = await mountStory();

  // ── The page's stack menu lists the members in the groups' order, under one label.
  const listeners = new Map();
  globalThis.HTMLElement = FakeElement;
  globalThis.document = {
    activeElement: null,
    createElement: (tag) => new FakeElement(tag),
    createTextNode: (text) => text,
    addEventListener: (type, listener) => listeners.set(type, listener),
    importNode: (node) => new FakeElement(node.localName),
  };
  const stack = shared.byPull.get(9)[0];
  // Each member's state as its page draws it (`stackMemberState`): the page's own, #9's, as
  // the list said it, and the others' as the list said them, the list the panel above read.
  const { listedState } = await import(pathToFileURL(path.join(GITHUB, "pull-state.js")).href);
  const source = story.identity.source;
  const menuDeps = {
    state: (target) =>
      page.stackMemberState(source, target, 9, listedState(source, 9)?.state ?? null),
    link(number) {
      const link = new FakeElement("a");
      link.dataset.number = String(number);
      return link;
    },
    icon: null,
    currentTitle: "",
    titleNodes: require("./sdk-ref-fixture.js").refHelpers(document).titleNodes,
    onOpen() {},
  };
  const menu = page.createStackMenu(stack, 9, menuDeps);
  // A press opens it, as a <details> does, with focus on its trigger; the menu puts focus on
  // its current member.
  document.activeElement = menu.element.childNodes[0];
  menu.element.open = true;
  menu.element.listeners.get("toggle")();
  const landed = document.activeElement;
  assert.equal(landed.getAttribute("aria-current"), "page", "the menu opens on its current member");
  const group = menu.element.childNodes
    .find((node) => node.classList.contains("github-pull-stack-menu"))
    .childNodes.find((node) => node.classList.contains("menu-group"));
  const [heading, ...links] = group.childNodes;
  const menuOrder = links.map((link) => Number(link.dataset.number));
  // Each member's one line as drawn (mb-as06): its state icon's state, then its text, the
  // bold place, the muted dot, and the title, then the number a screen reader says and the
  // line does not show, its visually hidden part, here in brackets; and the parts the line
  // is made of, one layout for every member, the current one too.
  const elements = (node) => node.childNodes.filter((child) => child instanceof FakeElement);
  const memberLines = links.map((link) => {
    const [icon, copy] = elements(link);
    const text = copy.childNodes
      .map((child) =>
        child instanceof FakeElement && child.classList.contains("visually-hidden")
          ? `[said, not shown: ${child.textContent}]`
          : typeof child === "string"
            ? child
            : child.textContent,
      )
      .join("");
    return `${icon.dataset.state ?? "(state unknown)"} ${text}`;
  });
  const memberLayouts = new Set(
    links.map((link) =>
      JSON.stringify([
        ...elements(link).map((part) => part.className),
        ...elements(elements(link)[1]).map((part) => part.className),
      ]),
    ),
  );
  assert.equal(memberLayouts.size, 1, "every member has one layout, the current one too");
  story.controller.setStacks(shared);
  const groupRow = story
    .model()
    .stacks.rows.find((row) => row.kind === "stack" && row.stack.number === stack.number);
  assert.deepEqual(menuOrder, groupRow.members, "the menu and the group list one order");
  const triggerText = menu.element.childNodes[0].textContent;
  menu.dispose();
  // A pull request in two stacks, #8: its page draws a chip for each, and each names its
  // stack before its position (`named`, which the page passes when the pull request is in
  // more than one stack), as #8's Pulls row names the other stack.
  const named = shared.byPull.get(8).map((each) => {
    const chip = page.createStackMenu(each, 8, { ...menuDeps, named: true });
    const trigger = chip.element.childNodes[0];
    const shown = { triggerText: trigger.textContent, trigger: trigger.getAttribute("aria-label") };
    chip.dispose();
    return shown;
  });

  process.stdout.write(
    `${JSON.stringify(
      {
        steps,
        mounted,
        menu: {
          heading: heading.textContent,
          headingClasses: heading.className,
          trigger: menu.element.childNodes[0].getAttribute("aria-label"),
          triggerText,
          triggerTip: menu.element.childNodes[0].dataset.tipText,
          focusOnOpen: {
            member: Number(landed.dataset.number),
            current: landed.getAttribute("aria-current") === "page",
          },
          members: menuOrder,
          lines: memberLines,
          layout: JSON.parse([...memberLayouts][0]),
          groupRow: { label: groupRow.label, members: groupRow.members },
          named,
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
