// Browserless session: each open pull request's readiness where a row names it (mb-3n21), the
// verdict's glyph in the Pulls tab's readiness column and on a stack's member rows, through the
// production code.
//
// builtin_plugins/github/row-readiness.js decides which rows are read and when, and what each
// draws: the verdict, the tone, and the label the server's answer gives (`GET pull-statuses`),
// for an open or draft pull request whose head the answer judged, and nothing for any other.
// builtin_plugins/github/stack-member-row.js draws it, its words after the state icon, out of
// view, and its glyph, hidden, where the row's layout puts it. The answers are the server's:
// tests/fixtures/github-pulls-readiness-responses.json, which
// tests/test_github_pulls_readiness_session.py records from the real routes, before the scan of
// every open pull request's status, while it runs, once it has ended, and after a push it has
// not read, with what the list's ask said of the scan each time.
//
// `lane` drives the lane alone over those answers, with the browser's idle time and its clock in
// the session's hands, and prints what each row draws at each step and what was asked. `panel`
// mounts the production Pulls panel over a stand-in for the DOM with the SDK's own painters
// (tests/dom/sdk-ref-fixture.js), and prints each row's verdict, glyph, label, last line, and
// the name its link is read by, as the list's ask starts the scan, ends it, and a push moves a
// row's head. `menu` mounts the production stack menu (`createStackMenu` in pull-page.js) on a
// lane of its own and prints each member's readiness and name as it opens. `invariants` are the
// relations every step holds, and `invariants.panel` what each row drew once the scan ended,
// which tests/test_github_pulls_readiness_session.py holds to the recorded verdicts. Where the
// column and its label are laid out, and in what ink, is Chrome's
// (tests/dom/github-pulls-readiness-chrome.mjs).

const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { FakeElement, FakeNode } = require("./pulls-test-dom.js");

const root = path.resolve(__dirname, "../..");
const GITHUB = path.join(root, "src/metabrowser/builtin_plugins/github");
const recorded = require("../fixtures/github-pulls-readiness-responses.json");
// The recording holds a row as one line of JSON.
for (const answer of Object.values(recorded)) {
  if (Array.isArray(answer.body?.rows)) {
    answer.body.rows = answer.body.rows.map((row) => JSON.parse(row));
  }
}
const SOURCE = recorded.list.body.source;
const ROUTE = "/api/plugin/github/pull-statuses";
const REFRESH = "/api/plugin/github/pulls-refresh";
const PUSHED = 105;
// The rows each story prints: an open pull request of each tone, ready to merge, waiting on its
// checks, and a draft with conflicts; a merged and a closed one; and #105, which is pushed.
const SHOWN = [106, 105, 10, 9, 8, 7];

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/** The recorded rows by number, of one or more recorded answers, the later ones winning. */
function rowsOf(...names) {
  const rows = new Map();
  for (const name of names) {
    for (const row of recorded[name].body.rows) {
      rows.set(row.number, row);
    }
  }
  return rows;
}

/** The server's answer for *numbers* from the recorded answer *name*: its envelope, with the
 * rows asked for, in their order. */
function answerFor(name, numbers) {
  const rows = rowsOf(...(name === "unscanned" ? ["unscanned", "unscanned_more"] : [name]));
  const more = name === "scanned" ? rowsOf("scanned_more") : new Map();
  const body = recorded[name].body;
  return {
    status: 200,
    body: {
      ...body,
      rows: numbers.map((number) => rows.get(number) ?? more.get(number)).filter(Boolean),
    },
  };
}

/** What a row draws, in words: its verdict, its tone, and its label, or "none". */
const said = (readiness) =>
  readiness === null ? "none" : `${readiness.verdict} (${readiness.tone}): ${readiness.label}`;

/** The name an element is read by, from its content: the text of what is not hidden, an image
 * by its label, in the order the row has them, its spaces collapsed. */
function nameOf(node) {
  const words = (each) => {
    if (each.data !== undefined) {
      return each.data;
    }
    if (each.hidden === true || each.getAttribute("aria-hidden") === "true") {
      return "";
    }
    if (each.getAttribute("role") === "img") {
      return each.getAttribute("aria-label") ?? "";
    }
    return each.childNodes.map(words).join(" ");
  };
  return words(node).replaceAll(" ", " ").replace(/\s+/g, " ").trim();
}

