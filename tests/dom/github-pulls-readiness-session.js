// Browserless session: each open pull request's readiness where a row names it (mb-3n21), the
// verdict's glyph in the Pulls tab's readiness column and on a stack's member rows, through the
// production code.
//
// builtin_plugins/github/row-readiness.js decides which rows are read and when, and what each
// draws: the verdict, the tone, and the label the server's answer gives (`GET pull-statuses`),
// for an open or draft pull request whose head and state the answer judged, and nothing for any
// other.
// builtin_plugins/github/stack-member-row.js draws it, its words after the state icon, out of
// view, and its glyph, hidden, where the row's layout puts it. The answers are the server's:
// tests/fixtures/github-pulls-readiness-responses.json, which
// tests/test_github_pulls_readiness_session.py records from the real routes, before the scan of
// every open pull request's status, while it runs, once it has ended, after a push it has not
// read, after a scan another tab's Refresh started, and after a pull request is marked a draft,
// with what the list's ask said of the scan each time.
//
// `lane` drives the lane alone over those answers, with the browser's idle time and its clock in
// the session's hands, and prints what each row draws at each step and what was asked; each
// surface draws a row before it asks for it, as a paint does. `panel`
// mounts the production Pulls panel over a stand-in for the DOM with the SDK's own painters
// (tests/dom/sdk-ref-fixture.js), and prints each row's verdict, glyph, label, last line, and
// the name its link is read by, as the list's ask starts the scan, ends it, and a push moves a
// row's head, and as it is mounted again. `menu` mounts the production stack menu
// (`createStackMenu` in pull-page.js) on a lane of its own, and then over an index another lane
// has read, and prints each member's readiness and name as it opens. `reads` draws one pull
// request on every kind of surface at once, each by the head it knows, in shuffled orders, and
// prints how often it is read for each thing that says it changed, at most once, and what each
// surface draws. `invariants` are the
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
 * rows asked for, in their order. The rows of the list's second page were asked apart, in the
 * answer named `<name>_more`. */
