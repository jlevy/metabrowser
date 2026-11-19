// Browserless session: each Pulls row's third line, its brief change line (mb-d0a3), which
// carries the chevron for its changed files (mb-h0ml), and the keys that reach it (mb-1l4i),
// through the production code.
//
// builtin_plugins/github/row-lines.js decides what a row's third line shows: the shell's
// pending placeholder while the line is read or the row's list is being listed, the line once
// it is, and nothing where its list is not cached and nothing lists it. The line is what the
// row's own cached list of changed files sums to, which the server answers for every row the
// list draws in one request (`GET pull-files-summary`). Its answers are the server's: the
// summaries in tests/fixtures/github-pull-files-summary-responses.json, which
// tests/test_github_pull_files_summary.py records from the real route, and the list the
// panel session replays.
//
// `lane` drives the lane alone over those answers, with the browser's idle time and its clock
// in the session's hands, and prints what each row shows at each step and what was asked.
// `row` mounts the production panel over a stand-in for the DOM with the SDK's own painters
// (tests/dom/sdk-ref-fixture.js) and prints each row's third line in its three states. `tree`
// goes on in that panel and prints what a press and each key do on a pull request, one item
// of three lines (mb-1z7j): a press on its title or number's line opens it and expands
// nothing, a press anywhere on its change line toggles its files, Up and Down walk whole
// items and expand nothing, Space toggles the files, Right opens them, Left closes them, and
// Enter opens the pull request. `focus` goes on from there: every key acts on the item with
// focus, even after a poll has moved the list's Tab stop to the current pull request.
// `invariants` are the relations every step holds.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { FakeElement, FakeNode } = require("./pulls-test-dom.js");

const root = path.resolve(__dirname, "../..");
const GITHUB = path.join(root, "src/metabrowser/builtin_plugins/github");
const summaries = require("../fixtures/github-pull-files-summary-responses.json");
const lists = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/github-pulls-panel-responses.json"), "utf8"),
);
// The recording holds each distinct window of rows once; `same_as` names the answer that has it.
const rowsOf = (rows) =>
  Array.isArray(rows)
    ? rows.map((row) => JSON.parse(row))
    : [rows.same_as].flat().flatMap((holder) => rowsOf(lists[holder].body.rows));
const listed = { ...lists.current.body, rows: rowsOf(lists.current.body.rows) };
const SOURCE = summaries.summed.body.source;
const ROUTE = "/api/plugin/github/pull-files-summary";

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/** The recorded rows by number, of one or more recorded answers, the later ones winning. */
function recordedRows(...names) {
  const rows = new Map();
  for (const name of names) {
    for (const row of summaries[name].body.rows) {
      rows.set(row.number, row);
    }
  }
  return rows;
}

/**
 * The server's answer for *numbers* from *rows*: a number the recording does not name is the
 * recording's own row of a pull request with nothing cached, under its number.
 */
function answerFor(rows, numbers) {
  const nothing = summaries.summed.body.rows.find((row) => row.reason === "not_cached");
  return {
    status: 200,
    body: {
      source: SOURCE,
      rows: numbers.map((number) => rows.get(number) ?? { ...nothing, number }),
    },
  };
}

/** What a row shows, in words: its line's sums, or its phase. */
function shown(line) {
  if (line.phase !== "shown") {
    return line.phase;
  }
  const { summary } = line;
  const statuses = summary.statuses.map((entry) => `${entry.count} ${entry.status}`).join(", ");
  const files = `${summary.files} ${summary.files === 1 ? "file" : "files"}`;
  return `shown ${files}: ${statuses}; +${summary.additions} −${summary.deletions}`;
}

/**
 * The lane alone: the browser's idle callbacks queued for the session to run, its clock the
 * session's, and every request it sends logged.
 */
