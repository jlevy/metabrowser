// Browserless session: each Pulls row's run and last line (mb-d0a3, mb-lqkb, mb-pw8t,
// mb-rb3n): the title, the place, the number, and the author, then the lines the pull request
// changes, its brief change line of its line totals alone, with the chevron for its changed
// files after them (mb-h0ml, mb-f0pz), and the age at the row's end, and the presses and keys
// that reach it (mb-1l4i), through the production code.
//
// builtin_plugins/github/row-lines.js decides what lines a row's toggle shows: the shell's
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
// (tests/dom/sdk-ref-fixture.js) and prints each row's run and last line in its three states.
// `totals` mounts it again on rows whose totals are zero or not known, and prints the lines
// they show: a total of zero is left out, and a change of no lines is "0 lines" (mb-efum). `tree`
// goes on in that panel and prints what a press and each key do on a pull request, one item
// (mb-1z7j): a press on its lines or its chevron toggles its files and opens no page, a press
// anywhere else on it, the title, the number, the author, or the age, opens it and expands
// nothing, Up and Down walk whole
// items and expand nothing, Space toggles the files, Right opens them, Left closes them, and
// Enter opens the pull request. `focus` goes on from there: every key acts on the item with
// focus, even after a poll has moved the list's Tab stop to the current pull request.
// `window` mounts it in a pane whose rows lay out shorter than `ROW_ESTIMATE_PX`, with the
// browser's frames, its resize notifications, and its idle time in the session's hands: the
// first window, placed at the estimate, draws fewer rows than the window the rows' heights
// place, and the one read of their lines names every row that window draws, whether the browser
// is idle after the frame that measured the rows or before it (mb-hb4a).
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
  // What the panel's window does when a read is about to name its rows: nothing, but where a
  // step says its rows' measures move it.
  let settleWindow = () => {};
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
    settle: () => settleWindow(),
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
  // The panel's first window is placed at `ROW_ESTIMATE_PX`, and the rows' measures move it;
  // the browser can be idle between the frame that measured them and the frame that draws the
  // window they place. The read settles the window before it names its rows, so the rows that
  // window adds are in the one read, not a second one (mb-hb4a).
  index.clear();
  settleWindow = () => {
    settleWindow = () => {};
    rows = [...rows, { number: 102, head: "7".repeat(40) }];
    lane.want(rows, SOURCE);
  };
  await step(
    "read again from nothing, the window drawing #102 too once its rows are measured: one read names all five",
    async () => {
      lane.want(rows, SOURCE);
      await runIdle();
    },
  );
  assert.deepEqual(
    steps.at(-1).asked,
    [`GET ${ROUTE}?numbers=106,105,104,103,102`],
    "one read names every row the settled window draws",
  );
  rows = rows.filter((row) => row.number !== 102);
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

/** The rows the list draws first, which each story reads. */
const SHOWN = [106, 105, 104, 103];

/**
 * Mount the production panel over a stand-in for the DOM on the recorded All list, with the
 * SDK's own painters and idle time in the session's hands, and print each row's run and last
 * line at each step, then what a press and each key do. Given *totals*, each drawn row's line
 * totals in `SHOWN`'s order, its rows are a recorded listed row with those totals, and the
 * story ends when their lines arrive, with what each shows.
 *
 * @param {{additions: number | null, deletions: number | null}[] | null} [totals]
 */