/**
 * The lane alone: the browser's idle callbacks queued for the session to run, its clock the
 * session's, and every request it sends logged.
 */
async function laneStory(readiness) {
  const { createRowReadiness, createReadinessIndex, ROW_READINESS_RETRY_MS } = readiness;
  const prefetch = await import(pathToFileURL(path.join(GITHUB, "comparison-prefetch.js")).href);
  const keep = prefetch.createComparisonKeep({ later: (callback) => callback() });
  const index = createReadinessIndex();
  let now = 1_000_000;
  /** @type {(() => void)[]} */
  let idle = [];
  const asked = [];
  let phase = "unscanned";
  const repaints = [];
  const deps = () => ({
    keep,
    index,
    async read(numbers) {
      asked.push(`GET ${ROUTE}?numbers=${numbers.join(",")}`);
      if (phase instanceof Error) {
        throw phase;
      }
      return answerFor(phase, numbers);
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
  const list = new Map(recorded.list.body.rows.map((row) => [row.number, row]));
  const stateOf = (row) =>
    row.merged ? "merged" : row.state === "closed" ? "closed" : row.draft ? "draft" : "open";
  let rows = SHOWN.map((number) => {
    const row = list.get(number);
    return { number, head: row.head_oid, state: stateOf(row) };
  });
  let lane = createRowReadiness(deps());
  const steps = [];
  const runIdle = async () => {
    while (idle.length > 0) {
      idle.shift()();
      await settle();
    }
  };
  const draws = (drawing = rows, of = lane) =>
    Object.fromEntries(drawing.map((row) => [`#${row.number}`, said(of.readiness(row))]));
  const step = async (what, act, drawing = rows, of = () => lane) => {
    asked.length = 0;
    repaints.length = 0;
    await act();
    const state = of().snapshot();
    steps.push({
      step: what,
      draws: draws(drawing, of()),
      asked: [...asked],
      ...(repaints.length > 0 ? { repainted: [...repaints] } : {}),
      lane: { wanted: state.wanted, running: state.running, scanning: state.scanning },
    });
  };

  await step("the list draws six rows: nothing is read until the browser is idle", () =>
    lane.want(rows, SOURCE),
  );
  assert.equal(idle.length, 1, "one read waits for idle");
  await step(
    "idle: one read names the four open rows, and none of the merged or closed ones; no scan has run, so the server has no status of any",
    runIdle,
  );
  assert.deepEqual(
    asked,
    [`GET ${ROUTE}?numbers=106,105,10,7`],
    "closed and merged rows are not asked",
  );
  await step("drawn again: nothing is read", () => lane.want(rows, SOURCE));
  assert.equal(idle.length, 0);
  await step(
    "the list's ask starts the scan: every row is read again, and the scan runs",
    async () => {
      phase = "scanning";
      lane.scanned(recorded.scan_started.body.status_scan);
      await runIdle();
    },
  );
  assert.equal(asked.length, 1, "a scan's start reads the rows drawn once");
  await step("the next ask finds the scan running: nothing more is read", async () => {
    lane.scanned(recorded.scan_joined.body.status_scan);
    await runIdle();
  });
  assert.deepEqual(asked, [], "a scan the lane heard running reads nothing more");
  await step(
    "the next finds it over: every row is read again, and each open row draws its verdict",
    async () => {
      phase = "scanned";
      lane.scanned(recorded.scan_not_due.body.status_scan);
      await runIdle();
    },
  );
  const judged = draws();
  assert.equal(judged["#9"], "none", "a closed pull request draws none");
  assert.equal(judged["#8"], "none", "a merged pull request draws none");
  await step("an ask with the scan still over reads nothing", async () => {
    lane.scanned(recorded.scan_not_due.body.status_scan);
    await runIdle();
  });
  assert.deepEqual(asked, []);
  // A Pulls tab mounted again in the document: its lane shares the document's index.
  lane.dispose();
  lane = createRowReadiness(deps());
  await step("a Pulls tab mounted again: each glyph at once, from the document's index", () =>
    lane.want(rows, SOURCE),
  );
  assert.equal(idle.length, 0, "a remount reads nothing");
  assert.deepEqual(draws(), judged, "a remount draws what was read");
  // #105 is pushed: the list's row names the new head.
  const pushedHead = recorded.pushed.body.rows[0].head;
  rows = rows.map((row) => (row.number === PUSHED ? { ...row, head: pushedHead } : row));
  phase = "pushed";
  await step(
    "#105 is pushed: its verdict judged the old head, so it draws none, and it alone is read again; the server has no status for the new head",
    async () => {
      lane.want(rows, SOURCE);
      await runIdle();
    },
  );
  assert.deepEqual(asked, [`GET ${ROUTE}?numbers=${PUSHED}`]);
  // The ask starts the scan again, and a read finds it over: the read's rows hold, and the
  // rest of the document's answers are older than the scan's end.
  phase = "scanned";
  await step(
    "a scan starts and a read finds it over: the read's rows hold, and nothing more is read",
    async () => {
      lane.scanned(recorded.scan_started.body.status_scan);
      await runIdle();
      lane.want(rows, SOURCE);
      await runIdle();
    },
  );
  assert.equal(asked.length, 1, "one read for the rows drawn");
  assert.equal(lane.snapshot().scanning, false, "the read said the scan is over");
  phase = new Error("the connection broke");
  await step("a read fails: each row keeps the glyph it had", async () => {
    lane.scanned(recorded.scan_started.body.status_scan);
    await runIdle();
  });
  assert.equal(draws()["#106"], judged["#106"], "a failure takes no glyph away");
  await step("drawn again within the minute: nothing is read", async () => {
    lane.want(rows, SOURCE);
    await runIdle();
  });
  assert.deepEqual(asked, []);
  phase = "scanned";
  await step("a minute on, the failed read is asked again", async () => {
    now += ROW_READINESS_RETRY_MS;
    lane.want(rows, SOURCE);
    await runIdle();
  });
  assert.equal(asked.length, 1);

  // A stack's member rows, which know no head, on a lane of their own over the document's
  // index: a member the Pulls tab read is settled, one it did not draw is read, and a merged
  // one is never asked.
  const members = [
    { number: 7, head: null, state: null },
    { number: 6, head: null, state: null },
    { number: 8, head: null, state: "merged" },
  ];
  phase = "scanned";
  const menuLane = createRowReadiness(deps());
  await step(
    "a stack's members, whose heads the menu does not know: #7, which the Pulls tab read, draws at once, #6 is read, and merged #8 is not asked",
    async () => {
      menuLane.refresh(members, SOURCE);
      await runIdle();
    },
    members,
    () => menuLane,
  );
  assert.deepEqual(asked, [`GET ${ROUTE}?numbers=6`]);
  await step(
    "opened again within the minute: nothing is read",
    async () => {
      menuLane.refresh(members, SOURCE);
      await runIdle();
    },
    members,
    () => menuLane,
  );
  assert.deepEqual(asked, []);
  await step(
    "a minute on, opened again: each member is read again",
    async () => {
      now += ROW_READINESS_RETRY_MS;
      menuLane.refresh(members, SOURCE);
      await runIdle();
    },
    members,
    () => menuLane,
  );
  assert.deepEqual(asked, [`GET ${ROUTE}?numbers=7,6`]);
  menuLane.dispose();

  // A server that serves no GitHub repository answers once, for every row.
  phase = "not_github";
  const plain = createRowReadiness({ ...deps(), index: createReadinessIndex() });
  await step(
    "a server with no repository: one answer, and no row draws a glyph",
    async () => {
      plain.want(rows, SOURCE);
      await runIdle();
      plain.want(rows, SOURCE);
      await runIdle();
    },
    rows,
    () => plain,
  );
  assert.equal(asked.length, 1, "a refusal for every row is not asked again");
  lane.dispose();
  return steps;
}

/**
 * The production panel, mounted over a stand-in for the DOM with the SDK's own painters, on the
 * recorded list; each read of the statuses answered from the recorded phase, and each ask of the
 * list's refresh with the recorded answer of the phase.
 */
async function panelStory() {
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
  const timers = [];
  let phase = "unscanned";
  let refreshAnswer = recorded.scan_not_due;
  let listAnswer = recorded.list.body;
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
    fetch(route, options = {}) {
      if (route.startsWith(`${ROUTE}?`)) {
        const numbers = new URL(route, "http://x").searchParams.get("numbers").split(",");
        requests.push(
          numbers.length > 8
            ? `GET ${ROUTE}?numbers=${numbers.slice(0, 8).join(",")},… (${numbers.length})`
            : `GET ${route}`,
        );
        const answer = answerFor(phase, numbers.map(Number));
        return respond(answer.body, answer.status);
      }
      if (route === REFRESH && options.method === "POST") {
        requests.push(`POST ${REFRESH}: status_scan=${refreshAnswer.body.status_scan}`);
        return respond(refreshAnswer.body, refreshAnswer.status);
      }
      if (route.startsWith("/api/plugin/github/pulls?")) {
        return respond(listAnswer);
      }
      if (route === "/api/plugin/github/pulls-prefetch") {
        return respond({ prefetch: "not_due" });
      }
      // The stacks, a record, or a list of files: nothing this story reads.
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
  const runIdle = async () => {
    while (idle.length > 0) {
      idle.shift()();
      await paint();
    }
  };
  /** @type {Record<string, () => unknown>} */
  const parts = {};
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
          open() {},
          file: null,
          fileHref: (number, file) => `/pull/${number}/files/${file}`,
          pageFor: () => null,
          onPageChange: () => () => {},
          filterChanged() {},
          // The navigation's one Refresh, which the reader presses (static/refresh-plan.js).
          refreshParts: {
            provide(name, part) {
              parts[name] = part;
              return () => {};
            },
          },
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
    const rowOf = (number) => childByClass(item(number), "github-pulls-entry").childNodes[0];
    const headingOf = (number) => childByClass(rowOf(number), "github-pulls-heading");
    const tailOf = (number) => childByClass(rowOf(number), "github-pulls-tail");
    const cellOf = (number) => childByClass(tailOf(number), "github-pulls-readiness");
    /** What a row draws of its readiness: the glyph's verdict and tone, the label after it,
     * whether the column is hidden from assistive technology, the words after the state icon,
     * the last line's parts, and the name its link is read by. */
    const drawnRow = (number) => {
      const cell = cellOf(number);
      const glyph = childByClass(cell, "github-pull-readiness-icon") ?? null;
      const label = childByClass(cell, "github-pulls-readiness-label") ?? null;
      return {
        glyph: glyph === null ? null : `${glyph.dataset.verdict} (${glyph.dataset.tone})`,
        label: label === null ? null : label.textContent,
        hidden: cell.getAttribute("aria-hidden") === "true",
        words: childByClass(headingOf(number), "github-pull-readiness-said").textContent,
        last: tailOf(number).childNodes.map((node) => node.className.split(" ")[0]),
        name: nameOf(rowOf(number)),
      };
    };
    const rowsDrawn = () =>
      Object.fromEntries(SHOWN.map((number) => [`#${number}`, drawnRow(number)]));
    const steps = [];
    const step = async (what, act) => {
      requests.length = 0;
      await act();
      await paint();
      steps.push({ step: what, rows: rowsDrawn(), requests: [...requests] });
    };
    await step(
      "mounted: every row's readiness column is there and empty; nothing is read yet",
      paint,
    );
    const cellsBefore = SHOWN.map(cellOf);
    await step(
      "idle: one read for the open rows drawn; no scan has run, so the server has no status of any, and every column stays empty",
      runIdle,
    );
    assert.ok(
      steps.at(-1).requests.filter((line) => line.startsWith(`GET ${ROUTE}`)).length === 1,
      "one read for the rows drawn",
    );
    await step(
      "the reader presses Refresh, and the ask starts the scan: the rows are read again",
      async () => {
        phase = "scanning";
        refreshAnswer = recorded.scan_started;
        await parts.pulls();
        await paint();
        await runIdle();
      },
    );
    await step(
      "Refresh again: the ask finds the scan over, and the rows are read again; each open row draws its verdict, the merged and the closed none",
      async () => {
        phase = "scanned";
        refreshAnswer = recorded.scan_not_due;
        await parts.pulls();
        await paint();
        await runIdle();
      },
    );
    const settled = steps.at(-1).rows;
    assert.ok(
      SHOWN.every((number, at) => cellOf(number) === cellsBefore[at]),
      "a readiness arriving keeps each row's column",
    );
    const invariants = Object.fromEntries(
      SHOWN.map((number) => {
        const glyph = childByClass(cellOf(number), "github-pull-readiness-icon") ?? null;
        const label = childByClass(cellOf(number), "github-pulls-readiness-label") ?? null;
        return [
          String(number),
          glyph === null
            ? null
            : {
                verdict: glyph.dataset.verdict,
                tone: glyph.dataset.tone,
                label: label.textContent,
              },
        ];
      }),
    );
    for (const number of SHOWN) {
      const row = settled[`#${number}`];
      assert.deepEqual(row.last, [
        "github-pulls-change",
        "github-pulls-readiness",
        "github-pulls-age",
      ]);
      assert.ok(row.hidden, `#${number}'s column is hidden from assistive technology`);
      const drawn = invariants[String(number)];
      // The name says the verdict after the state, as the state icon says the state.
      const state = row.name.split(" ")[0];
      assert.ok(
        drawn === null
          ? !row.name.includes("Ready") && row.words === ""
          : row.name.startsWith(`${state} ${drawn.label} `) && row.words === drawn.label,
        `#${number}'s name says its verdict after its state: ${row.name}`,
      );
      assert.equal(row.label, drawn?.label ?? null, `#${number}'s label is its verdict's`);
    }
    // A push the list finds: its next answer names #105's new head.
    listAnswer = recorded.pushed_list.body;
    phase = "pushed";
    await step(
      "a poll: the list names #105's new head, so its verdict, which judged the old one, is drawn no more, and #105 alone is read again; the server has no status for the new head",
      async () => {
        const poll = timers
          .filter(({ from }) => /scheduleNext .*pulls-panel\.js/.test(from))
          .at(-1);
        assert.ok(poll !== undefined, "the list has a poll waiting");
        timers.length = 0;
        poll.callback();
        await paint();
        await runIdle();
      },
    );
    assert.deepEqual(
      steps.at(-1).requests.filter((line) => line.startsWith(`GET ${ROUTE}`)),
      [`GET ${ROUTE}?numbers=${PUSHED}`],
    );
    assert.equal(steps.at(-1).rows[`#${PUSHED}`].glyph, null);
    // The list's ask starts a scan again, and the panel is disposed before the browser is
    // idle: the read it had queued is cancelled, and nothing is read once it is gone.
    requests.length = 0;
    phase = "scanning";
    refreshAnswer = recorded.scan_started;
    await parts.pulls();
    await paint();
    const queued = idle.length;
    handle.dispose();
    await runIdle();
    const afterDispose = requests.filter((line) => line.startsWith(`GET ${ROUTE}`));
    assert.ok(queued > 0, "the scan's start queued a read");
    assert.deepEqual(afterDispose, [], "a disposed panel reads no readiness");
    steps.push({
      step: "the ask starts a scan again, and the panel is disposed before the browser is idle: its queued read is cancelled, and nothing is read",
      requests: [...requests],
    });
    return { steps, invariants };
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

/**
 * The production stack menu of #7's page, over a stand-in for the DOM, its members' readiness
 * from a lane of its own over the recorded answers once the scan ended: #7's is its page's own,
 * the server's verdict on it, and the others' are read as the menu opens.
 */
async function menuStory(readiness) {
  const page = await import(pathToFileURL(path.join(GITHUB, "pull-page.js")).href);
  const listeners = new Map();
  const saved = {
    HTMLElement: Object.getOwnPropertyDescriptor(globalThis, "HTMLElement"),
    document: Object.getOwnPropertyDescriptor(globalThis, "document"),
    DOMParser: Object.getOwnPropertyDescriptor(globalThis, "DOMParser"),
  };
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
  globalThis.DOMParser = class {
    parseFromString() {
      return { body: { firstElementChild: new FakeElement("svg") } };
    }
  };
  try {
    /** @type {(() => void)[]} */
    let idle = [];
    const asked = [];
    let menu = null;
    const lane = readiness.createRowReadiness({
      index: readiness.createReadinessIndex(),
      async read(numbers) {
        asked.push(`GET ${ROUTE}?numbers=${numbers.join(",")}`);
        return answerFor("scanned", numbers);
      },
      schedule(callback) {
        idle.push(callback);
        return callback;
      },
      cancel(handle) {
        idle = idle.filter((callback) => callback !== handle);
      },
      isVisible: () => true,
      now: () => 1_000_000,
      changed: () => menu?.repaint(),
    });
    const scanned = rowsOf("scanned", "scanned_more");
    const own = readiness.shownReadiness(scanned.get(7));
    // Each member's state as the Pulls list said it, and none for #6, which it has not drawn.
    const states = { 8: "merged", 7: "open", 6: null };
    const stack = {
      number: 286,
      base_ref: "main",
      open: true,
      pulls: [6, 7, 8],
      titles: ["Count to two", "Follow up", "Stack change 8"],
      authors: ["contributor", "forker", "contributor"],
      avatars: [null, null, null],
      labels: [null, null, null],
    };
    const memberRow = (target) => ({ number: target, head: null, state: states[target] });
    menu = page.createStackMenu(stack, 7, {
      state: (target) => states[target],
      link(number) {
        const link = new FakeElement("a");
        link.dataset.number = String(number);
        return link;
      },
      icon: null,
      currentTitle: "Follow up",
      titleNodes: require("./sdk-ref-fixture.js").refHelpers(document).titleNodes,
      menus: require("./sdk-ref-fixture.js").refHelpers(document).menus,
      readiness: (target) => (target === 7 ? own : lane.readiness(memberRow(target))),
      onOpen() {
        lane.refresh(stack.pulls.filter((target) => target !== 7).map(memberRow), SOURCE);
      },
    });
    const elements = (node) => node.childNodes.filter((child) => child instanceof FakeElement);
    const links = () =>
      menu.element.childNodes
        .find((node) => node.classList.contains("github-pull-stack-menu"))
        .childNodes.find((node) => node.classList.contains("menu-group"))
        .childNodes.filter((node) => node.dataset?.number !== undefined);
    /** Each member: its parts, its readiness's words and glyph, and the name it is read by. */
    const members = () =>
      Object.fromEntries(
        links().map((link) => {
          const parts = elements(link);
          const cell = parts.at(-1);
          const glyph = elements(cell)[0] ?? null;
          return [
            `#${link.dataset.number}`,
            {
              parts: parts.map((part) => part.className.split(" ").at(-1)),
              glyph: glyph === null ? null : `${glyph.dataset.verdict} (${glyph.dataset.tone})`,
              hidden: cell.getAttribute("aria-hidden") === "true",
              name: nameOf(link),
            },
          ];
        }),
      );
    const steps = [];
    menu.element.open = true;
    menu.element.listeners.get("toggle")();
    steps.push({
      step: "the menu opens: #7, the page's own, says its page's verdict; #6 waits for its read, and merged #8 has none",
      members: members(),
      asked: [...asked],
    });
    while (idle.length > 0) {
      idle.shift()();
      await settle();
    }
    steps.push({
      step: "idle: #6's read, and its verdict drawn in the open menu",
      members: members(),
      asked: [...asked],
    });
    const layouts = new Set(Object.values(members()).map((member) => member.parts.join(" ")));
    assert.equal(layouts.size, 1, "every member has one layout, a member with no readiness too");
    menu.dispose();
    lane.dispose();
    return steps;
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
  const readiness = await import(pathToFileURL(path.join(GITHUB, "row-readiness.js")).href);
  const lane = await laneStory(readiness);
  const { steps: panel, invariants } = await panelStory();
  const menu = await menuStory(readiness);
  process.stdout.write(
    `${JSON.stringify({ lane, panel, menu, invariants: { panel: invariants } }, null, 2)}\n`,
  );
})().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
