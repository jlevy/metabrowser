// Browserless session: the Pulls tab grouped by stack, through the production code.
//
// builtin_plugins/github/pulls-panel.js's controller decides the rows the list draws and the
// keys walk, and builtin_plugins/github/pull-stacks.js how they group: each stack with a pull
// request in the list has a "Stack #N" row, open by default, with its Whole stack row and
// its pull requests under it, one level in, in the stack menu's order, top of the stack
// first; pull requests in no stack follow, in the list's order; one in two stacks sits
// once, under the first; and with no stacks known for
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
 * stack snapshot, and drive what its handle and its list do with a stack's row and its
 * Whole stack row: Space's toggles, Right and Left (a member's files open, then closed, and
 * the Whole stack row's, the stack's own), and a press on a row or on a change line. Each step
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
          open: (route) =>
            opened.push(route.stack ? `Stack #${route.number}'s page` : route.number),
          file: null,
          fileHref: (number, file) => `/pull/${number}/files/${file}`,
          stackFileHref: (stack, file) => `/stack/${stack}/changes/${file}`,
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
        ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
          label: "1m",
          className: "age-min",
        })),
        formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
      },
    );
    await paint();
    const list = container.childNodes.find((node) => node.classList?.contains("github-pulls-list"));
    // A stack's row is its item's one line; a pull request's row is its zone's link (mb-1z7j).
    const rowOf = (item) =>
      item.childNodes[0].classList.contains("github-pulls-entry")
        ? item.childNodes[0].childNodes[0]
        : item.childNodes[0];
    const drawnRows = () =>
      list.childNodes.filter((item) => item.classList.contains("github-pulls-item")).map(rowOf);
    const isWhole = (row) => row.classList.contains("github-pulls-whole-row");
    const stackRow = () => drawnRows().find((row) => row.dataset.stack === "286" && !isWhole(row));
    /** The first element under *node*, at any depth, with the class *name*, or null. */
    const find = (node, name) =>
      node.classList?.contains(name)
        ? node
        : (node.childNodes ?? []).reduce((found, child) => found ?? find(child, name), null);
    // A pull request's toggle, the lines and the chevron at its run's end, which opens and
    // closes the changed files its row owns (mb-1z7j, mb-pw8t).
    const changeOf = (row) => find(row, "github-pulls-change");
    const pullRow = (number) => drawnRows().find((row) => row.dataset.number === String(number));
    const wholeRow = () => drawnRows().find((row) => row.dataset.stack === "286" && isWhole(row));
    /** Stack #286's pull requests as drawn: the rows a level in that are no Whole stack row. */
    const membersDrawn = () =>
      drawnRows()
        .filter((row) => row.getAttribute("aria-level") === "2" && !isWhole(row))
        .map((row) => Number(row.dataset.number));
    /** A row's toggle: hidden from assistive technology, its chevron turned or not. */
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
        row.getAttribute("aria-expanded") === null
          ? null
          : `expanded ${row.getAttribute("aria-expanded")}`,
        row.getAttribute("tabindex") === "0" ? "Tab stop" : null,
        document.activeElement === row ? "focused" : null,
      ]
        .filter(Boolean)
        .join(" · ");
    /** The tree as drawn, to the first pull request in no stack, with its roles and places:
     * each pull request's row, then its toggle. */
    const tree = () => {
      const rows = drawnRows();
      const end = rows.findIndex(
        (row) => row.getAttribute("aria-level") === "1" && !row.dataset.stack,
      );
      return rows
        .slice(0, end + 1)
        .flatMap((row) =>
          isWhole(row)
            ? [
                [
                  said(row, `Whole stack of #${row.dataset.stack}`),
                  row.getAttribute("href"),
                  row.getAttribute("aria-current") === "page" ? "current" : null,
                ]
                  .filter(Boolean)
                  .join(" · "),
                saidLine(changeOf(row), `  Whole stack of #${row.dataset.stack}'s toggle`),
              ]
            : row.dataset.stack
              ? [said(row, `Stack #${row.dataset.stack}`)]
              : [
                  said(row, `#${row.dataset.number}`),
                  saidLine(changeOf(row), `  #${row.dataset.number}'s toggle`),
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
    await step(
      "mounted: Stack #286 open, its Whole stack row and its pull requests one level in",
      () => undefined,
    );
    // The heading as first drawn, before any read of the stack's change answers: its label,
    // the stack's size as a count summary, and its age, all there at once, and its
    // accessible name, which says the count the heading shows.
    const headingOf = (row) => {
      const heading = row.childNodes.find((node) =>
        node.classList?.contains("github-pulls-stack-heading"),
      );
      const age = row.childNodes.find((node) => node.classList?.contains("github-pulls-age"));
      return {
        text: heading.childNodes.map((node) => node.textContent).join(" "),
        age: age.textContent,
        name: row.getAttribute("aria-label"),
      };
    };
    const headingDrawn = headingOf(stackRow());
    const shownCount = /· (\d+) pulls?$/.exec(headingDrawn.text)?.[1];
    assert.ok(
      shownCount !== undefined &&
        headingDrawn.name.startsWith(`Stack #286, ${shownCount} pull request`),
      "the heading's accessible name says the count it shows",
    );
    // Each member's run as drawn (pulls-panel.js, `paintPlace` and `buildRow`): the state
    // icon, then the title, then the stack menu's muted dot and its place in bold, " · 3/3",
    // where another stack's glyph is written ⧉, then the dot and the number, and no stack icon
    // on its row, whose stack's row has it (mb-dzsi, mb-vkhd, mb-pw8t). A pull request in no
    // stack has no place and no dot before one.
    const textOf = (node) =>
      node.data !== undefined
        ? node.data
        : node.classList?.contains("github-pull-stack-other")
          ? "⧉"
          : (node.childNodes ?? []).map(textOf).join("");
    const classOf = (node) => node.className?.split(" ")[0];
    const titleLine = (row) => {
      const heading = find(row, "github-pulls-heading");
      assert.deepEqual(
        heading.childNodes.map(classOf).slice(0, 5),
        [
          "github-pull-state-icon",
          "github-pulls-title",
          "github-pulls-place",
          "github-pulls-sep",
          "github-pulls-number",
        ],
        "the state icon, then the title, the place, and the number, one flow",
      );
      const place = heading.childNodes[2];
      const number = heading.childNodes[4];
      // The no-break space before each dot is written as a space.
      const text = [heading.childNodes[1], place, heading.childNodes[3], number.firstChild]
        .map(textOf)
        .join("")
        .replaceAll("\u00a0", " ");
      return { heading, place, text };
    };
    const memberLines = drawnRows()
      .filter((row) => row.getAttribute("aria-level") === "2" && !isWhole(row))
      .map((row) => {
        assert.equal(
          find(row, "github-pull-stack-icon"),
          null,
          "a member's row draws no stack icon",
        );
        const { place, text } = titleLine(row);
        assert.equal(place.hidden, false, "a member's place is shown");
        // The place and its dot follow the title: a no-break space, so no line starts with the
        // dot, the dot, and a space, where the run may wrap, then the position.
        assert.deepEqual(
          place.childNodes.map((node) => classOf(node) ?? node.data),
          ["\u00a0", "github-pull-stack-dot", " ", "github-pull-stack-position"],
          "the place is the dot, then the position, after the title",
        );
        const dot = place.childNodes[1];
        assert.equal(textOf(dot), "·");
        assert.equal(dot.getAttribute("aria-hidden"), "true", "the place's label says it");
        return `#${row.dataset.number}: ${text}`;
      });
    const loose = drawnRows().find(
      (row) => row.getAttribute("aria-level") === "1" && !row.dataset.stack,
    );
    const looseLine = titleLine(loose);
    assert.equal(looseLine.place.hidden, true, "a pull request in no stack has no place");
    assert.equal(looseLine.place.childNodes.length, 0, "and no dot");
    const unstacked = `#${loose.dataset.number}: ${looseLine.text}`;
    await step("Space on the stack's row (the handle's toggleStack) closes it", () =>
      handle.toggleStack(286),
    );
    await step("and again opens it", () => handle.toggleStack(286));
    await step(
      "Right on the stack's row goes to its first row, Whole stack, which opens the stack's page",
      () => handle.expand(),
    );
    // The Whole stack row's children are the stack's changed files, as a pull request's
    // row's are its own: Right opens them, and Left closes them before it goes up. No pull
    // request is under it, opened or closed.
    const membersBeside = membersDrawn();
    assert.ok(membersBeside.length > 0, "the stack's pull requests are drawn beside it");
    const beforeStackFiles = requests.length;
    await step(
      "Right on the Whole stack row opens the stack's changed files, as on a pull request's row",
      () => handle.expand(),
    );
    const stackFilesOpen = wholeRow().getAttribute("aria-expanded");
    // What opening them reads: the stack, as its page reads it, and nothing before.
    const stackFilesRequests = requests.slice(beforeStackFiles);
    assert.deepEqual(membersDrawn(), membersBeside, "opening them hides no pull request");
    await step("Left first closes them, keeping the Whole stack row", () => handle.collapse());
    const stackFilesClosed = wholeRow().getAttribute("aria-expanded");
    assert.deepEqual(membersDrawn(), membersBeside, "the members stay as they were, beside it");
    await step("J goes to its first pull request, which opens", () => handle.move(1));
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
    // opens the stack's files and #8's, walks down the stack, and closes it; Home opens it,
    // closes the stack's files and #8's, and gives the Tab stop to the newest row. The
    // address it opens names no pull request, which the host tells the list next.
    await step(
      "Right, Right, J, Right: the Whole stack row, the stack's files, then #8, then #8's files",
      () => {
        handle.expand();
        handle.expand();
        handle.move(1);
        return handle.expand();
      },
    );
    await step(
      "K back to the Whole stack row, J down the stack, then Space on its row closes it",
      () => {
        handle.move(-1);
        for (let press = 0; press < 3; press += 1) {
          handle.move(1);
        }
        return handle.toggleStack(286);
      },
    );
    const homeRequests = requests.length;
    await step("Home: every stack open, no files open, the Tab stop on the first row", () => {
      handle.home();
      handle.setCurrent(null);
    });
    const homed = steps.at(-1).tree;
    assert.ok(homed[0].startsWith("#106") && homed[0].endsWith("Tab stop"), homed[0]);
    assert.ok(
      homed.every((row) => !row.includes("change line") || row.includes("chevron collapsed")),
      "no pull request's files are open",
    );
    assert.equal(pullRow(8).getAttribute("aria-expanded"), "false", "#8's files closed");
    assert.equal(wholeRow().getAttribute("aria-expanded"), "false", "the stack's files closed");
    assert.deepEqual(requests.slice(homeRequests), [], "Home reads nothing");
    // The stack's Whole stack row, the first of its set: Space, or a press on its change
    // line or the chevron after it, opens and closes the stack's changed files and opens no
    // page; a press anywhere else on it opens the stack's page, as a pull request's row
    // opens its own, and while that page is open the row is the current row, until an
    // address that names a pull request takes the mark back.
    const wholeTitle = find(wholeRow(), "github-pulls-whole-title");
    const wholeName = wholeRow().getAttribute("aria-label");
    // Its toggle is a pull request's row's: the change line's box, then the chevron, last.
    assert.deepEqual(
      changeOf(wholeRow()).childNodes.map(classOf),
      ["github-pulls-stack-change", "github-pulls-toggle"],
      "the Whole stack row's toggle is its change line, then the chevron after it",
    );
    assert.deepEqual(
      wholeRow().childNodes.map(classOf),
      ["github-pull-stack-icon", "github-pulls-whole-line"],
      "the Whole stack row leads with the Layers glyph, and no chevron",
    );
    await step(
      "Space on the Whole stack row (the handle's toggleStackFiles) opens the stack's changed files",
      () => handle.toggleStackFiles(286),
    );
    assert.equal(opened.length, 0, "Space on the Whole stack row opens no page");
    let prevented = 0;
    for (const [part, name] of [
      ["github-pulls-stack-change", "a press on its change line closes them, and opens no page"],
      ["github-pulls-toggle", "a press on the chevron after it opens them, and opens no page"],
    ]) {
      await step(name, () =>
        list.listeners.get("click")({
          target: find(changeOf(wholeRow()), part),
          button: 0,
          preventDefault() {
            prevented += 1;
          },
        }),
      );
      assert.equal(steps.at(-1).opened, undefined, "a press on the toggle opens no page");
    }
    assert.equal(prevented, 2, "neither press follows the row's link");
    await step("Left on the Whole stack row closes them", () => handle.collapse());
    await step("a press on the Whole stack row opens the stack's page", () =>
      list.listeners.get("click")({ target: wholeTitle, button: 0, preventDefault() {} }),
    );
    await step("the stack's page is open: its Whole stack row is the current row", () =>
      handle.setCurrent(null, null, { stack: 286 }),
    );
    await step("Left on it goes to the stack's row", () => handle.collapse());
    await step("an address that names #8 takes the mark back", () => handle.setCurrent(8));
    assert.equal(wholeRow().getAttribute("aria-current"), null, "the mark has left the row");
    handle.dispose();
    return {
      "member lines": memberLines,
      "a pull request in no stack": unstacked,
      files: { "Right on #8": filesOpen, "then Left": filesClosed },
      "the stack's files": {
        "Right on the Whole stack row": stackFilesOpen,
        "then Left": stackFilesClosed,
        "requests when first opened": stackFilesRequests,
      },
      label: { text: label.textContent, classes: label.className },
      heading: headingDrawn,
      "Whole stack row": { name: wholeName },
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
  const { createStackIndex, stackCaption, stackMenuOrder, wholeStackOfKey, wholeStackRowKey } =
    stackModule;
  /** A row key as a reader names the row: a pull request, a stack, or a stack's Whole stack. */
  const rowName = (key) =>
    key === null
      ? null
      : wholeStackOfKey(key) !== null
        ? `Whole stack of #${wholeStackOfKey(key)}`
        : key < 0
          ? `Stack #${-key}`
          : `#${key}`;
  const index = (name) => createStackIndex(stacks[name].body);

  /** One panel's controller over recorded answers, with every effect it asks for logged. */
  function mount({ filter = "all", list = "current", byState = false, window = null } = {}) {
    // `requests` counts every request, which Home's reset makes none of.
    const log = { opened: [], marks: [], prefetch: [], revealed: [], requests: 0 };
    let model = null;
    let anchor = null;
    /** The row the current-row mark is on. */
    let marked = null;
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
          if (byState && method === "GET" && route.startsWith("/api/plugin/github/pulls?")) {
            // Each filter's own list, for a story in which the list moves from Open to All:
            // Open's recorded list, and All's, in which a lookup places #8.
            const all = lists.current;
            const at = new URL(route, "http://example").searchParams.get("at");
            const catalog = [...all.body.rows, ...lists.more_window.body.rows];
            const position =
              at === null ? -1 : catalog.findIndex((row) => row.number === Number(at));
            const rows = route.includes("state=open")
              ? lists.open_current.body.rows
              : at !== null
                ? position === -1
                  ? []
                  : [catalog[position]]
                : route.includes("&after=")
                  ? lists.more_window.body.rows
                  : all.body.rows;
            const body = route.includes("state=open") ? lists.open_current.body : all.body;
            return Promise.resolve({ status: 200, etag: null, body: { ...body, rows, position } });
          }
          if (method === "GET" && route.startsWith("/api/plugin/github/pulls?")) {
            if (window !== null) {
              // Keep a partial cached window so a stack member below it has to come
              // from the stack projection.
              if (route.includes("&after=")) {
                return Promise.resolve({
                  status: 200,
                  body: { ...window, rows: [] },
                  etag: null,
                });
              }
              return Promise.resolve({ status: 200, body: window, etag: null });
            }
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
        markCurrent(previous, next) {
          // The panel's own rule: a mark that leaves clears only the row that held it.
          marked = panel.markedRow(marked, previous, next);
        },
        markAnchor(_previous, next, focus) {
          anchor = next;
          if (focus) {
            log.marks.push(`focus ${rowName(next)}`);
          }
        },
        reveal(key) {
          log.revealed.push(key);
        },
        open(route) {
          log.opened.push(route.number);
        },
        openStack(number) {
          log.opened.push(`Stack #${number}'s page`);
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
      marked: () => marked,
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

  /** What a reader sees of the rows, skipping the middle of long runs of standalone PRs. */
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
    const flush = () => {
      lines.push(...(rest.length > 3 ? [...rest.slice(0, 2), "…", rest.at(-1)] : rest));
      rest.length = 0;
    };
    for (const row of model.stacks.rows) {
      if (row.kind === "stack") {
        flush();
        // The heading as drawn: its label, the stack's size, and the time its age tells,
        // then its place and its accessible name's words.
        const pulls = stackModule.stackPullsCount(row.stack);
        lines.push(
          `${row.expanded ? "▾" : "▸"} ${row.label} · ${pulls} ${pulls === 1 ? "pull" : "pulls"} · updated ${row.updatedAt} [${row.posinset}/${row.setsize}] · ${row.hint}`,
        );
      } else if (row.kind === "whole") {
        lines.push(`    Whole stack [${row.posinset}/${row.setsize}]`);
      } else if (row.level === 2) {
        lines.push(
          `    #${row.number} ${caption(row.number, row.stack)} [${row.posinset}/${row.setsize}]`,
        );
      } else {
        rest.push(`#${row.number} [${row.posinset}/${row.setsize}]`);
      }
    }
    flush();
    return lines;
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
    const updated = new Map(model.rows.map((row) => [row.number, row.updatedAt]));
    for (const row of rows) {
      if (row.kind === "stack") {
        // Compare the stack projection with any newer times the current window has read.
        const times = row.stack.pulls.flatMap((number) => updated.get(number) ?? []);
        if (row.stack.updated_at) {
          times.push(row.stack.updated_at);
        }
        assert.equal(
          row.updatedAt === null ? null : Date.parse(row.updatedAt),
          times.length === 0 ? null : Math.max(...times.map((time) => Date.parse(time))),
          "a stack's time is its newest known member activity",
        );
        // Its accessible name says the count its heading shows.
        const pulls = stackModule.stackPullsCount(row.stack);
        assert.ok(
          row.hint.startsWith(`${row.label}, ${pulls} pull request${pulls === 1 ? "" : "s"}`),
          row.hint,
        );
        // Members are the stack menu's order, of the pull requests the list has.
        const order = stackMenuOrder(row.stack).filter((number) => row.members.includes(number));
        assert.deepEqual(row.members, order);
        for (const number of row.members) {
          assert.ok(stackModule.stackMembership(stackIndex, identity, number).includes(row.stack));
        }
      }
    }
    const top = rows.filter((row) => row.level === 1);
    const times = top.map(
      (row) => (row.kind === "stack" ? row.updatedAt : updated.get(row.number)) ?? "",
    );
    assert.deepEqual(times, [...times].sort().reverse(), "top-level rows are newest first");
    assert.deepEqual(
      top.map((row) => row.posinset),
      top.map((_row, at) => at + 1),
    );
    // The rows under each open stack are its pull requests and its one Whole stack row, a
    // level in, each placed in the stack's set where it is drawn; a closed one has none.
    for (const [at, row] of rows.entries()) {
      if (row.kind !== "stack") {
        continue;
      }
      const whole = rows.findIndex(
        (other) => other.kind === "whole" && other.stack === row.stack.number,
      );
      if (!row.expanded) {
        assert.equal(whole, -1, "a closed stack has no Whole stack row");
        continue;
      }
      const under = rows.slice(at + 1, at + row.members.length + 2);
      assert.deepEqual(
        under.flatMap((each) => (each.kind === "pull" ? [each.number] : [])),
        row.members,
      );
      assert.deepEqual(
        under.flatMap((each) => (each.kind === "whole" ? [each.key] : [])),
        [wholeStackRowKey(row.stack.number)],
        "an open stack has one Whole stack row, among its own rows",
      );
      for (const [place, each] of under.entries()) {
        assert.deepEqual([each.level, each.posinset, each.setsize], [2, place + 1, under.length]);
      }
    }
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

  // ── The session's second part, `node github-pulls-stack-groups-session.js reveal`: what a
  // reveal unfolds, and what stays folded. It prints on its own so each transcript stays
  // within what tryscript can match: one of 41 KB was refused as too large a regular
  // expression, where 39 KB matched.
  if (process.argv[2] === "reveal") {
    const current = index("current");
    // ── A reveal that must move the list first. #8 is closed, so Open leaves it out: an address
    // that names it moves the list to All, and the row arrives after the address was named. It
    // is revealed there as a row the list already held is, the stack the reader closed opened
    // over it (review of #862).
    for (const [how, hide] of [["closes Stack #286", (panel) => panel.setStackOpen(286, false)]]) {
      const moved = mount({ filter: "open", list: "open_current", byState: true });
      moved.controller.setStacks(current);
      await moved.controller.start({ shown: true });
      await settle();
      hide(moved.controller);
      await settle();
      const before = moved.controller.snapshot();
      moved.log.revealed.length = 0;
      moved.controller.setCurrent(8);
      await settle();
      await settle();
      const after = moved.controller.snapshot();
      record(
        `on Open the reader ${how}; an address that names #8, which Open leaves out, moves the list to All and reveals it there`,
        moved,
        current,
        {
          filter: `${before.filter} → ${after.filter}`,
          closed: `${JSON.stringify(before.closedStacks)} → ${JSON.stringify(after.closedStacks)}`,
          revealed: moved.log.revealed.splice(0).map(rowName),
          current: rowName(moved.marked()),
          tabStop: rowName(moved.anchor()),
        },
      );
      assert.equal(after.filter, "all");
      assert.ok(
        moved.model().stacks.rows.some((row) => row.kind === "pull" && row.number === 8),
        "#8's row is drawn once the list holds it",
      );
      assert.equal(moved.anchor(), 8, "and takes the Tab stop");
      moved.controller.dispose?.();
    }
    // ── What the reader folded stays folded until they open the item again. #7 is the open
    // pull request; the reader closes its stack. The tab
    // shown again, a landing that keeps the list's place, and a filter picked all ask for the
    // list, not the item, and unfold nothing; only an address that names the item again does
    // (docs/design-system.md, "Navigation Reveals the Item"; final review of #862).
    for (const [how, fold] of [["closes Stack #286", (panel) => panel.setStackOpen(286, false)]]) {
      const kept = mount({ filter: "all", byState: true });
      kept.controller.setStacks(current);
      await kept.controller.start({ shown: true });
      await settle();
      kept.controller.setCurrent(7);
      await settle();
      fold(kept.controller);
      await settle();
      // One line a state, so the transcript stays within what tryscript can match.
      const folded = () => {
        const { filter, closedStacks } = kept.controller.snapshot();
        return `${filter} · closed ${JSON.stringify(closedStacks)}`;
      };
      const asFolded = folded();
      const survived = {};
      kept.controller.setShown(false);
      kept.controller.setShown(true);
      await settle();
      survived["the tab hidden and shown again"] = folded();
      kept.controller.setCurrent(6, { preserveScroll: true });
      await settle();
      survived["a landing on #6 that keeps the list's place"] = folded();
      kept.controller.setFilter("open");
      await settle();
      await settle();
      survived["the Open filter picked"] = folded();
      assert.equal(survived["the tab hidden and shown again"], asFolded);
      assert.equal(survived["a landing on #6 that keeps the list's place"], asFolded);
      assert.equal(survived["the Open filter picked"], asFolded.replace(/^all/, "open"));
      assert.notEqual(asFolded, "all · closed []");
      kept.controller.setCurrent(7);
      await settle();
      record(
        `the reader ${how} over the open pull request, #7: the tab shown again, a landing that keeps the list's place, and a filter picked leave it folded, and an address that names #7 again opens the stack`,
        kept,
        current,
        {
          folded: asFolded,
          ...survived,
          "an address that names #7 again": folded(),
          tabStop: rowName(kept.anchor()),
        },
      );
      assert.equal(folded(), "open · closed []");
      kept.controller.dispose?.();
    }
    process.stdout.write(`${JSON.stringify({ steps, invariants: true }, null, 2)}\n`);
    return;
  }

  if (process.argv[2] === "recency") {
    const pull = (number, hour, state) => ({
      number,
      title: `PR ${number}`,
      state,
      updated_at: `2026-09-17T${hour}:00Z`,
    });
    const open = [pull(5, "13:00", "open"), pull(99, "12:00", "open"), pull(101, "11:00", "open")];
    const closed = [
      pull(6, "13:00", "closed"),
      pull(98, "12:00", "closed"),
      pull(102, "11:00", "closed"),
    ];
    const members = [
      [pull(7, "08:00", "open"), pull(8, "12:30", "closed")],
      [pull(12, "11:30", "open"), pull(13, "07:00", "closed")],
    ];
    const template = stacks.current.body;
    const snapshot = (groups) =>
      createStackIndex({
        ...template,
        stacks: groups.map(([open, closed], i) => ({
          ...template.stacks[0],
          number: 286 + i,
          pulls: [open.number, closed.number],
          updated_at: [open.updated_at, closed.updated_at].sort().at(-1),
          leaders: { open, closed, all: open.updated_at > closed.updated_at ? open : closed },
        })),
      });
    const values = {
      open: [...open, members[1][0]],
      closed: [...closed, members[0][1]],
      all: [...open, ...closed, members[0][1], members[1][0]],
    };
    const expected = {
      open: [5, -286, 99, -287, 101],
      closed: [6, -286, 98, -287, 102],
      all: [6, 5, -286, 99, 98, -287, 102, 101],
    };
    const activity = {};
    for (const [filter, rows] of Object.entries(values)) {
      rows.sort((a, b) => b.updated_at.localeCompare(a.updated_at) || b.number - a.number);
      const window = {
        ...lists.current.body,
        list: filter,
        fetched: rows.length,
        rows,
        next_after: rows.at(-1).number,
      };
      const story = mount({ filter, window });
      story.controller.setStacks(snapshot(members));
      await story.controller.start({ shown: true });
      const top = () =>
        story
          .model()
          .stacks.rows.filter((row) => row.level === 1)
          .map((row) => row.key);
      assert.deepEqual(top(), expected[filter]);
      const initial = top().map(rowName);
      // Only the stack projection knows the newest change in this scenario.
      story.controller.setStacks(
        snapshot([members[0], [members[1][0], pull(13, "13:30", "closed")]]),
      );
      assert.deepEqual(top(), [-287, ...expected[filter].filter((number) => number !== -287)]);
      activity[filter] = { initial, "after the closed member is updated": top().map(rowName) };
      story.controller.dispose();
    }
    // Both stacks rank inside the Open window, and share its newest off-window member.
    const shared = pull(14, "10:00", "open");
    const alternate = pull(15, "09:30", "open");
    const grouped = snapshot([
      [shared, pull(16, "12:45", "closed")],
      [alternate, pull(17, "12:15", "closed")],
    ]);
    const [first, second] = grouped.stacks;
    second.pulls.unshift(shared.number);
    const story = mount({
      filter: "open",
      window: {
        ...lists.current.body,
        list: "open",
        fetched: open.length,
        rows: open,
        next_after: 101,
      },
    });
    story.controller.setStacks(createStackIndex({ ...template, stacks: [first, second] }));
    await story.controller.start({ shown: true });
    const groups = story
      .model()
      .stacks.rows.filter((row) => row.kind === "stack")
      .map((row) => ({ stack: row.stack.number, members: row.members }));
    assert.deepEqual(groups, [
      { stack: 286, members: [14] },
      { stack: 287, members: [15] },
    ]);
    activity["overlapping stacks in a partial Open window"] = groups;
    story.controller.dispose();
    process.stdout.write(`${JSON.stringify(activity, null, 2)}\n`);
    return;
  }

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
  record(
    "stacks known: Stack #286 among the pull requests, top of the stack first",
    story,
    current,
    {
      tabStop: story.anchor(),
    },
  );

  // ── Keys: a stack's row is a stop of its own, as a folder's is, and its Whole stack row
  // is a row that opens the stack's page, as a pull request's row opens its own.
  story.controller.focused(-286);
  for (const name of ["J", "J", "J", "J", "J", "K"]) {
    await story.key(name);
  }
  // The last open, #6, reads ahead its neighbours as drawn, #7 above it and #106 below, and
  // the top: the stack's pull requests first, its Whole stack row and a stack's row passed
  // over.
  const ahead = story.log.prefetch.at(-1);
  story.log.prefetch.length = 0;
  record(
    "J walks into the stack, onto its Whole stack row first, which opens the stack's page, then its pull requests and out, and K steps back; the stack's row opens nothing",
    story,
    current,
    { "read ahead after the last open": ahead?.records ?? null },
  );
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
  record(
    "Right again goes to its first row, Whole stack, which opens the stack's page",
    story,
    current,
  );
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
  // The stack's own page (`/stack/<n>`): its Whole stack row is the current row, and an
  // address that names the page opens a stack the reader closed, as one naming a member does.
  await story.key("Left");
  await story.key("Left");
  story.controller.setCurrent(null, { stack: 286 });
  record(
    "the reader closes the stack; an address that names its page opens it and marks its Whole stack row",
    story,
    current,
    {
      closed: story.controller.snapshot().closedStacks,
      current: rowName(story.marked()),
      tabStop: rowName(story.anchor()),
    },
  );
  await story.key("Left");
  record("Left on the Whole stack row goes to its stack's row", story, current, {
    tabStop: rowName(story.anchor()),
  });
  story.controller.focused(wholeStackRowKey(286));
  await story.key("Right");
  await story.key("Enter");
  record(
    "Right on the Whole stack row does nothing; Enter opens the stack's page",
    story,
    current,
    { current: rowName(story.marked()) },
  );
  story.controller.setCurrent(7);
  record("an address that names #7 again takes the mark back", story, current, {
    current: rowName(story.marked()),
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
    "#8 in two stacks: once, under the most recently updated stack, its badge naming the other",
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
  // ── A stack's page named before the list knows the stacks: its Whole stack row is marked
  // and revealed once the stacks arrive and draw it, as a pull request's row is revealed once
  // the list holds it.
  const early = mount();
  await early.controller.start({ shown: true });
  await settle();
  early.log.revealed.length = 0;
  early.controller.setCurrent(null, { stack: 286 });
  const revealedFlat = early.log.revealed.splice(0).map(rowName);
  early.controller.setStacks(current);
  record(
    "an address of Stack #286's page before the stacks are known: its row is revealed when they draw it",
    early,
    current,
    {
      "revealed while flat": revealedFlat,
      "revealed once grouped": early.log.revealed.splice(0).map(rowName),
      current: rowName(early.marked()),
      tabStop: rowName(early.anchor()),
    },
  );
  early.controller.setStacks(index("absent"));
  early.controller.setStacks(current);
  record("stacks read again: the row is not revealed again", early, current, {
    revealed: early.log.revealed.splice(0).map(rowName),
  });

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
    removeEventListener(type, listener) {
      if (listeners.get(type) === listener) {
        listeners.delete(type);
      }
    },
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
    menus: require("./sdk-ref-fixture.js").refHelpers(document).menus,
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
  // bold place, the muted dot, the title, and the number at the line's end, as a Pulls row
  // shows it (mb-1kzu); and the parts the line is made of, one layout for every member, the
  // current one too.
  const elements = (node) => node.childNodes.filter((child) => child instanceof FakeElement);
  const memberLines = links.map((link) => {
    const [icon, copy] = elements(link);
    const text = copy.childNodes
      .map((child) => (typeof child === "string" ? child : child.textContent))
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