async function rowStory(lines, totals = null) {
  const panel = await import(pathToFileURL(path.join(GITHUB, "pulls-panel.js")).href);
  const rowSummaries = recordedRows("summed");
  // A comparison already has its measured size when the navigation reads its totals.
  rowSummaries.set(106, {
    ...rowSummaries.get(106),
    size: { state: "measured", pushed_bytes: 22_528, diff_bytes: 60_314 },
  });
  for (const [at, total] of (totals ?? []).entries()) {
    const number = SHOWN[at];
    // A change of no lines renames a file; any other modifies one.
    const status = total.additions === 0 && total.deletions === 0 ? "renamed" : "modified";
    rowSummaries.set(number, {
      ...rowSummaries.get(105),
      number,
      generation: String(number).padStart(32, "0"),
      statuses: [{ status, count: 1 }],
      ...total,
    });
  }
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
        const answer = answerFor(rowSummaries, numbers.map(Number));
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
        ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
          label: "1m",
          className: "age-min",
        })),
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
    const item = (number) =>
      list.childNodes.find(
        (node) =>
          node.classList?.contains("github-pulls-item") && node.dataset.number === String(number),
      );
    const childByClass = (node, name) =>
      node.childNodes.find((child) => child.classList?.contains(name));
    /** The first element under *node*, at any depth, with the class *name*. */
    const findByClass = (node, name) => {
      for (const child of node.childNodes) {
        if (child.classList?.contains(name)) {
          return child;
        }
        const found = child.childNodes === undefined ? undefined : findByClass(child, name);
        if (found !== undefined) {
          return found;
        }
      }
      return undefined;
    };
    // The item is one zone (`.github-pulls-entry`, mb-1z7j), its link, the row of the tree:
    // its run, the title, the place, the number, and the author, and its last line, its
    // toggle, the lines and the chevron after them, and the age at the row's end (mb-rb3n).
    const zoneOf = (number) => childByClass(item(number), "github-pulls-entry");
    const rowOf = (number) => zoneOf(number).childNodes[0];
    const headingOf = (number) => childByClass(rowOf(number), "github-pulls-heading");
    const tailOf = (number) => childByClass(rowOf(number), "github-pulls-tail");
    const changeOf = (number) => findByClass(rowOf(number), "github-pulls-change");
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
    /** The text *node* shows: its text but what is hidden. */
    const shownOf = (node) =>
      node.data !== undefined
        ? node.data
        : node.getAttribute("hidden") !== null
          ? ""
          : node.childNodes.map(shownOf).join("");
    /** A part of a row's run: its class, and the parts of the author. */
    const runPart = (node) =>
      node.className === "github-pulls-by"
        ? { [node.className]: node.childNodes.map(runPart) }
        : (node.className ?? node.data);
    /** Each row as drawn: its run's parts, its last line's parts, the text its run shows, the
     * lines' text, and its item's name and state, and #106's lines part for part; and what
     * the item says for its number, its author, and its age, in its link's hidden text
     * (`spoken`). */
    const rowsDrawn = () =>
      Object.fromEntries(
        SHOWN.map((number) => {
          const heading = headingOf(number);
          const copy = childByClass(heading, "github-pull-row-copy");
          const end = childByClass(copy, "github-pull-row-end");
          return [
            `#${number}`,
            {
              run: [
                ...heading.childNodes.slice(0, 2),
                ...copy.childNodes.filter((part) => part.className && part !== end),
                ...end.childNodes,
              ].map(runPart),
              last: tailOf(number).childNodes[0].childNodes.map((node) => node.className),
              end: tailOf(number).childNodes.at(-1).className,
              shown: shownOf(heading).replaceAll("\u00a0", " "),
              spoken: textOf(childByClass(rowOf(number), "sr-only")),
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
    /** A row's toggle, its lines and chevron: hidden from assistive technology or not, which
     * way its chevron points, whether it is a stop of the tree's, and focus. */
    const saidLine = (number) => {
      const line = changeOf(number);
      return [
        `  #${number}'s toggle`,
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
      step: "mounted: each row's toggle holds the pending placeholder; the browser is not idle yet",
      lines: rowsDrawn(),
      requests: requests.splice(0),
    });
    // The placeholder, the chevron, and the toggle are the nodes the arrival keeps.
    const changeBefore = changeOf(106);
    const toggleBefore = childByClass(changeOf(106), "github-pulls-toggle");
    const pendingBefore = lineOf(106).childNodes[0];
    await paint();
    assert.equal(
      lineOf(106).childNodes[0],
      pendingBefore,
      "the placeholder is one node across paints, so its quiet period and pulse run once",
    );
    await runIdle();
    const arrived = rowsDrawn();
    if (totals !== null) {
      // Each row draws the component built with its zero totals left out, after the dot
      // before it, and is described by its words (mb-efum).
      const drawn = SHOWN.map((number, at) => {
        const said = sdk.changeLine(lines.rowLineInput(rowSummaries.get(number), null));
        const line = shape(lineOf(number).childNodes);
        assert.deepEqual(
          line,
          shape([...sdk.changeLineNodes(said)]),
          `#${number} draws the component with its zero totals left out`,
        );
        assert.equal(arrived[`#${number}`].words, `Changed files: ${said.label}`);
        assert.ok(!/[+−]0\b/.test(arrived[`#${number}`].text), `#${number} shows no zero total`);
        // The totals the line shows, each its class and text.
        const stats = findByClass(lineOf(number), "change-line-stats").childNodes;
        return {
          row: `#${number}`,
          totals: totals[at],
          text: arrived[`#${number}`].text,
          words: arrived[`#${number}`].words,
          shows: stats.map((node) => `${node.className}: ${textOf(node)}`),
        };
      });
      handle.dispose();
      restore();
      return { drawn };
    }
    steps.push({
      step: "idle: one read for the rows drawn; #106's and #105's lines arrive, and #104 and #103 have none",
      lines: arrived,
      requests: requests.splice(0).map((route) => `${route.split("&")[0].slice(0, 80)}…`),
    });
    assert.equal(changeOf(106), changeBefore, "the toggle stays");
    assert.equal(childByClass(changeOf(106), "github-pulls-toggle"), toggleBefore);
    // The lines are the shell's one component, through the SDK, of the line totals alone,
    // with no file statuses (mb-lqkb): the separator, then the same nodes, part for part.
    const { rowLineInput } = lines;
    const summary106 = summaries.summed.body.rows.find((row) => row.number === 106);
    const said106 = sdk.changeLine(rowLineInput(summary106, null));
    assert.deepEqual(said106.statusParts, [], "the lines name no file statuses");
    assert.deepEqual(
      arrived["#106"].line,
      // Spread into this realm's array: the SDK's own is its sandbox's.
      shape([...sdk.changeLineNodes(said106)]),
      "the row draws the component, after the dot before it",
    );
    // The heading ends with readiness and the PR number. The diff toggle and age stay below.
    for (const number of SHOWN) {
      const row = arrived[`#${number}`];
      assert.deepEqual(row.run.slice(1, 4), [
        "sr-only github-pull-readiness-said",
        "github-pulls-title",
        "github-pulls-place",
      ]);
      assert.deepEqual(row.run.slice(-2), ["github-pulls-readiness", "github-pulls-number"]);
      assert.deepEqual(row.last, [
        "github-pulls-change-line",
        "github-pulls-toggle",
        "github-pulls-change-words",
      ]);
      assert.equal(row.end, "github-pulls-age age-min");
    }
    // The link is the run, the last line, and the number, the author, and the age said for
    // its name alone.
    assert.deepEqual(
      rowOf(106).childNodes.map((node) => node.className),
      ["github-pulls-heading", "github-pulls-tail", "sr-only"],
    );
    assert.equal(textOf(childByClass(rowOf(106), "sr-only")), "contributor · #106 · 1m");
    // Each item says its number and its last line in words, whatever its toggle shows: the
    // number, the author, and the age, read with the title as the item's name.
    for (const number of SHOWN) {
      assert.equal(arrived[`#${number}`].spoken, `contributor · #${number} · 1m`);
    }
    assert.equal(arrived["#106"].words, `Changed files: ${said106.label}`);
    assert.equal(
      rowOf(106).getAttribute("aria-describedby"),
      wordsOf(106).getAttribute("id"),
      "the row is described by its line's words",
    );
    // No file total and no file statuses: the totals alone (the spaces between items are the
    // layout's gap).
    assert.equal(arrived["#106"].text.replace(/\s/g, ""), said106.text.replace(/\s/g, ""));
    assert.ok(!/file/.test(arrived["#106"].text), "the line names no file total");
    assert.ok(!/\d [ADMR]\b/.test(arrived["#106"].text), "the line names no file status");
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
    /** A press on *target*, a part of #*number*'s item named *part*, by *type* ("click", or
     * "auxclick" for a middle press): whether the panel kept the browser from following the
     * item's link (`defaultPrevented`). */
    const press = (what, number, part, target, type = "click") =>
      keyStep(
        what,
        () => {
          const event = {
            target,
            button: type === "click" ? 0 : 1,
            defaultPrevented: false,
            preventDefault() {
              this.defaultPrevented = true;
            },
          };
          list.listeners.get(type)(event);
          return { defaultPrevented: event.defaultPrevented };
        },
        { item: number, on: part, ...(type === "click" ? {} : { type }) },
      );
    // Every part of the item but its toggle, the lines and the chevron after them, is the
    // item's link's: a press opens the pull request and expands nothing (docs/design-system.md,
    // "A Click on the Toggle's Line Toggles"; mb-pw8t).
    await press(
      "a press on #106's title opens it, and its files stay closed",
      106,
      "title",
      findByClass(rowOf(106), "github-pulls-title"),
    );
    await press(
      "a press on #105's number, after its title, opens it, and its files stay closed",
      105,
      "number",
      findByClass(rowOf(105), "github-pulls-number"),
    );
    await press(
      "a press on #105's author, in its run, opens it too",
      105,
      "author",
      findByClass(rowOf(105), "github-pulls-author"),
    );
    await press(
      "a press on #105's age opens it too",
      105,
      "age",
      findByClass(rowOf(105), "github-pulls-age"),
    );
    await press(
      "a press on #105's last line, past its toggle, opens it too",
      105,
      "last line",
      tailOf(105),
    );
    // A modified press, which on a link opens a new tab, toggles nothing on the toggle and
    // opens no page; off it, on the item's link, it is the browser's, which opens the pull
    // request in a new tab (`defaultPrevented` false).
    const modifiedPress = (what, number, part, target, modifier) =>
      keyStep(
        what,
        () => {
          const event = Object.assign(new globalThis.MouseEvent(), {
            target,
            button: 0,
            [modifier]: true,
            defaultPrevented: false,
            preventDefault() {
              this.defaultPrevented = true;
            },
          });
          list.listeners.get("click")(event);
          return { defaultPrevented: event.defaultPrevented };
        },
        { item: number, on: part, modifier },
      );
    await modifiedPress(
      "a Cmd-press on #105's number is the browser's, a new tab: nothing opens or toggles here",
      105,
      "number",
      findByClass(rowOf(105), "github-pulls-number"),
      "metaKey",
    );
    await modifiedPress(
      "a Ctrl-press on #105's chevron toggles nothing and opens no page",
      105,
      "chevron",
      childByClass(changeOf(105), "github-pulls-toggle"),
      "ctrlKey",
    );
    await press(
      "a middle press on #105's lines opens no tab, and toggles nothing",
      105,
      "lines",
      lineOf(105),
      "auxclick",
    );
    await modifiedPress(
      "a Cmd-press on #106's title is the browser's, a new tab: nothing opens here",
      106,
      "title",
      findByClass(rowOf(106), "github-pulls-title"),
      "metaKey",
    );
    await press(
      "a press on #106's state icon opens it again, and its files stay closed",
      106,
      "state icon",
      findByClass(rowOf(106), "github-pull-state-icon"),
    );
    assert.equal(rowOf(106).getAttribute("aria-expanded"), "false");
    // The toggle, the lines or the chevron: a press toggles, opens no page, and leaves the
    // focus on the item, the tree's one stop, so Space and the arrows go on from it.
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
      "a press on its lines, before the chevron, closes them: the lines are the toggle too",
      106,
      "lines",
      lineOf(106),
    );
    await press(
      "a press on the toggle itself, between its lines and its chevron, opens them again",
      106,
      "toggle",
      changeOf(106),
    );
    await press("and closes them", 106, "toggle", changeOf(106));
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
    await keyStep("Enter opens #105, and expands nothing", () => handle.activateAnchor());
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
    // A press on #103's chevron focuses #103, whose page is not the one open. A poll then
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
      "a press on #103's chevron opens its files and focuses #103, while #105's page is open",
      103,
      "chevron",
      childByClass(changeOf(103), "github-pulls-toggle"),
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

/** Rows by number in words: the first and the last of them and how many, or "none". */
const span = (numbers) =>
  numbers.length === 0
    ? "none"
    : numbers.length === 1
      ? `#${numbers[0]}`
      : `#${numbers[0]} to #${numbers.at(-1)}, ${numbers.length} rows`;

/**
 * Mount the production panel in a pane `PANE_PX` tall whose rows each lay out `ROW_PX` tall,
 * shorter than `ROW_ESTIMATE_PX`, with the browser's frames, its layout's resize
 * notifications, and its idle time in the session's hands. The first window is placed at the
 * estimate, and the window the rows' heights place draws more of them. The browser is idle
 * once between the frame that drew the first window and the next: after that frame laid the
 * rows out and measured them, the window's frame waiting (`measured`), or before it
 * (`unmeasured`). Either way the one read of their lines names every row the window draws
 * (mb-hb4a): the lane settles the window before its read names the rows.
 *
 * @param {"measured" | "unmeasured"} idleAfter
 */
async function windowStory(idleAfter) {
  const panel = await import(pathToFileURL(path.join(GITHUB, "pulls-panel.js")).href);
  const PANE_PX = 600;
  // A closed row whose run is two lines, as most are at 380 px: the 2 px pad, two 19.5 px
  // lines, and 20 px of last line (`ROW_ESTIMATE_PX` in pulls-panel.js).
  const ROW_PX = 61;
  /** @type {FakeElement | null} */
  let pane = null;
  const heightOf = (node) =>
    node.classList?.contains("github-pulls-item")
      ? ROW_PX
      : node.classList?.contains("github-pulls-spacer")
        ? Number.parseFloat(node.style.height) || 0
        : 0;
  // The list at the pane's top, scrolled with it, and its items and spacers laid out in its
  // order.
  class WindowElement extends FakeElement {
    getBoundingClientRect() {
      const box = (top, height) => ({
        top,
        bottom: top + height,
        height,
        left: 0,
        right: 300,
        width: 300,
      });
      if (this === pane) {
        return box(0, PANE_PX);
      }
      if (this.classList.contains("github-pulls-list")) {
        return box(-pane.scrollTop, 0);
      }
      if (
        !this.classList.contains("github-pulls-item") &&
        !this.classList.contains("github-pulls-spacer")
      ) {
        return super.getBoundingClientRect();
      }
      let top = -pane.scrollTop;
      for (const node of this.parentNode?.childNodes ?? []) {
        if (node === this) {
          break;
        }
        top += heightOf(node);
      }
      return box(top, heightOf(this));
    }
  }
  /** Each ResizeObserver the panel makes, and the height it was last told of each target. */
  const observers = [];
  class ResizeObserverStandIn {
    constructor(callback) {
      this.callback = callback;
      this.told = new Map();
      observers.push(this);
    }
    observe(target) {
      this.told.set(target, null);
    }
    unobserve(target) {
      this.told.delete(target);
    }
    disconnect() {
      this.told.clear();
    }
  }
  /** A frame's layout: each observer is told of the boxes whose height changed since it was
   * last told, a box observed anew among them, as a browser tells it after layout. */
  const layout = () => {
    for (const observer of observers) {
      const entries = [];
      for (const [target, told] of observer.told) {
        const height = target.getBoundingClientRect().height;
        if (height !== told) {
          observer.told.set(target, height);
          entries.push({ target, borderBoxSize: [{ blockSize: height, inlineSize: 300 }] });
        }
      }
      if (entries.length > 0) {
        observer.callback(entries, observer);
      }
    }
  };
  /** @type {Map<number, () => void>} */
  const frames = new Map();
  let frameIds = 0;
  /** @type {(() => void)[]} */
  let idle = [];
  const requests = [];
  const document = {
    activeElement: null,
    visibilityState: "visible",
    addEventListener() {},
    createElement: (tag) => new WindowElement(tag),
    createDocumentFragment: () => new FakeNode("#fragment"),
    importNode: (node) => new WindowElement(node.localName),
  };
  const respond = (body, status = 200) =>
    Promise.resolve({ status, headers: { get: () => null }, json: async () => body });
  const globals = {
    document,
    window: {
      addEventListener() {},
      setTimeout: () => 0,
      clearTimeout() {},
      requestAnimationFrame(callback) {
        frameIds += 1;
        frames.set(frameIds, callback);
        return frameIds;
      },
      cancelAnimationFrame(id) {
        frames.delete(id);
      },
    },
    getComputedStyle: () => ({ getPropertyValue: () => "24" }),
    HTMLElement: FakeElement,
    Element: FakeElement,
    MouseEvent: class {},
    DOMParser: class {
      parseFromString() {
        return { body: { firstElementChild: new WindowElement("svg") } };
      }
    },
    IntersectionObserver: class {
      takeRecords() {}
      observe() {}
      disconnect() {}
    },
    ResizeObserver: ResizeObserverStandIn,
    fetch(route) {
      if (route.startsWith(`${ROUTE}?`)) {
        const numbers = new URL(route, "http://x").searchParams.get("numbers").split(",");
        requests.push(numbers.map(Number));
        const answer = answerFor(recordedRows("summed"), numbers.map(Number));
        return respond(answer.body, answer.status);
      }
      if (route.startsWith("/api/plugin/github/pulls?")) {
        return respond(listed);
      }
      if (route === "/api/plugin/github/pulls-prefetch") {
        return respond({ prefetch: "not_due" });
      }
      return respond(null, 404);
    },
  };
  const saved = {};
  for (const [name, value] of Object.entries(globals)) {
    saved[name] = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, { value, configurable: true, writable: true });
  }
  const restore = () => {
    for (const [name, descriptor] of Object.entries(saved)) {
      if (descriptor === undefined) {
        delete globalThis[name];
      } else {
        Object.defineProperty(globalThis, name, descriptor);
      }
    }
  };
  /** A frame: its animation callbacks, then its layout and the resize notifications. */
  const frame = async () => {
    await settle();
    const due = [...frames.values()];
    frames.clear();
    for (const callback of due) {
      callback();
    }
    layout();
    await settle();
  };
  /** An idle period: the idle callbacks asked for before it. */
  const idlePeriod = async () => {
    await settle();
    for (const callback of idle.splice(0)) {
      callback();
    }
    await settle();
  };
  try {
    pane = new WindowElement("div");
    pane.scrollTop = 0;
    const container = new WindowElement("div");
    pane.append(container);
    const handle = panel.mountPullsPanel(
      container,
      {
        kind: "pull-request-list",
        pullsNav: {
          filter: "all",
          current: null,
          shown: true,
          refreshAhead: false,
          scrollRoot: pane,
          open() {},
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
        filterControls: { groupHtml: () => "<div></div>", bind: () => () => {} },
        ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
          label: "1m",
          className: "age-min",
        })),
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
    const drawn = () =>
      list.childNodes
        .filter((node) => node.classList?.contains("github-pulls-item"))
        .map((node) => Number(node.dataset.number));
    // The list answers, and its first window is drawn at the estimate.
    await settle();
    const first = drawn();
    if (idleAfter === "measured") {
      await frame();
    }
    await idlePeriod();
    for (let turn = 0; turn < 4; turn += 1) {
      await frame();
      await idlePeriod();
    }
    const last = drawn();
    handle.dispose();
    restore();
    return {
      idle:
        idleAfter === "measured"
          ? "after the frame that measured the first window's rows, before the next"
          : "before the first window's rows were laid out",
      "drawn at the estimate": span(first),
      "drawn at the rows' heights": span(last),
      asked: requests.map(span),
      oneRead: requests.length === 1 && requests[0].join() === last.join(),
    };
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
  // Each story of the zero and unknown totals mounts the panel afresh: nothing it is shown
  // was read before in the document.
  const totals = [];
  for (const cases of [
    [
      { additions: 1093, deletions: 0 },
      { additions: 0, deletions: 493 },
      { additions: 3, deletions: 1 },
      { additions: 0, deletions: 0 },
    ],
    [
      { additions: 0, deletions: null },
      { additions: null, deletions: 2 },
      { additions: null, deletions: null },
      { additions: 1, deletions: 0 },
    ],
  ]) {
    lines.documentRowLines.clear();
    prefetch.documentComparisons.clear();
    totals.push(...(await rowStory(lines, cases)).drawn);
  }
  // The window placed at the estimate and drawn again at its rows' heights: one read names
  // every row it draws, whenever the browser is idle between the two frames (mb-hb4a).
  const windows = [];
  for (const idleAfter of ["measured", "unmeasured"]) {
    lines.documentRowLines.clear();
    prefetch.documentComparisons.clear();
    const story = await windowStory(idleAfter);
    assert.ok(story.oneRead, `${story.idle}: one read names every row drawn`);
    assert.notEqual(
      story["drawn at the estimate"],
      story["drawn at the rows' heights"],
      `${story.idle}: the rows' heights move the window`,
    );
    windows.push(story);
  }
  // Every step of the row story holds the item's one zone (mb-1z7j) and the rule for a row
  // with a disclosure toggle (docs/design-system.md, "A Click on the Toggle's Line Toggles"):
  // a press on the toggle, a Pulls row's lines and the chevron after them (mb-pw8t), toggles
  // that item's files and opens no page, and a press anywhere else on the item opens it and
  // toggles nothing. Only those presses and Space, Right, and Left change what is open; a
  // walk, Enter, Tab, or a line's arrival opens nothing.
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
        // Each item's toggle turns its chevron with the item's one state, is hidden from
        // assistive technology with no role, so the tree holds only its items and their
        // groups, and is never a stop of its own.
        const number = /#(\d+)/.exec(line)[1];
        const turn = now[number] === "true" ? "expanded" : "collapsed";
        assert.ok(line.includes(`· chevron ${turn}`), `${step.step}: ${line}`);
        assert.ok(
          line.includes("· hidden · chevron") && line.endsWith("no stop"),
          `${step.step}: ${line}`,
        );
      } else {
        assert.ok(step.tree[at + 1].startsWith("  "), "each item's row has its toggle");
      }
    }
    if (before !== null) {
      const changed = Object.keys(now).filter((number) => now[number] !== before[number]);
      if (step.pressed !== undefined) {
        // A modified or a middle press toggles nothing, wherever it lands, and opens no page
        // here; on the toggle the browser follows no link either, and off it the browser's
        // new tab is its own.
        const onToggle = ["chevron", "lines", "toggle"].includes(step.pressed.on);
        const plain = step.pressed.modifier === undefined && step.pressed.type === undefined;
        if (!plain) {
          assert.equal(step.opened, undefined, `${step.step}: a modified press opens no page`);
          assert.deepEqual(step.handled, { defaultPrevented: onToggle }, step.step);
        }
        assert.deepEqual(
          changed,
          onToggle && plain ? [String(step.pressed.item)] : [],
          `${step.step}: a press on the toggle toggles, and on the item's other parts does not`,
        );
        if (onToggle) {
          assert.equal(step.opened, undefined, `${step.step}: the toggle opens no page`);
          assert.deepEqual(step.handled, { defaultPrevented: true }, step.step);
        } else if (plain) {
          assert.ok(step.opened?.length > 0, `${step.step}: the item's link opens it`);
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
    ["age", "author", "chevron", "last line", "lines", "number", "state icon", "title", "toggle"],
    "the story presses every part of an item",
  );
  // One part a run, so each transcript block stays one reviewable size: `lane`, `row`,
  // `totals`, `tree`, `focus`, or `window`. (A block also has to stay under the size at which
  // the transcript runner's matcher, a regular expression built from the block, is too large
  // to compile.)
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
        : part === "totals"
          ? { totals }
          : part === "tree"
            ? { tree: treeSteps }
            : part === "focus"
              ? { focus: focusSteps }
              : part === "window"
                ? { window: windows }
                : {
                    steps: {
                      lane: lane.length,
                      row: lineSteps.length,
                      totals: totals.length,
                      tree: treeSteps.length,
                      focus: focusSteps.length,
                      window: windows.length,
                    },
                  };
  process.stdout.write(`${JSON.stringify({ ...printed, invariants: true }, null, 2)}\n`);
})().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
