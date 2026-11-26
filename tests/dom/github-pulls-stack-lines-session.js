// Browserless session: each stack's brief change line in the Pulls tab (mb-9ekj), on its
// Stack Overview row (mb-tvhs), through the production code.
//
// builtin_plugins/github/stack-lines.js decides what a stack's Stack Overview row shows of its
// change line, its combined change, its members' own changes accumulated, which the server sums
// (`GET stack-change`): the shell's pending placeholder while the read of its stack is on
// its way, the line once it is, and nothing where it cannot be had. It reads the stacks the
// list draws, one at a time when the browser is idle, once for each stack's members and
// their heads, within the lines' own hourly cap, and keeps each answer in the document's
// comparison keep under its stack and its revision. Its answers are the server's: the stack
// changes in tests/fixtures/github-stack-change-responses.json, which
// tests/test_github_stack_change.py records from the real route, and the lists and stack
// snapshot the stack-groups session replays.
//
// `lane` drives the lane alone over those answers, with the browser's idle time, its clock,
// and when each read is answered in the session's hands, and prints what each stack shows
// at each step and what was asked. `heading` mounts the production panel over a stand-in
// for the DOM with the SDK's own painters (tests/dom/sdk-ref-fixture.js) and prints each
// stack's heading, which is whole from its first paint, its label, its size, and its age,
// and waits on no read, and its Stack Overview row in its three states: waiting, its line
// arrived, and unavailable, with its parts as drawn and its accessible name, then, in a fresh document each, its line
// with totals that are zero or not known: a total of zero is left out, and a change of no
// lines is "0 lines" (mb-efum). `invariants` are the relations every step holds.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { FakeElement, FakeNode } = require("./pulls-test-dom.js");

const root = path.resolve(__dirname, "../..");
const GITHUB = path.join(root, "src/metabrowser/builtin_plugins/github");
const changes = require("../fixtures/github-stack-change-responses.json");
const stacks = require("../fixtures/github-stacks-responses.json");
const lists = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/github-pulls-panel-responses.json"), "utf8"),
);
// The recording holds each distinct window of rows once; `same_as` names the answer that has it.
const rowsOf = (rows) =>
  Array.isArray(rows)
    ? rows.map((row) => JSON.parse(row))
    : [rows.same_as].flat().flatMap((holder) => rowsOf(lists[holder].body.rows));
const listed = { ...lists.current.body, rows: rowsOf(lists.current.body.rows) };
const more = { ...lists.more_window.body, rows: rowsOf(lists.more_window.body.rows) };
const SOURCE = "https://github.com/octo/demo";
// A head the catalog reports once a stack's top has moved: no commit of the recording.
const MOVED = "1".repeat(40);
const MOVED_AGAIN = "2".repeat(40);

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/** The server's answer for stack *number*, as the recording has it. */
function answerFor(number) {
  const found = Object.values(changes).find((answer) => answer.body.number === number);
  return found ?? changes.not_stacked;
}

/**
 * The lane alone: the browser's idle callbacks queued for the session to run, its clock the
 * session's, each read answered when the session lets it be, and every request it sends
 * logged.
 */