function answerFor(name, numbers) {
  const more = `${name}_more`;
  const rows = rowsOf(...(more in recorded ? [name, more] : [name]));
  const body = recorded[name].body;
  return {
    status: 200,
    body: { ...body, rows: numbers.map((number) => rows.get(number)).filter(Boolean) },
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
  // The list's two pages: by activity, #8 and #7 are on the second.
  const list = new Map(
    [...recorded.list.body.rows, ...recorded.more.body.rows].map((row) => [row.number, row]),
  );
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
  // What each row draws, as a surface's paint asks it, naming the rows' repository itself.
  const draws = (drawing = rows, of = lane) =>
    Object.fromEntries(drawing.map((row) => [`#${row.number}`, said(of.readiness(row, SOURCE))]));
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
  /** What the list's recorded ask *name* said of the scan, as the Pulls tab passes it on. */
  const ask = (of, name) =>
    of.scanned(recorded[name].body.status_scan, recorded[name].body.status_scan_at);

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
      ask(lane, "scan_started");
      await runIdle();
    },
  );
  assert.equal(asked.length, 1, "a scan's start reads the rows drawn once");
  await step("the next ask finds the scan running: nothing more is read", async () => {
    ask(lane, "scan_joined");
    await runIdle();
  });
  assert.deepEqual(asked, [], "a scan the lane heard running reads nothing more");
  await step(
    "the next says the scan ended: every row is read again, and each open row draws its verdict",
    async () => {
      phase = "scanned";
      ask(lane, "scan_not_due");
      await runIdle();
    },
  );
  const judged = draws();
  assert.equal(judged["#9"], "none", "a closed pull request draws none");
  assert.equal(judged["#8"], "none", "a merged pull request draws none");
  await step("an ask that says the same scan ended reads nothing", async () => {
    ask(lane, "scan_not_due");
    await runIdle();
  });
  assert.deepEqual(asked, []);
  // A Pulls tab mounted again in the document: its lane shares the document's index, and its
  // first paint draws each row before it asks for any, as the panel's paint does.
  lane.dispose();
  lane = createRowReadiness(deps());
  const firstPaint = draws();
  await step(
    "a Pulls tab mounted again: its first paint, before it asks for a row, draws each glyph from the document's index, and its ask reads nothing",
    () => lane.want(rows, SOURCE),
  );
  assert.deepEqual(firstPaint, judged, "a remount's first paint draws what was read");
  assert.equal(idle.length, 0, "a remount reads nothing");
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
  // The ask starts the scan again, and a read finds none running: the read's rows hold, and
  // nothing more is read.
  phase = "scanned";
  await step(
    "a scan starts and a read finds none running: the read's rows hold, and nothing more is read",
    async () => {
      ask(lane, "scan_started");
      await runIdle();
      lane.want(rows, SOURCE);
      await runIdle();
    },
  );
  assert.equal(asked.length, 1, "one read for the rows drawn");
  assert.equal(lane.snapshot().scanning, false, "the read said no scan runs");
  phase = new Error("the connection broke");
  await step("a read fails: each row keeps the glyph it had", async () => {
    ask(lane, "scan_started");
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
  const menuFirstPaint = draws(members, menuLane);
  await step(
    "a stack's members, whose heads the menu does not know: #7, which the Pulls tab read, draws at once, #6 is read, and merged #8 is not asked",
    async () => {
      menuLane.refresh(members, SOURCE);
      await runIdle();
    },
    members,
    () => menuLane,
  );
  assert.equal(menuFirstPaint["#7"], draws(members, menuLane)["#7"], "drawn before it asks");
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
    "a minute on, opened again: each member is read again, once: #7 by the Pulls tab's lane, which draws it too and is told it is due, and #6 by the menu's",
    async () => {
      now += ROW_READINESS_RETRY_MS;
      menuLane.refresh(members, SOURCE);
      await runIdle();
    },
    members,
    () => menuLane,
  );
  assert.deepEqual(asked, [`GET ${ROUTE}?numbers=7`, `GET ${ROUTE}?numbers=6`]);
  menuLane.dispose();

  // A scan this lane did not hear start, another tab's Refresh's, as a look at the mirror's
  // base branches starts one after an ask has answered, ends before the next ask: the ask
  // starts nothing and says when the latest scan ended, later than the lane had heard.
  phase = "rescanned";
  await step(
    "a scan the lane did not hear start ends before the next ask, which says when: every row is read again",
    async () => {
      ask(lane, "scan_ended_elsewhere");
      await runIdle();
    },
  );
  assert.equal(asked.length, 1, "a scan's end it did not hear start reads the rows once");
  await step("the next ask says the same: nothing is read", async () => {
    ask(lane, "scan_ended_elsewhere");
    await runIdle();
  });
  assert.deepEqual(asked, []);

  // A pull request page reads #7's status itself, a minute after the scan observed it: every
  // row in the document that draws #7 reads it again, once, so the Pulls row says what the
  // page's header says without waiting for the next scan.
  const scannedAt = recorded.rescanned.body.rows.find((row) => row.number === 7).status.observed_at;
  const pageRead = new Date(Date.parse(scannedAt) + 60_000).toISOString().replace(".000Z", "Z");
  await step(
    "a pull request page reads #7's status itself, newer than the scan's: #7 alone is read again",
    async () => {
      index.heard(SOURCE, 7, pageRead);
      await runIdle();
    },
  );
  assert.deepEqual(asked, [`GET ${ROUTE}?numbers=7`]);
  await step("the page reads the same status again as it polls: nothing is read", async () => {
    index.heard(SOURCE, 7, pageRead);
    index.heard(SOURCE, 7, scannedAt);
    await runIdle();
  });
  assert.deepEqual(asked, []);

  // The author marks #106 a draft, which the list says: the verdict judged it open, so it is
  // drawn no more, even while a read fails, until the server judges the draft.
  const DRAFTED = recorded.drafted.body.rows[0].number;
  rows = rows.map((row) => (row.number === DRAFTED ? { ...row, state: "draft" } : row));
  phase = new Error("the connection broke");
  await step(
    "#106 is marked a draft: its verdict judged it open, so it draws none; its read again fails, and it still draws none",
    async () => {
      lane.want(rows, SOURCE);
      await runIdle();
    },
  );
  assert.deepEqual(asked, [`GET ${ROUTE}?numbers=${DRAFTED}`]);
  assert.equal(draws()[`#${DRAFTED}`], "none", "no verdict on a state it did not judge");
  phase = "drafted";
  await step(
    "a minute on, the draft is read again, and draws the server's verdict on it",
    async () => {
      now += ROW_READINESS_RETRY_MS;
      lane.want(rows, SOURCE);
      await runIdle();
    },
  );
  assert.deepEqual(asked, [`GET ${ROUTE}?numbers=${DRAFTED}`]);

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
  // The list's two pages, by activity: #8 and #7 are on the second, which the panel reads
  // once the reader reaches the end of the first.
  let listAnswer = recorded.list.body;
  let moreAnswer = recorded.more.body;
  /** @type {((entries: {isIntersecting: boolean}[]) => void) | null} */
  let reachEnd = null;
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
      constructor(callback) {
        reachEnd = callback;
      }
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
        const after = new URL(route, "http://x").searchParams.get("after");
        return respond(after === String(listAnswer.next_after) ? moreAnswer : listAnswer);
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
    const sdk = require("./sdk-ref-fixture.js").refHelpers(document);
    /** The production Pulls panel, mounted in this document. */
    const mount = () => {
      const into = new PanelElement("div");
      // A view tall enough to hold every row of both pages, so each is drawn.
      into.bounds = () => ({
        top: 0,
        bottom: 100_000,
        height: 100_000,
        left: 0,
        right: 800,
        width: 800,
      });
      return {
        container: into,
        handle: panel.mountPullsPanel(
          into,
          {
            kind: "pull-request-list",
            pullsNav: {
              filter: "all",
              current: null,
              shown: true,
              refreshAhead: false,
              scrollRoot: into,
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
        ),
      };
    };
    let { container, handle } = mount();
    const listOf = () =>
      container.childNodes.find((node) => node.classList?.contains("github-pulls-list"));
    let list = listOf();
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
    const cellOf = (number) =>
      childByClass(childByClass(tailOf(number), "github-pull-row-end"), "github-pulls-readiness");
    /** What a row draws of its readiness: the glyph's verdict and tone, the label after it,
     * whether the column is hidden from assistive technology, the words after the state icon,
     * the last line's parts, and the name its link is read by. */
    const drawnRow = (number) => {
      const cell = cellOf(number);
      const glyph = childByClass(cell, "github-pull-readiness-icon") ?? null;
      const label = childByClass(headingOf(number), "github-pull-readiness-said").textContent;
      return {
        glyph: glyph === null ? null : `${glyph.dataset.verdict} (${glyph.dataset.tone})`,
        label: label || null,
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
      "mounted, and the reader scrolls to the end of the list's first window, which reads its second: every row's readiness column is there and empty; nothing is read yet",
      async () => {
        await paint();
        reachEnd?.([{ isIntersecting: true }]);
        await paint();
      },
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
        const label = childByClass(headingOf(number), "github-pull-readiness-said").textContent;
        return [
          String(number),
          glyph === null
            ? null
            : {
                verdict: glyph.dataset.verdict,
                tone: glyph.dataset.tone,
                label,
              },
        ];
      }),
    );
    for (const number of SHOWN) {
      const row = settled[`#${number}`];
      assert.deepEqual(row.last, [
        "github-pulls-change",
        "github-pulls-age",
        "github-pull-row-end",
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
    moreAnswer = recorded.pushed_more.body;
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
    // The Pulls tab mounted again in the document: its lane shares the document's index, and
    // its first paint, before the browser is idle and before any read, draws each glyph the
    // index holds; #105's verdict judged a head the list no longer names, so it draws none.
    phase = "scanned";
    refreshAnswer = recorded.scan_not_due;
    requests.length = 0;
    ({ container, handle } = mount());
    list = listOf();
    await paint();
    const remounted = rowsDrawn();
    assert.deepEqual(
      requests.filter((line) => line.startsWith(`GET ${ROUTE}`)),
      [],
      "the first paint reads nothing",
    );
    for (const number of SHOWN) {
      assert.equal(
        remounted[`#${number}`].glyph,
        number === PUSHED ? null : settled[`#${number}`].glyph,
        `#${number} is drawn in the remounted tab's first paint`,
      );
    }
    steps.push({
      step: "the Pulls tab mounted again in the document: its first paint, before the browser is idle and before any read, draws each glyph the document's index holds",
      rows: remounted,
      requests: [...requests],
    });
    handle.dispose();
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
    const runIdle = async () => {
      while (idle.length > 0) {
        idle.shift()();
        await settle();
      }
    };
    /** A lane over *index*, each read logged with *who* asked it. */
    const laneOf = (index, who, changed) =>
      readiness.createRowReadiness({
        index,
        async read(numbers) {
          asked.push(`${who}: GET ${ROUTE}?numbers=${numbers.join(",")}`);
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
        changed,
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
    /** #7's page's stack menu, its other members' readiness on a lane over *index*, wired as
     * the page wires it (pull-page.js): each paint names the repository itself. */
    const menuOver = (index) => {
      let menu = null;
      const lane = laneOf(index, "menu", () => menu?.repaint());
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
        readiness: (target) => (target === 7 ? own : lane.readiness(memberRow(target), SOURCE)),
        onOpen() {
          lane.refresh(stack.pulls.filter((target) => target !== 7).map(memberRow), SOURCE);
        },
      });
      return { menu, lane };
    };
    const elements = (node) => node.childNodes.filter((child) => child instanceof FakeElement);
    const links = (menu) =>
      menu.element.childNodes
        .find((node) => node.classList.contains("github-pull-stack-menu"))
        .childNodes.find((node) => node.classList.contains("menu-group"))
        .childNodes.filter((node) => node.dataset?.number !== undefined);
    /** Each member: its parts, its readiness's words and glyph, and the name it is read by. */
    const members = (menu) =>
      Object.fromEntries(
        links(menu).map((link) => {
          const parts = elements(link);
          const end = elements(parts.at(-1)).at(-1);
          const cell = elements(end).find((part) =>
            part.classList.contains("github-pull-stack-member-readiness"),
          );
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
    const open = (menu) => {
      menu.element.open = true;
      menu.element.listeners.get("toggle")();
    };
    const steps = [];
    const first = menuOver(readiness.createReadinessIndex());
    open(first.menu);
    steps.push({
      step: "the menu opens: #7, the page's own, says its page's verdict; #6 waits for its read, and merged #8 has none",
      members: members(first.menu),
      asked: [...asked],
    });
    await runIdle();
    steps.push({
      step: "idle: #6's read, and its verdict drawn in the open menu",
      members: members(first.menu),
      asked: [...asked],
    });
    assert.equal(members(first.menu)["#6"].glyph, "ready (success)", "a read lands in the menu");
    const layouts = new Set(
      Object.values(members(first.menu)).map((member) => member.parts.join(" ")),
    );
    assert.equal(layouts.size, 1, "every member has one layout, a member with no readiness too");
    first.menu.dispose();
    first.lane.dispose();

    // Another page's menu, opened over the document's index once the Pulls tab has read #6: its
    // first open, which draws its members before it asks for any, draws #6's glyph, and nothing
    // is read.
    asked.length = 0;
    const shared = readiness.createReadinessIndex();
    const pulls = laneOf(shared, "pulls", () => {});
    const six =
      recorded.list.body.rows.find((row) => row.number === 6) ??
      recorded.more.body.rows.find((row) => row.number === 6);
    pulls.want([{ number: 6, head: six.head_oid, state: "open" }], SOURCE);
    await runIdle();
    const read = [...asked];
    const later = menuOver(shared);
    open(later.menu);
    await runIdle();
    steps.push({
      step: "the Pulls tab has read #6 into the document's index; another page's menu opens: its first open draws #6's glyph, and reads nothing",
      read_before: read,
      members: members(later.menu),
      asked: asked.slice(read.length),
    });
    assert.equal(members(later.menu)["#6"].glyph, "ready (success)", "drawn on its first open");
    assert.deepEqual(asked.slice(read.length), [], "a settled member is not read again");
    later.menu.dispose();
    later.lane.dispose();
    pulls.dispose();
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

/**
 * One pull request drawn by every kind of surface at once, over one index, each knowing it by
 * the head and the state it has (row-readiness.js): two Pulls tabs by the catalog's head, the
 * one the server judges; a stack's page and a stack menu by none; and a surface whose record
 * lags, by an older head. Each asks for it, the browser runs their idle callbacks, and their
 * reads land, in a shuffled order each turn, many turns between two things that say it
 * changed. Whatever the order, the row is read at most once for each, never in turn; and each
 * surface draws the verdict where the head it knows is the one the server judged, or it knows
 * none. The server's answers are #105's, before and after its push.
 */
async function readsStory(readiness) {
  const { createRowReadiness, createReadinessIndex, ROW_READINESS_RETRY_MS } = readiness;
  const NUMBER = PUSHED;
  const before = rowsOf("scanned").get(NUMBER);
  const after = rowsOf("pushed").get(NUMBER);
  const index = createReadinessIndex();
  let now = 1_000_000;
  let phase = "scanned";
  let reads = 0;
  /** @type {(() => void)[]} */
  let idle = [];
  /** @type {(() => void)[]} */
  const landing = [];
  // A fixed shuffle, so the transcript is the same each run.
  let seed = 20261126;
  const random = () => {
    seed = (seed * 1103515245 + 12345) % 2 ** 31;
    return seed / 2 ** 31;
  };
  const shuffled = (items) =>
    items
      .map((item) => ({ item, at: random() }))
      .sort((left, right) => left.at - right.at)
      .map(({ item }) => item);
  const surface = (name, row, ask) => ({
    name,
    row,
    ask,
    lane: createRowReadiness({
      index,
      keep: { quiet: async () => {} },
      read(numbers) {
        reads += 1;
        const answer = answerFor(phase, numbers);
        return new Promise((resolve) => landing.push(() => resolve(answer)));
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
      changed() {},
    }),
  });
  const lagging = "1".repeat(40);
  const surfaces = [
    surface(
      "a Pulls tab, by the catalog's head",
      { number: NUMBER, head: before.head, state: "open" },
      "want",
    ),
    surface("another Pulls tab", { number: NUMBER, head: before.head, state: "open" }, "want"),
    surface("a stack's page, by no head", { number: NUMBER, head: null, state: "open" }, "refresh"),
    surface(
      "a surface whose record lags, by its record's head",
      { number: NUMBER, head: lagging, state: "open" },
      "refresh",
    ),
    surface(
      "a stack menu, by no head and no state",
      { number: NUMBER, head: null, state: null },
      "refresh",
    ),
  ];
  const [pullsTab, otherTab, , behind] = surfaces;
  /** Many turns: every surface asks, then the browser runs idle callbacks and lands reads in
   * a shuffled order, until nothing waits. */
  const turns = async () => {
    for (let turn = 0; turn < 6; turn += 1) {
      for (const each of shuffled(surfaces)) {
        each.lane[each.ask]([each.row], SOURCE);
      }
      while (idle.length > 0 || landing.length > 0) {
        const queue = landing.length === 0 || (idle.length > 0 && random() < 0.5) ? idle : landing;
        const [next] = queue.splice(Math.floor(random() * queue.length), 1);
        next();
        await settle();
      }
    }
  };
  const changes = [];
  const change = async (what, act, expected) => {
    reads = 0;
    await act();
    await turns();
    assert.ok(reads <= 1, `${what}: read ${reads} times`);
    assert.equal(reads, expected, what);
    changes.push({
      change: what,
      reads,
      draws: Object.fromEntries(
        surfaces.map((each) => [each.name, said(each.lane.readiness(each.row, SOURCE))]),
      ),
    });
  };
  const scanAt = recorded.scanned.body.scan.at;
  const laterScan = recorded.scan_ended_elsewhere.body.status_scan_at;
  await change("drawn first, and again and again", () => {}, 1);
  await change("drawn again and again, nothing changed", () => {}, 0);
  await change(
    "the list's ask says the scan started",
    () => pullsTab.lane.scanned("started", scanAt),
    1,
  );
  await change("an ask says a scan ended", () => pullsTab.lane.scanned("not_due", laterScan), 1);
  await change(
    "another tab's ask says that same scan ended",
    () => otherTab.lane.scanned("not_due", laterScan),
    0,
  );
  await change(
    "a pull request page reads its status, newer than the answer's, and again as it polls",
    () => {
      const read = new Date(Date.parse(laterScan) + 60_000).toISOString().replace(".000Z", "Z");
      index.heard(SOURCE, NUMBER, read);
      index.heard(SOURCE, NUMBER, read);
    },
    1,
  );
  await change(
    "a minute passes",
    () => {
      now += ROW_READINESS_RETRY_MS;
    },
    1,
  );
  await change(
    "the list names a new head, which both Pulls tabs draw",
    () => {
      phase = "pushed";
      pullsTab.row = { ...pullsTab.row, head: after.head };
      otherTab.row = { ...otherTab.row, head: after.head };
    },
    1,
  );
  await change(
    "the lagging record catches up with that head",
    () => {
      behind.row = { ...behind.row, head: after.head };
    },
    0,
  );
  for (const each of surfaces) {
    each.lane.dispose();
  }
  return changes;
}

(async () => {
  const readiness = await import(pathToFileURL(path.join(GITHUB, "row-readiness.js")).href);
  const lane = await laneStory(readiness);
  const { steps: panel, invariants } = await panelStory();
  const menu = await menuStory(readiness);
  const reads = await readsStory(readiness);
  // This script prints the lane's story, and github-pulls-readiness-surfaces-session.js,
  // which runs this same session with `--part surfaces`, the rest, each a transcript's
  // command of its own (cli-ui-github-pulls-readiness.tryscript.md), since the whole in one
  // command is larger than the regular expression tryscript's matcher compiles. `--part all`
  // prints everything, as tests/test_github_pulls_readiness_session.py reads it.
  const all = { lane, panel, menu, reads, invariants: { panel: invariants } };
  const part = process.argv.indexOf("--part");
  const wanted = part === -1 ? "lane" : process.argv[part + 1];
  const chosen =
    wanted === "all"
      ? all
      : wanted === "surfaces"
        ? { panel, menu, reads, invariants: all.invariants }
        : { lane };
  process.stdout.write(`${JSON.stringify(chosen, null, 2)}\n`);
})().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