async function laneStory(lines, prefetch) {
  const { createRowLines, createRowLineIndex, ROW_LINE_RETRY_MS } = lines;
  const keep = prefetch.createComparisonKeep({ later: (callback) => callback() });
  const index = createRowLineIndex();
  let now = 1_000_000;
  /** @type {(() => void)[]} */
  let idle = [];
  const asked = [];
  let answers = (numbers) => answerFor(recordedRows("summed"), numbers);
  const repaints = [];
  const deps = () => ({
    keep,
    index,
    async read(numbers) {
      asked.push(`GET ${ROUTE}?numbers=${numbers.join(",")}`);
      const answer = answers(numbers);
      if (answer instanceof Error) {
        throw answer;
      }
      return answer;
    },
    schedule(callback) {
      idle.push(callback);
      return callback;
    },
    cancel(handle) {
      idle = idle.filter((callback) => callback !== handle);
    },
    isVisible: () => true,
    now: () => now,
    changed: (numbers) => repaints.push(numbers === null ? "every row" : numbers.join(",")),
  });
  let rows = [
    { number: 106, head: "1".repeat(40) },
    { number: 105, head: "2".repeat(40) },
    { number: 104, head: "3".repeat(40) },
    { number: 103, head: "4".repeat(40) },
  ];
  let lane = createRowLines(deps());
  const steps = [];
  const runIdle = async () => {
    while (idle.length > 0) {
      idle.shift()();
      await settle();
    }
  };
  const shows = () =>
    Object.fromEntries(rows.map((row) => [`#${row.number}`, shown(lane.line(row))]));
  const step = async (what, act) => {
    asked.length = 0;
    repaints.length = 0;
    await act();
    const state = lane.snapshot();
    steps.push({
      step: what,
      shows: shows(),
      asked: [...asked],
      ...(repaints.length > 0 ? { repainted: [...repaints] } : {}),
      lane: {
        wanted: state.wanted,
        running: state.running,
        awaiting: state.awaiting,
        refusedAll: state.refusedAll,
      },
    });
  };

  await step("the list draws #106 to #103: each row waits, and nothing is read yet", () =>
    lane.want(rows, SOURCE),
  );
  assert.equal(idle.length, 1, "one read waits for idle");
  await step(
    "the browser is idle: one read for all four; #106 and #105 are summed, #104 has no list, and #103's is still filling",
    runIdle,
  );
  assert.deepEqual(asked, [`GET ${ROUTE}?numbers=106,105,104,103`], "one read for all four");
  await step("drawn again: each line in the paint that draws it, and nothing is read", () =>
    lane.want(rows, SOURCE),
  );
  assert.equal(idle.length, 0);
  // A Pulls tab mounted again in the document: its lane shares the document's index.
  lane.dispose();
  lane = createRowLines(deps());
  await step("a Pulls tab mounted again: the lines at once, from the document's index", () =>
    lane.want(rows, SOURCE),
  );
  assert.equal(idle.length, 0, "a remount reads nothing");
  // The panel's prefetch asked the server's lane to list #104's and #103's files, and the lane
  // took the ask (a 202): both wait for their lists in the placeholder.
  await step("the prefetch lane takes the ask to list #104's and #103's files: both wait", () =>
    lane.listing([104, 103]),
  );
  assert.equal(idle.length, 0, "waiting for the lane reads nothing");
  answers = (numbers) => answerFor(recordedRows("summed", "relisted"), numbers);
  await step(
    "the lane's report says it listed them: both are read again in one request, and both are shown",
    async () => {
      lane.listed([104, 103]);
      await runIdle();
    },
  );
  await step("#106 is pushed, its head moves: it is read again, its line shown meanwhile", () => {
    rows = rows.map((row) => (row.number === 106 ? { ...row, head: "5".repeat(40) } : row));
    lane.want(rows, SOURCE);
  });
  await step("and once read, shown again", runIdle);
  await step("#105's tree reads a list of another refresh: its line is read again", async () => {
    lane.heard(105, "f".repeat(32));
    await runIdle();
  });
  const generation = summaries.summed.body.rows.find((row) => row.number === 105).generation;
  await step("its tree reads the same refresh's list: nothing is read", async () => {
    lane.heard(105, generation);
    await runIdle();
  });
  // A row whose list another refresh is listing, one this tab did not ask for.
  index.clear();
  answers = (numbers) => answerFor(recordedRows("summed", "listing"), numbers);
  await step(
    "a row whose list another's refresh is listing waits for it, and nothing more is read",
    async () => {
      lane.want(rows, SOURCE);
      await runIdle();
      lane.want(rows, SOURCE);
      await runIdle();
    },
  );
  now += ROW_LINE_RETRY_MS;
  answers = (numbers) => answerFor(recordedRows("summed"), numbers);
  await step("a minute on, it is asked again: no list, so no line and no placeholder", async () => {
    lane.want(rows, SOURCE);
    await runIdle();
  });
  // A read that fails keeps what each row had, and is asked again a minute on.
  index.clear();
  answers = () => ({ status: 500, body: { error: "boom" } });
  await step("the read fails: no line and no placeholder", async () => {
    lane.want(rows, SOURCE);
    await runIdle();
  });
  now += ROW_LINE_RETRY_MS;
  answers = (numbers) => answerFor(recordedRows("summed"), numbers);
  await step("a minute on, the failed read is asked again", async () => {
    lane.want(rows, SOURCE);
    await runIdle();
  });
  // A request with no room left for a list defers it, which says nothing of the list: the
  // line the row had stays shown until the next request reads it.
  await step("#106 is pushed again: its line stays shown while it is read again", () => {
    rows = rows.map((row) => (row.number === 106 ? { ...row, head: "6".repeat(40) } : row));
    lane.want(rows, SOURCE);
  });
  answers = (numbers) => answerFor(recordedRows("summed", "deferred"), numbers);
  await step(
    "the request had no room for #106's list (deferred): its line stays, and the next request reads it",
    async () => {
      idle.shift()();
      await settle();
    },
  );
  assert.equal(shows()["#106"].startsWith("shown"), true, "a deferral keeps the line");
  answers = (numbers) => answerFor(recordedRows("summed"), numbers);
  await step("the next request reads it: shown", runIdle);
  // The prefetch lane took the ask for #104's files, and then the panel stopped following
  // the lane, hidden or offline, before its report said the lane was done.
  await step("the lane takes the ask for #104's files: it waits", () => lane.listing([104]));
  await step("the panel stops following the lane: nothing more is read", async () => {
    lane.want(rows, SOURCE);
    await runIdle();
  });
  assert.equal(shows()["#104"], "waiting");
  now += ROW_LINE_RETRY_MS;
  await step(
    "a minute on, #104 is read again and leaves the placeholder: its list is not cached",
    async () => {
      lane.want(rows, SOURCE);
      await runIdle();
    },
  );
  assert.equal(shows()["#104"], "none", "a wait for the lane ends a minute on");
  // An answer that sums to nothing, a list still filling or too large to sum, names its
  // list's refresh, so the row's tree reading that same list reads nothing more.
  index.clear();
  await step("read again from nothing: #103's list is still filling", async () => {
    lane.want(rows, SOURCE);
    await runIdle();
  });
  const filling = summaries.summed.body.rows.find((row) => row.number === 103).generation;
  await step("#103's tree reads that refresh's list: nothing more is read", async () => {
    lane.heard(103, filling);
    await runIdle();
  });
  assert.equal(steps.at(-1).asked.length, 0, "the same refresh's list is not read again");
  // A server that serves no GitHub repository has no row's list: one answer says so.
  index.clear();
  lane.dispose();
  lane = createRowLines(deps());
  answers = () => summaries.not_github;
  await step("a server with no repository: one answer, and no row waits", async () => {
    lane.want(rows, SOURCE);
    await runIdle();
    lane.listing([106]);
  });
  lane.dispose();
  return steps;
}

