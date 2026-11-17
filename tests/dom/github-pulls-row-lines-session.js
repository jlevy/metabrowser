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
// (tests/dom/sdk-ref-fixture.js) and prints each row's third line in its three states, then
// what a press and each key do: a press on the row opens it and expands nothing, a press on
// its change line toggles its files, Up and Down walk the rows and expand nothing, Right goes
// to a row's change line, and there Enter and Space toggle its files, Left closes them and
// goes back, and Up and Down leave it. `invariants` are the relations every step holds.

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
    const rowOf = (number) => item(number).childNodes[0];
    const changeOf = (number) =>
      childByClass(item(number), "github-pulls-change-group").firstElementChild;
    const lineOf = (number) => childByClass(changeOf(number), "github-pulls-change-line");
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
              name: change.getAttribute("aria-label"),
              expanded: change.getAttribute("aria-expanded"),
            },
          ];
        }),
      );
    /** One item as drawn: its name, role, level, place, expansion, Tab stop, and focus. */
    const said = (element, name) =>
      [
        name,
        element.getAttribute("role"),
        `level ${element.getAttribute("aria-level")}`,
        `${element.getAttribute("aria-posinset")}/${element.getAttribute("aria-setsize")}`,
        `expanded ${element.getAttribute("aria-expanded")}`,
        element.getAttribute("aria-owns") === null
          ? null
          : `owns ${element.getAttribute("aria-owns")}`,
        element.getAttribute("tabindex") === "0" ? "Tab stop" : null,
        document.activeElement === element ? "focused" : null,
      ]
        .filter(Boolean)
        .join(" · ");
    /** The tree as drawn for the four rows: each row, then its change line, the row's child. */
    const tree = () =>
      SHOWN.flatMap((number) => [
        said(rowOf(number), `#${number}`),
        said(changeOf(number), `  #${number}'s change line`),
      ]);
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
    assert.equal(arrived["#106"].name, `Changed files: ${said106.label}`);
    // No file total: the brief line alone (its spaces between items are the layout's gap).
    assert.equal(arrived["#106"].text.replace(/\s/g, ""), said106.text.replace(/\s/g, ""));
    assert.ok(!/file/.test(arrived["#106"].text), "the line names no file total");
    // Collapsed by default, and nothing opens on its own.
    steps.push({
      step: "the collapsed default: no row's files are open, and no list was read",
      tree: tree(),
      requests: requests.splice(0),
    });
    const keyStep = (what, act) => {
      const handled = act();
      return paint().then(() => {
        steps.push({
          step: what,
          ...(handled === undefined ? {} : { handled }),
          tree: tree(),
          ...(opened.length > 0 ? { opened: opened.splice(0) } : {}),
          ...(requests.length > 0 ? { requests: requests.splice(0) } : {}),
        });
      });
    };
    const title = childByClass(rowOf(106), "github-pulls-title");
    await keyStep("a press on #106's title opens it, and its files stay closed", () =>
      list.listeners.get("click")({ target: title, button: 0, preventDefault() {} }),
    );
    assert.equal(changeOf(106).getAttribute("aria-expanded"), "false");
    const chevron = childByClass(changeOf(106), "github-pulls-toggle");
    await keyStep("a press on its chevron opens its files, and opens no page", () => {
      chevron.focus();
      list.listeners.get("click")({ target: chevron, button: 0, preventDefault() {} });
    });
    assert.equal(changeOf(106).getAttribute("aria-expanded"), "true");
    await keyStep("a press on its change line closes them", () =>
      list.listeners.get("click")({ target: lineOf(106), button: 0, preventDefault() {} }),
    );
    rowOf(106).focus();
    list.listeners.get("focusin")({ target: rowOf(106) });
    await keyStep("Down walks to #105, which opens, and expands nothing", () => handle.move(1));
    await keyStep("Down again to #104: nothing expands", () => handle.move(1));
    await keyStep("Up back to #105", () => handle.move(-1));
    await keyStep("Right on #105 goes to its change line, and opens nothing", () =>
      handle.expand(),
    );
    await keyStep("Enter on the change line opens its files", () => handle.activateAnchor());
    await keyStep("Enter again closes them", () => handle.activateAnchor());
    await keyStep("Space on it (the handle's toggleFiles) opens them", () =>
      handle.toggleFiles(105),
    );
    await keyStep("Left closes them, and keeps the change line", () => handle.collapse());
    await keyStep("Right opens them again", () => handle.expand());
    await keyStep(
      "Down from the open change line, its files not yet listed, goes on to #104, which opens",
      () => handle.move(1),
    );
    await keyStep("Up back to #105, which opens", () => handle.move(-1));
    await keyStep("Right to its change line, then Left: its files close", () => {
      handle.expand();
      return handle.collapse();
    });
    await keyStep("Left again goes back to #105's row", () => handle.collapse());
    await keyStep("Right, then Up from the change line: back to #105's row", () => {
      handle.expand();
      return handle.move(-1);
    });
    await keyStep("Right, then Down from its closed change line: on to #104, which opens", () => {
      handle.expand();
      return handle.move(1);
    });
    await keyStep("Tab reaches #103's row, and Enter opens it: nothing expands", () => {
      rowOf(103).focus();
      list.listeners.get("focusin")({ target: rowOf(103) });
      return handle.activateAnchor();
    });
    handle.dispose();
    restore();
    return { steps, said: { text: said106.text, label: said106.label } };
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
  // No step of the row story expands a row's files but a press on its change line, Enter or
  // Space on it, or Right from it.
  for (const step of row.steps) {
    const opens = /chevron|Enter on the change line|Space on it|Right opens/.test(step.step);
    if (!opens && step.tree !== undefined) {
      const before = row.steps[row.steps.indexOf(step) - 1]?.tree ?? [];
      for (const [at, line] of step.tree.entries()) {
        if (line.includes("change line") && line.includes("expanded true")) {
          assert.ok(
            before[at]?.includes("expanded true"),
            `${step.step}: nothing opens a row's files on its own`,
          );
        }
      }
    }
  }
  // One part a run, so each transcript block stays one reviewable size: `lane` or `row`.
  // With neither, the run holds every part's invariants and says how many steps each took.
  const part = process.argv[2];
  const printed =
    part === "lane"
      ? { lane }
      : part === "row"
        ? { row }
        : { steps: { lane: lane.length, row: row.steps.length } };
  process.stdout.write(`${JSON.stringify({ ...printed, invariants: true }, null, 2)}\n`);
})().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