async function laneStory(lines, prefetch) {
  const { createStackLines, stackChangeKey, STACK_LINE_RETRY_MS, createStackLineIndex } = lines;
  const keep = prefetch.createComparisonKeep({ later: (callback) => callback() });
  const index = createStackLineIndex();
  let now = 1_000_000;
  /** @type {(() => void)[]} */
  let idle = [];
  const asked = [];
  let answers = (number) => answerFor(number);
  /** Reads on their way, each answered when the session runs it. */
  const held = [];
  const repaints = [];
  const deps = (budget) => ({
    keep,
    index,
    ...(budget === undefined ? {} : { budget }),
    read(number) {
      asked.push(`GET /api/plugin/github/stack-change?number=${number}`);
      return new Promise((resolve, reject) => {
        held.push(() => {
          const answer = answers(number);
          if (answer instanceof Error) {
            reject(answer);
          } else {
            resolve({ status: answer.status, body: answer.body });
          }
        });
      });
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
    changed: (number) => repaints.push(number),
  });
  // Each stack as the list draws it: its members, and each one's head from the recorded rows.
  const heads = new Map(
    [...listed.rows, ...more.rows].map((row) => [row.number, row.head_oid ?? null]),
  );
  let shared = stacks.shared.body.stacks.map(({ number, pulls }) => ({
    number,
    pulls,
    heads: pulls.map((member) => heads.get(member) ?? null),
  }));
  /** The list with stack *number*'s member at *at*, its top unless named, moved to *head*. */
  const moved = (number, head, at = -1) => {
    shared = shared.map((stack) =>
      stack.number === number
        ? { ...stack, heads: stack.heads.with(at < 0 ? stack.heads.length + at : at, head) }
        : stack,
    );
  };
  let lane = createStackLines(deps());
  const steps = [];
  /** The next idle callback, and what it leads to. */
  const idleOnce = async () => {
    idle.shift()?.();
    await settle();
  };
  /** Answer the reads on their way. */
  const answer = async () => {
    for (const release of held.splice(0)) {
      release();
    }
    await settle();
  };
  /** Run the browser's idle callbacks, and answer each read, until none is left. */
  const runIdle = async () => {
    while (idle.length > 0 || held.length > 0) {
      await idleOnce();
      await answer();
    }
  };
  const shows = () =>
    Object.fromEntries(
      shared.map((stack) => {
        const line = lane.line(stack, SOURCE);
        return [
          `Stack #${stack.number}`,
          line.phase === "shown"
            ? `shown ${line.change.files} files, +${line.change.additions} −${line.change.deletions}`
            : line.phase,
        ];
      }),
    );
  const step = async (what, act) => {
    asked.length = 0;
    repaints.length = 0;
    await act();
    steps.push({
      step: what,
      shows: shows(),
      asked: [...asked],
      ...(repaints.length > 0 ? { repainted: [...repaints] } : {}),
      lane: lane.snapshot(),
    });
  };

  await step("the list draws #286 and #290: nothing is read yet, and no heading waits", () =>
    lane.want(shared, SOURCE),
  );
  assert.equal(idle.length, 1, "one read waits for idle at a time");
  await step("the browser is idle: #286's read is sent, and only its heading waits", idleOnce);
  await step("#286's line arrives, and #290's read is sent: its heading waits now", async () => {
    await answer();
    await idleOnce();
  });
  await step(
    "#290's answer: a member's list is not cached, and it names it: no line, asked again later",
    answer,
  );
  const kept = changes.current.body;
  const key = stackChangeKey(kept.number, kept.revision);
  assert.deepEqual(keep.snapshot().kept, [key], "the change is kept under its stack and revision");
  await step(
    "drawn again within the minute: the line in the paint that draws it, nothing read",
    () => lane.want(shared, SOURCE),
  );
  assert.equal(idle.length, 0);
  // A Pulls tab mounted again in the document: its lane shares the document's keep and index.
  lane.dispose();
  lane = createStackLines(deps());
  await step("a Pulls tab mounted again: the line at once, from the keep", () =>
    lane.want(shared, SOURCE),
  );
  assert.equal(idle.length, 0, "a remount reads nothing");
  now += STACK_LINE_RETRY_MS;
  await step(
    "a minute on, #290 is asked again, silently; still not cached, it waits longer",
    async () => {
      lane.want(shared, SOURCE);
      await idleOnce();
      assert.equal(lane.line(shared[1], SOURCE).phase, "none", "a stack still settling waits not");
      await answer();
    },
  );
  // A filter that holds no row of #286's top leaves its head unknown: unchanged (B3).
  moved(286, null);
  await step("a filter holds no row of #286's top: nothing is read again", () =>
    lane.want(shared, SOURCE),
  );
  assert.equal(idle.length, 0, "an unknown head is no move");
  // The prefetch lists #290's member: the stacks that hold it are read at once (B1).
  answers = (number) => (number === 290 ? changes.arrived : answerFor(number));
  await step(
    "the prefetch lists a member of #290: it is read at once, and its line arrives",
    async () => {
      lane.listed(shared[1].pulls.at(-1));
      await runIdle();
    },
  );
  now += 3_600_000;
  await step("an hour on, every stack settled: nothing is read, and no heading waits", () =>
    lane.want(shared, SOURCE),
  );
  assert.equal(idle.length, 0, "a settled answer is not read again on a timer");
  // Any member's change moves the accumulation: here one below the top, whose list is still
  // of the head before, so the answer names it.
  moved(286, MOVED, 1);
  answers = (number) =>
    number === 286 ? changes.moving : number === 290 ? changes.arrived : answerFor(number);
  await step(
    "a member of #286 moves: read again, the line stays; its list is still settling",
    async () => {
      lane.want(shared, SOURCE);
      await runIdle();
    },
  );
  now += STACK_LINE_RETRY_MS;
  answers = (number) => (number === 290 ? changes.arrived : answerFor(number));
  await step(
    "a minute on it is asked again, silently, and the refreshed list settles it",
    async () => {
      lane.want(shared, SOURCE);
      await idleOnce();
      assert.equal(lane.line(shared[0], SOURCE).phase, "shown", "the line stays while it settles");
      await answer();
    },
  );
  moved(286, MOVED_AGAIN);
  answers = (number) => (number === 286 ? new Error("connection dropped") : changes.arrived);
  await step("#286's top moves again and the read fails: the line it had stays shown", async () => {
    lane.want(shared, SOURCE);
    await runIdle();
  });
  await step("drawn again within the minute: the failed read is not asked again yet", () =>
    lane.want(shared, SOURCE),
  );
  assert.equal(idle.length, 0);
  now += STACK_LINE_RETRY_MS;
  answers = (number) => (number === 286 ? { status: 304, body: null } : changes.arrived);
  await step("a minute on it is asked again; a 304 says its last answer holds", async () => {
    lane.want(shared, SOURCE);
    await runIdle();
  });
  // The keep let the line go: the stack is read again, and that read fails.
  keep.clear();
  answers = (number) =>
    number === 286 ? { status: 500, body: { error: "boom" } } : changes.arrived;
  await step("the keep let the lines go and #286's read failed: no line, and no wait", async () => {
    lane.want(shared, SOURCE);
    await runIdle();
  });
  now += STACK_LINE_RETRY_MS;
  answers = (number) => (number === 290 ? changes.arrived : answerFor(number));
  await step(
    "a minute on, #286 is asked again, with no placeholder, and its line is back",
    async () => {
      lane.want(shared, SOURCE);
      await idleOnce();
      assert.equal(lane.line(shared[0], SOURCE).phase, "none", "a retry after a failure waits not");
      await answer();
    },
  );
  // A server that refuses every stack: one answer says so, and the lane asks a minute on.
  for (const [refusal, what] of [["not_github", "a server with no repository"]]) {
    keep.clear();
    index.clear();
    lane.dispose();
    lane = createStackLines(deps());
    answers = () => changes[refusal];
    await step(`${what}: one refusal, and no other stack is read`, async () => {
      lane.want(shared, SOURCE);
      await runIdle();
    });
    await step(`${what}, drawn again within the minute: nothing is read`, () =>
      lane.want(shared, SOURCE),
    );
    assert.equal(idle.length, 0);
    now += STACK_LINE_RETRY_MS;
    await step(`${what}, a minute on: one read, and no heading waits`, async () => {
      lane.want(shared, SOURCE);
      await runIdle();
    });
  }
  // The lines' own hourly cap, apart from the comparison warms'.
  index.clear();
  answers = (number) => answerFor(number);
  const spent = prefetch.createWarmBudget(() => now, 0);
  lane.dispose();
  lane = createStackLines(deps(spent));
  await step("the lines' hourly cap is spent: nothing is read, and no heading waits", async () => {
    lane.want(shared, SOURCE);
    await runIdle();
  });
  lane.dispose();
  return steps;
}

/**
 * Mount the production panel over a stand-in for the DOM on the recorded All list and the
 * shared stack snapshot, with the SDK's own painters and idle time in the session's hands,
 * and print each stack's heading as drawn at each step.
 */
async function headingStory() {
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
  /** The stack changes the server answers, by stack, each held until the session lets it go. */
  let changeFor = (number) => answerFor(number);
  /** @type {(() => void)[]} */
  const held = [];
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
      if (route.startsWith("/api/plugin/github/stack-change?")) {
        requests.push(route);
        const answer = changeFor(Number(new URL(route, "http://x").searchParams.get("number")));
        return new Promise((resolve) => held.push(resolve)).then(() =>
          respond(answer.body, answer.status),
        );
      }
      if (route.startsWith("/api/plugin/github/pulls?")) {
        return respond(route.includes("&after=") ? more : listed);
      }
      if (route === "/api/plugin/github/stacks") {
        return respond(stacks.shared.body);
      }
      if (route === "/api/plugin/github/pulls-prefetch") {
        return respond({ prefetch: "not_due" });
      }
      // A refresh, a record, or a pull request's files: nothing this story reads.
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
  try {
    let container = new PanelElement("div");
    const sdk = require("./sdk-ref-fixture.js").refHelpers(document);
    const mount = (into) =>
      panel.mountPullsPanel(
        into,
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
    let handle = mount(container);
    const listNode = () =>
      container.childNodes.find((node) => node.classList?.contains("github-pulls-list"));
    const stackRows = () =>
      listNode()
        .childNodes.filter((item) => item.classList.contains("github-pulls-stack-item"))
        .map((item) => item.childNodes[0]);
    const childByClass = (node, name) =>
      node.childNodes.find((child) => child.classList?.contains(name));
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
    /** A stack's Stack Overview row, the first row under its open stack. */
    const wholeRow = (stack) =>
      listNode()
        .childNodes.filter((item) => item.classList.contains("github-pulls-whole-item"))
        .map((item) => item.childNodes[0])
        .find((row) => row.dataset.stack === String(stack));
    /** A stack's toggle of its changed files, on its Stack Overview row's line (mb-odt4). */
    const toggleOf = (row) =>
      childByClass(
        childByClass(wholeRow(row.dataset.stack), "github-pulls-whole-line"),
        "github-pulls-whole-change",
      );
    /** A stack's change slot, in that toggle, before its chevron. */
    const changeOf = (row) => {
      const toggle = toggleOf(row);
      assert.deepEqual(
        toggle.childNodes.map((node) => node.className),
        ["github-pulls-stack-change", "github-pulls-toggle"],
        "the toggle is the change line's slot, then the chevron, whatever the slot holds",
      );
      return childByClass(toggle, "github-pulls-stack-change");
    };
    /**
     * Each stack as drawn. `heading` is its row: its text, its age, and its name, none of
     * which a read of the stack's change moves. The rest is its Stack Overview row: its change
     * slot and its name.
     */
    const headings = () =>
      Object.fromEntries(
        stackRows().map((row) => {
          const heading = childByClass(row, "github-pulls-stack-heading");
          const whole = wholeRow(row.dataset.stack);
          const change = changeOf(row);
          return [
            `Stack #${row.dataset.stack}`,
            {
              heading: {
                text: heading.childNodes.map(textOf).join(" "),
                age: textOf(childByClass(row, "github-pulls-age")),
                name: row.getAttribute("aria-label"),
              },
              text: textOf(change),
              change: shape(change.childNodes),
              name: whole.getAttribute("aria-label"),
            },
          ];
        }),
      );
    /**
     * The next idle callback that reads a stack, and the paint after it. A pull request's row
     * reads its own change line in the same idle time (row-lines.js), in a request this story
     * leaves unanswered, so a callback that reads no stack is run and passed over.
     */
    const idleOnce = async () => {
      const before = requests.length;
      while (idle.length > 0 && requests.length === before) {
        idle.shift()();
        await paint();
      }
    };
    /** Let the reads on their way be answered, and paint. */
    const release = async () => {
      for (const answer of held.splice(0)) {
        answer();
      }
      await paint();
    };
    const steps = [];
    await paint();
    const mountedHeadings = headings();
    steps.push({
      step: "mounted: no stack waits, since no read is sent; the browser is not idle yet",
      headings: mountedHeadings,
      requests: requests.splice(0),
    });
    /** Every step leaves each stack's heading as it was first drawn: the count and the age
     * are there at once, and no read of a stack's change moves or changes them. */
    const headingsHold = (drawn) => {
      for (const [stack, each] of Object.entries(drawn)) {
        assert.deepEqual(each.heading, mountedHeadings[stack].heading, `${stack}'s heading`);
      }
    };
    // The list draws #290 first. Its read is sent when the browser is idle, and only then
    // does its heading wait, its name saying so; #286's, queued behind it, does not.
    await idleOnce();
    steps.push({
      step: "idle: #290's read is sent, and its Stack Overview row waits; #286's is queued and does not",
      headings: headings(),
      requests: requests.splice(0),
    });
    const row290 = stackRows().find((row) => row.dataset.stack === "290");
    const pendingBefore = changeOf(row290).childNodes[0];
    await paint();
    assert.equal(
      changeOf(row290).childNodes[0],
      pendingBefore,
      "the placeholder is one node across paints, so its quiet period and pulse run once",
    );
    await release();
    await idleOnce();
    steps.push({
      step: "#290 has a member with no list, so it shows nothing; #286's read is sent, and it waits",
      headings: headings(),
      requests: requests.splice(0),
    });
    // The label, and the Stack Overview row's words, are the nodes the arrival keeps.
    const row286 = stackRows().find((row) => row.dataset.stack === "286");
    const wholeWords = () => childByClass(wholeRow(286), "github-pulls-whole-line").childNodes[0];
    const wordsBefore = wholeWords();
    const labelBefore = childByClass(
      childByClass(row286, "github-pulls-stack-heading"),
      "github-pull-stack-label",
    );
    await release();
    const arrived = headings();
    steps.push({
      step: "#286's line arrives on its Stack Overview row, and #290's shows nothing still",
      headings: arrived,
      requests: requests.splice(0),
    });
    for (const step of steps) {
      headingsHold(step.headings);
    }
    // Whatever is still left for idle time reads no stack.
    while (idle.length > 0) {
      idle.shift()();
      await paint();
    }
    assert.deepEqual(requests, [], "nothing more is read");
    const heading286 = childByClass(row286, "github-pulls-stack-heading");
    assert.equal(
      childByClass(heading286, "github-pull-stack-label"),
      labelBefore,
      "the label stays",
    );
    assert.equal(wholeWords(), wordsBefore, "the Stack Overview row's words stay");
    assert.equal(textOf(wordsBefore), "Stack Overview");
    // The line is the shell's one component, through the SDK: the same nodes, part for part,
    // of the stack's line totals alone, with no file statuses (mb-lqkb).
    const { stackLineInput } = await import(
      pathToFileURL(path.join(GITHUB, "stack-lines.js")).href
    );
    const said = sdk.changeLine(stackLineInput(changes.current.body));
    assert.deepEqual(said.statusParts ?? [], [], "the line counts no files by status");
    const expected = shape([
      ...sdk.countPartsNodes([{ separator: "·" }]),
      ...sdk.changeLineNodes(said),
    ]);
    assert.deepEqual(arrived["Stack #286"].change, expected, "the row draws the component");
    assert.equal(arrived["Stack #286"].name, `Stack Overview, Stack #286: ${said.label}`);
    handle.dispose();
    // Totals a member's list could not count, a binary file, are followed by the muted
    // "(estimated)", which the name says too (B4 of review B on #484): a fresh document.
    const lines = await import(pathToFileURL(path.join(GITHUB, "stack-lines.js")).href);
    const prefetch = await import(pathToFileURL(path.join(GITHUB, "comparison-prefetch.js")).href);
    lines.documentStackLines.clear();
    prefetch.documentComparisons.clear();
    changeFor = (number) => (number === 286 ? changes.inexact : answerFor(number));
    container = new PanelElement("div");
    handle = mount(container);
    await paint();
    while (idle.length > 0 || held.length > 0) {
      await idleOnce();
      await release();
    }
    const estimated = headings()["Stack #286"];
    steps.push({
      step: "a member's list could not count a binary file: “(estimated)” follows the totals",
      headings: { "Stack #286": estimated },
      requests: requests.splice(0),
    });
    assert.equal(estimated.change.at(-1).class, "github-pulls-stack-change-note");
    assert.equal(estimated.text.endsWith("(estimated)"), true);
    assert.match(estimated.name, /^Stack Overview, Stack #286: .+, estimated$/);
    handle.dispose();
    // A total of zero is left out, and a change of no lines is "0 lines", said "no lines
    // changed" (mb-efum): #286's answer with each of these totals, in a fresh document each.
    /** The totals a drawn line shows, each its class and text, from its shape. */
    const showsOf = (nodes) =>
      nodes.flatMap((node) =>
        typeof node === "string"
          ? []
          : node.class === "change-line-stats"
            ? node.children.map((total) => `${total.class}: ${total.children.join("")}`)
            : showsOf(node.children ?? []),
      );
    const totals = [];
    for (const total of [
      { additions: 0, deletions: 4 },
      { additions: 5, deletions: 4 },
      { additions: 0, deletions: 0 },
      { additions: 0, deletions: null },
      { additions: null, deletions: 4 },
      { additions: null, deletions: null },
    ]) {
      lines.documentStackLines.clear();
      prefetch.documentComparisons.clear();
      const answer = { ...changes.current, body: { ...changes.current.body, ...total } };
      changeFor = (number) => (number === 286 ? answer : answerFor(number));
      container = new PanelElement("div");
      handle = mount(container);
      await paint();
      while (idle.length > 0 || held.length > 0) {
        await idleOnce();
        await release();
      }
      requests.splice(0);
      const drawn = headings()["Stack #286"];
      const built = sdk.changeLine(stackLineInput(answer.body));
      assert.deepEqual(
        drawn.change,
        shape([...sdk.countPartsNodes([{ separator: "·" }]), ...sdk.changeLineNodes(built)]),
        `${JSON.stringify(total)}: the row draws the component with its zero totals left out`,
      );
      assert.equal(drawn.name, `Stack Overview, Stack #286: ${built.label}`);
      assert.ok(!/[+−]0\b/.test(drawn.text), `${JSON.stringify(total)}: no zero total shows`);
      totals.push({
        totals: total,
        text: drawn.text,
        shows: showsOf(drawn.change),
        name: drawn.name,
      });
      handle.dispose();
    }
    for (const [name, descriptor] of Object.entries(saved)) {
      if (descriptor === undefined) {
        delete globalThis[name];
      } else {
        Object.defineProperty(globalThis, name, descriptor);
      }
    }
    return { steps, said: { text: said.text, label: said.label }, totals };
  } catch (error) {
    for (const [name, descriptor] of Object.entries(saved)) {
      if (descriptor === undefined) {
        delete globalThis[name];
      } else {
        Object.defineProperty(globalThis, name, descriptor);
      }
    }
    throw error;
  }
}

/**
 * When a stack whose answer keeps naming a member not yet settled is asked again: a minute
 * on, then doubling, to the ceiling, then at the ceiling (review C of #484, C3). The minutes
 * of each read over two and a half hours, a want each minute, as a panel paints.
 */
async function retrySchedule(lines, prefetch) {
  const { createStackLines, createStackLineIndex, STACK_LINE_PENDING_MAX_MS } = lines;
  const keep = prefetch.createComparisonKeep({ later: (callback) => callback() });
  const start = 5_000_000;
  let now = start;
  const reads = [];
  const lane = createStackLines({
    keep,
    index: createStackLineIndex(),
    async read(number) {
      reads.push((now - start) / 60_000);
      return { status: 200, body: { ...changes.not_cached.body, number } };
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
  });
  /** @type {(() => void)[]} */
  let idle = [];
  const stack = { number: 290, pulls: [8, 9, 10], heads: [null, null, null] };
  for (let minute = 0; minute <= 150; minute += 1) {
    now = start + minute * 60_000;
    lane.want([stack], SOURCE);
    while (idle.length > 0) {
      idle.shift()();
      await settle();
    }
  }
  lane.dispose();
  assert.deepEqual(
    reads,
    [0, 1, 3, 7, 15, 31, 61, 91, 121, 151].filter((at) => at <= 150),
  );
  assert.equal(STACK_LINE_PENDING_MAX_MS, 30 * 60_000, "the ceiling is half an hour");
  return reads;
}

(async () => {
  const lines = await import(pathToFileURL(path.join(GITHUB, "stack-lines.js")).href);
  const prefetch = await import(pathToFileURL(path.join(GITHUB, "comparison-prefetch.js")).href);
  const lane = await laneStory(lines, prefetch);
  // Every step: a heading waits only while its own stack's read is on its way, never for a
  // read queued behind another, and at most one heading waits at a time.
  for (const step of lane) {
    const waiting = Object.entries(step.shows).filter(([, shown]) => shown === "waiting");
    assert.ok(waiting.length <= 1, `${step.step}: one heading waits at most`);
    for (const [stack] of waiting) {
      assert.equal(
        step.lane.running,
        Number(stack.slice(7)),
        `${step.step}: ${stack} waits for its own read on its way`,
      );
    }
  }
  const heading = await headingStory();
  const retries = await retrySchedule(lines, prefetch);
  process.stdout.write(
    `${JSON.stringify({ lane, heading, retryMinutes: retries, invariants: true }, null, 2)}\n`,
  );
})().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