/**
 * Mount the production panel over a stand-in for the DOM on the recorded All list, with the
 * SDK's own painters and idle time in the session's hands, and print each row's third line
 * at each step, then what a press and each key do.
 */
async function rowStory(lines) {
  const panel = await import(pathToFileURL(path.join(GITHUB, "pulls-panel.js")).href);
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
  const respond = (body, status = 200) =>
    Promise.resolve({ status, headers: { get: () => null }, json: async () => body });
  const requests = [];
  const opened = [];
  // The panel's timers, kept and never run on their own, each with where it was set: the
  // story fires the list's next poll when it says (`firePoll`), as the poll's delay ending
  // would. A tree of changed files polls its own list too, so a timer is told by the stack
  // that set it, the list's `scheduleNext` in pulls-panel.js.
  const timers = [];
  const globals = {
    document,
    window: {
      addEventListener() {},
      setTimeout: (callback) => {
        timers.push({ callback, from: new Error().stack ?? "" });
        return 0;
      },
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
      if (route.startsWith(`${ROUTE}?`)) {
        requests.push(route);
        const numbers = new URL(route, "http://x").searchParams.get("numbers").split(",");
        const answer = answerFor(recordedRows("summed"), numbers.map(Number));
        return respond(answer.body, answer.status);
      }
      if (route.startsWith("/api/plugin/github/pull-files?")) {
        // A row's tree reads its list when it opens; this story reads none of its rows.
        requests.push(route);
        return respond(null, 404);
      }
      if (route.startsWith("/api/plugin/github/pulls?")) {
        return respond(listed);
      }
      if (route === "/api/plugin/github/pulls-prefetch") {
        return respond({ prefetch: "not_due" });
      }
      // The stacks, a refresh, or a record: nothing this story reads.
      return respond(null, 404);
    },
  };
  const saved = {};
  for (const [name, value] of Object.entries(globals)) {
    saved[name] = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, { value, configurable: true, writable: true });
  }
  /** @type {(() => void)[]} */
  let idle = [];
  const paint = async () => {
    await settle();
    for (const frame of frames.splice(0)) {
      frame();
    }
    await settle();
  };
  const restore = () => {
    for (const [name, descriptor] of Object.entries(saved)) {
      if (descriptor === undefined) {
        delete globalThis[name];
      } else {
        Object.defineProperty(globalThis, name, descriptor);
      }
    }
  };
  try {
    const container = new PanelElement("div");
    const sdk = require("./sdk-ref-fixture.js").refHelpers(document);
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
          open: (route) => opened.push(`#${route.number}`),
          file: null,
          fileHref: (number, file) => `/pull/${number}/files/${file}`,
          pageFor: () => null,
          onPageChange: () => () => {},
          filterChanged() {},
        },
      },
      {
        ...sdk,
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
        whenIdle(callback) {
          idle.push(callback);
          return () => {
            idle = idle.filter((queued) => queued !== callback);
          };
        },
      },
    );
    const list = container.childNodes.find((node) => node.classList?.contains("github-pulls-list"));
    const SHOWN = [106, 105, 104, 103];
    const item = (number) =>
      list.childNodes.find(
        (node) =>
          node.classList?.contains("github-pulls-item") && node.dataset.number === String(number),
      );
    const childByClass = (node, name) =>
      node.childNodes.find((child) => child.classList?.contains(name));
    // The item's three lines are one zone (`.github-pulls-entry`, mb-1z7j): the link, the
    // row of the tree, and under it the change line, which carries the toggle.
    const zoneOf = (number) => childByClass(item(number), "github-pulls-entry");
    const rowOf = (number) => zoneOf(number).childNodes[0];
    const changeOf = (number) => childByClass(zoneOf(number), "github-pulls-change");
    const lineOf = (number) => childByClass(changeOf(number), "github-pulls-change-line");
    // The line's words, hidden, which describe the row (`aria-describedby`).
    const wordsOf = (number) => childByClass(changeOf(number), "github-pulls-change-words");
    /** Which way the line's chevron points: `.expanded` or `.collapsed`. */
    const turnOf = (number) =>
      changeOf(number).classList.contains("expanded") ? "expanded" : "collapsed";
    /** Nodes as data: text as its string, an element its class, attributes, and content. */
    const shape = (nodes) =>
      nodes.map((node) =>
        node.data !== undefined
          ? node.data
          : {
              class: node.className,
              ...Object.fromEntries(
                ["aria-hidden", "data-file-status"]
                  .filter((name) => node.getAttribute(name) !== null)
                  .map((name) => [name, node.getAttribute(name)]),
              ),
              ...(node.childNodes.length === 0 ? {} : { children: shape(node.childNodes) }),
            },
      );
    const textOf = (node) =>
      node.data !== undefined ? node.data : node.childNodes.map(textOf).join("");
    /** Each row's third line as drawn: its parts, its text, and its item's name and state,
     * and #106's line part for part. */
    const thirdLines = () =>
      Object.fromEntries(
        SHOWN.map((number) => {
          const change = changeOf(number);
          return [
            `#${number}`,
            {
              parts: change.childNodes.map((node) => node.className),
              text: textOf(lineOf(number)),
              ...(number === 106 ? { line: shape(lineOf(number).childNodes) } : {}),
              words: textOf(wordsOf(number)),
              chevron: turnOf(number),
            },
          ];
        }),
      );
    /** One element as drawn: its name, role, level, place, expansion, what it owns, describes,
     * or controls, whether it is a stop of the tree's, and focus. */
    const said = (element, name) => {
      const attribute = (label, attr) =>
        element.getAttribute(attr) === null ? null : `${label} ${element.getAttribute(attr)}`;
      const tabindex = element.getAttribute("tabindex");
      return [
        name,
        element.getAttribute("role"),
        attribute("level", "aria-level"),
        element.getAttribute("aria-posinset") === null
          ? null
          : `${element.getAttribute("aria-posinset")}/${element.getAttribute("aria-setsize")}`,
        `expanded ${element.getAttribute("aria-expanded")}`,
        attribute("owns", "aria-owns"),
        attribute("described by", "aria-describedby"),
        attribute("controls", "aria-controls"),
        tabindex === "0" ? "Tab stop" : tabindex === null ? "no stop" : null,
        document.activeElement === element ? "focused" : null,
      ]
        .filter(Boolean)
        .join(" · ");
    };
    /** The line under a row: hidden from assistive technology or not, which way its chevron
     * points, whether it is a stop of the tree's, and focus. */
    const saidLine = (number) => {
      const line = changeOf(number);
      return [
        `  #${number}'s change line`,
        line.getAttribute("aria-hidden") === "true" ? "hidden" : "exposed",
        line.getAttribute("role"),
        `chevron ${turnOf(number)}`,
        line.getAttribute("tabindex") === null ? "no stop" : "a stop",
        document.activeElement === line ? "focused" : null,
      ]
        .filter(Boolean)
        .join(" · ");
    };
    /** The tree as drawn for the four rows: each item's row, then the line under it that
     * carries its toggle. */
    const tree = () =>
      SHOWN.flatMap((number) => [said(rowOf(number), `#${number}`), saidLine(number)]);
    const runIdle = async () => {
      while (idle.length > 0) {
        idle.shift()();
        await paint();
      }
    };
    const steps = [];
    await paint();
    steps.push({
      step: "mounted: each row's third line holds the pending placeholder; the browser is not idle yet",
      lines: thirdLines(),
      requests: requests.splice(0),
    });
    // The placeholder, the chevron, and the change line are the nodes the arrival keeps.
    const changeBefore = changeOf(106);
    const toggleBefore = childByClass(changeBefore, "github-pulls-toggle");
    const pendingBefore = lineOf(106).childNodes[0];
    await paint();
    assert.equal(
      lineOf(106).childNodes[0],
      pendingBefore,
      "the placeholder is one node across paints, so its quiet period and pulse run once",
    );
    await runIdle();
    const arrived = thirdLines();
    steps.push({
      step: "idle: one read for the rows drawn; #106's and #105's lines arrive, and #104 and #103 have none",
      lines: arrived,
      requests: requests.splice(0).map((route) => `${route.split("&")[0].slice(0, 80)}…`),
    });
    assert.equal(changeOf(106), changeBefore, "the change line stays");
    assert.equal(childByClass(changeOf(106), "github-pulls-toggle"), toggleBefore);
    // The line is the shell's one component, through the SDK: the same nodes, part for part.
    const { rowLineInput } = lines;
    const tree106 = await sdk.loadChangedFilesTree();
    const summary106 = summaries.summed.body.rows.find((row) => row.number === 106);
    const said106 = sdk.changeLine(rowLineInput(summary106, tree106.statusBreakdown));
    assert.deepEqual(
      arrived["#106"].line,
      // Spread into this realm's array: the SDK's own is its sandbox's.
      shape([...sdk.changeLineNodes(said106)]),
      "the row draws the component",
    );
    assert.equal(arrived["#106"].words, `Changed files: ${said106.label}`);
    assert.equal(
      rowOf(106).getAttribute("aria-describedby"),
      wordsOf(106).getAttribute("id"),
      "the row is described by its line's words",
    );
    // No file total: the brief line alone (its spaces between items are the layout's gap).
    assert.equal(arrived["#106"].text.replace(/\s/g, ""), said106.text.replace(/\s/g, ""));
    assert.ok(!/file/.test(arrived["#106"].text), "the line names no file total");
    // Collapsed by default, and nothing opens on its own.
    steps.push({
      step: "the collapsed default: no row's files are open, and no list was read",
      tree: tree(),
      requests: requests.splice(0),
    });
    const keyStep = (what, act, pressed) => {
      const handled = act();
      return paint().then(() => {
        steps.push({
          step: what,
          ...(pressed === undefined ? {} : { pressed }),
          ...(handled === undefined ? {} : { handled }),
          tree: tree(),
          ...(opened.length > 0 ? { opened: opened.splice(0) } : {}),
          ...(requests.length > 0 ? { requests: requests.splice(0) } : {}),
        });
      });
    };
    /** A plain press on *target*, a part of #*number*'s item named *part*. */
    const press = (what, number, part, target) =>
      keyStep(what, () => list.listeners.get("click")({ target, button: 0, preventDefault() {} }), {
        item: number,
        on: part,
      });
    // The item's other lines, which include no toggle of their own: a press opens the pull
    // request and expands nothing (docs/design-system.md, "A Click on the Toggle's Line
    // Toggles").
    await press(
      "a press on #106's title opens it, and its files stay closed",
      106,
      "title",
      childByClass(rowOf(106), "github-pulls-title"),
    );
    await press(
      "a press on #105's number's line opens it, and its files stay closed",
      105,
      "number's line",
      childByClass(rowOf(105), "github-pulls-meta"),
    );
    await press(
      "a press on #106's state icon opens it again, and its files stay closed",
      106,
      "state icon",
      rowOf(106).childNodes[0],
    );
    assert.equal(rowOf(106).getAttribute("aria-expanded"), "false");
    // The line that carries the toggle, anywhere on it: a press toggles, opens no page, and
    // leaves the focus on the item, the tree's one stop, so Space and the arrows go on from it.
    await press(
      "a press on #106's chevron opens its files, opens no page, and focuses its item",
      106,
      "chevron",
      childByClass(changeOf(106), "github-pulls-toggle"),
    );
    assert.equal(turnOf(106), "expanded");
    assert.equal(rowOf(106).getAttribute("aria-expanded"), "true");
    assert.equal(document.activeElement, rowOf(106), "the item takes the focus, not its line");
    await press(
      "a press on the values of its change line closes them: the whole line carries the toggle",
      106,
      "change line",
      lineOf(106),
    );
    await press(
      "a press on the change line itself, past its values, opens them again",
      106,
      "change line",
      changeOf(106),
    );
    await press("and closes them", 106, "change line", changeOf(106));
    rowOf(106).focus();
    list.listeners.get("focusin")({ target: rowOf(106) });
    await keyStep("Down walks to #105, a whole item, which opens and expands nothing", () =>
      handle.move(1),
    );
    await keyStep("Down again to #104: nothing expands", () => handle.move(1));
    await keyStep("Up back to #105", () => handle.move(-1));
    await keyStep(
      "Space on #105 (the handle's toggleFiles) opens its files in place, and keeps the focus",
      () => handle.toggleFiles(105),
    );
    await keyStep("Space again closes them", () => handle.toggleFiles(105));
    await keyStep("Enter opens #105 again, and expands nothing", () => handle.activateAnchor());
    await keyStep("Right opens #105's files, as on a folder", () => handle.expand());
    await keyStep(
      "Right again, its files not yet listed, has no file to go to: the focus stays",
      () => handle.expand(),
    );
    await keyStep(
      "Down from #105, its files open, goes on to #104, a whole item: the files are Right's",
      () => handle.move(1),
    );
    await keyStep("Up back to #105, its files still open", () => handle.move(-1));
    await keyStep("Left closes #105's files, as on a folder", () => handle.collapse());
    await keyStep(
      "Left again, on a pull request in no stack, goes nowhere, and is the list's",
      () => handle.collapse(),
    );
    // A press on #103's change line focuses #103, whose page is not the one open. A poll then
    // settles the list's anchor, its Tab stop, on #105, the current pull request, and leaves
    // focus on #103; each key still acts on #103, the item with focus (mb-1z7j).
    const focusFrom = steps.length;
    const firePoll = () => {
      const poll = timers.filter(({ from }) => /scheduleNext .*pulls-panel\.js/.test(from)).at(-1);
      assert.ok(poll !== undefined, "the list has a poll waiting");
      timers.length = 0;
      poll.callback();
    };
    const drifted = (step) =>
      step.tree.some((line) => /^#105 .*· Tab stop/.test(line)) &&
      step.tree.some((line) => /^#103 .*· focused$/.test(line));
    await press(
      "a press on #103's change line opens its files and focuses #103, while #105's page is open",
      103,
      "change line",
      lineOf(103),
    );
    await keyStep("a poll: the Tab stop goes back to #105, and focus stays on #103", firePoll);
    assert.ok(drifted(steps.at(-1)), "the poll moves the Tab stop and leaves the focus");
    await keyStep("Left closes #103's files: the item with focus, not the Tab stop", () =>
      handle.collapse(),
    );
    assert.equal(rowOf(103).getAttribute("aria-expanded"), "false", "Left closes #103's files");
    assert.equal(rowOf(105).getAttribute("aria-expanded"), "false", "and leaves #105's");
    await keyStep("a poll again: the Tab stop goes back to #105", firePoll);
    assert.ok(drifted(steps.at(-1)), "the poll moves the Tab stop again");
    await keyStep("Right opens #103's files again", () => handle.expand());
    assert.equal(rowOf(103).getAttribute("aria-expanded"), "true", "Right opens #103's files");
    assert.equal(rowOf(105).getAttribute("aria-expanded"), "false", "and not #105's");
    await keyStep("a poll again", firePoll);
    assert.ok(drifted(steps.at(-1)), "and again");
    await keyStep("Enter opens #103, the item with focus", () => handle.activateAnchor());
    assert.deepEqual(steps.at(-1).opened, ["#103"], "Enter opens the focused item");
    await keyStep("Tab reaches #103's row, and Enter opens it: nothing expands", () => {
      rowOf(103).focus();
      list.listeners.get("focusin")({ target: rowOf(103) });
      return handle.activateAnchor();
    });
    handle.dispose();
    restore();
    return { steps, focusFrom, said: { text: said106.text, label: said106.label } };
  } catch (error) {
    restore();
    throw error;
  }
}

(async () => {
  const lines = await import(pathToFileURL(path.join(GITHUB, "row-lines.js")).href);
  const prefetch = await import(pathToFileURL(path.join(GITHUB, "comparison-prefetch.js")).href);
  const lane = await laneStory(lines, prefetch);
  // Every step: a row waits only while a read of it is coming, or its list is being listed.
  for (const step of lane) {
    for (const [row, phase] of Object.entries(step.shows)) {
      if (phase === "waiting") {
        const number = Number(row.slice(1));
        assert.ok(
          step.lane.wanted.includes(number) ||
            step.lane.running?.includes(number) ||
            step.lane.awaiting.includes(number) ||
            step.step.includes("listing"),
          `${step.step}: ${row} waits for a read or a listing that is coming`,
        );
      }
    }
  }
  const row = await rowStory(lines);
  // Every step of the row story holds the item's one zone (mb-1z7j) and the rule for a row
  // with a disclosure toggle (docs/design-system.md, "A Click on the Toggle's Line Toggles"):
  // a press on the line that carries the toggle toggles that item's files, and a press on the
  // larger item that includes it toggles nothing. Only those presses and Space, Right, and
  // Left change what is open; a walk, Enter, Tab, or a line's arrival opens nothing.
  const expansionOf = (tree) =>
    Object.fromEntries(
      tree.flatMap((line) => {
        const found = /^#(\d+) · .* · expanded (\w+)/.exec(line);
        return found === null ? [] : [[found[1], found[2]]];
      }),
    );
  let before = null;
  for (const step of row.steps) {
    if (step.tree === undefined) {
      continue;
    }
    const now = expansionOf(step.tree);
    for (const [at, line] of step.tree.entries()) {
      if (line.startsWith("  ")) {
        // The line under each item turns its chevron with the item's one state, is hidden
        // from assistive technology with no role, so the tree holds only its items and their
        // groups, and is never a stop of its own.
        const number = /#(\d+)/.exec(line)[1];
        const turn = now[number] === "true" ? "expanded" : "collapsed";
        assert.ok(line.includes(`· chevron ${turn}`), `${step.step}: ${line}`);
        assert.ok(
          line.includes("· hidden · chevron") && line.endsWith("no stop"),
          `${step.step}: ${line}`,
        );
      } else {
        assert.ok(step.tree[at + 1].startsWith("  "), "each item's row has its line under it");
      }
    }
    if (before !== null) {
      const changed = Object.keys(now).filter((number) => now[number] !== before[number]);
      if (step.pressed !== undefined) {
        const onToggle = ["chevron", "change line"].includes(step.pressed.on);
        assert.deepEqual(
          changed,
          onToggle ? [String(step.pressed.item)] : [],
          `${step.step}: a press on the toggle's line toggles, and on the item's other lines does not`,
        );
        if (onToggle) {
          assert.equal(step.opened, undefined, `${step.step}: the toggle's line opens no page`);
        }
      } else if (/^(Space|Right|Left)\b/.test(step.step)) {
        // A key toggles at most the item with focus.
        const focusedItem = step.tree.find((line) => / · focused$/.test(line));
        const focusedNumber = focusedItem === undefined ? null : /^#(\d+)/.exec(focusedItem)?.[1];
        assert.ok(
          changed.every((number) => number === focusedNumber),
          `${step.step}: a key acts on the item with focus`,
        );
      } else {
        assert.deepEqual(changed, [], `${step.step}: nothing opens a row's files on its own`);
      }
    }
    before = now;
  }
  const pressedParts = new Set(row.steps.flatMap((step) => step.pressed?.on ?? []));
  assert.deepEqual(
    [...pressedParts].sort(),
    ["change line", "chevron", "number's line", "state icon", "title"],
    "the story presses every part of an item",
  );
  // One part a run, so each transcript block stays one reviewable size: `lane`, `row`,
  // `tree`, or `focus`. (A block also has to stay under the size at which the transcript
  // runner's matcher, a regular expression built from the block, is too large to compile.)
  // With none, the run holds every part's invariants and says how many steps each took.
  const lineSteps = row.steps.filter((step) => "lines" in step);
  const treeSteps = row.steps.slice(lineSteps.length, row.focusFrom);
  const focusSteps = row.steps.slice(row.focusFrom);
  assert.ok(
    [...treeSteps, ...focusSteps].every((step) => !("lines" in step)),
    "the row's line steps come first",
  );
  const part = process.argv[2];
  const printed =
    part === "lane"
      ? { lane }
      : part === "row"
        ? { row: { steps: lineSteps, said: row.said } }
        : part === "tree"
          ? { tree: treeSteps }
          : part === "focus"
            ? { focus: focusSteps }
            : {
                steps: {
                  lane: lane.length,
                  row: lineSteps.length,
                  tree: treeSteps.length,
                  focus: focusSteps.length,
                },
              };
  process.stdout.write(`${JSON.stringify({ ...printed, invariants: true }, null, 2)}\n`);
})().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
