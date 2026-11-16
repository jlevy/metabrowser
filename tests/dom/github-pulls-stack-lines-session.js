// Browserless session: each stack heading's brief change line in the Pulls tab (mb-9ekj),
// through the production code.
//
// builtin_plugins/github/stack-lines.js decides what a stack's heading shows of its change
// line, its combined change, the top's head against the base branch, which the server sums
// (`GET stack-change`): the shell's pending placeholder while the line is read, the line once
// it is, and nothing where it cannot be had. It reads the stacks the list draws, one at a time
// when the browser is idle, within the Pulls tab's hourly cap, and keeps each answer in the
// document's comparison keep under the stack's two commits. Its answers are the server's: the
// stack changes in tests/fixtures/github-stack-change-responses.json, which
// tests/test_github_stack_change.py records from the real route, and the lists and stack
// snapshot the stack-groups session replays.
//
// `lane` drives the lane alone over those answers, with the browser's idle time and its
// clock in the session's hands, and prints what each heading shows at each step and what was
// asked. `heading` mounts the production panel over a stand-in for the DOM with the SDK's own
// painters (tests/dom/sdk-ref-fixture.js) and prints the heading of each stack in its three
// states: waiting, its line arrived, and unavailable, with its parts as drawn and its
// accessible name. `invariants` are the relations every step holds.

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
const SOURCE = "https://github.com/octo/demo";

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
 * session's, and every request it sends logged.
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
  const repaints = [];
  const deps = (budget) => ({
    keep,
    index,
    budget,
    async read(number) {
      asked.push(`GET /api/plugin/github/stack-change?number=${number}`);
      const answer = answers(number);
      if (answer instanceof Error) {
        throw answer;
      }
      return { status: answer.status, body: answer.body };
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
  const shared = stacks.shared.body.stacks.map(({ number, pulls }) => ({ number, pulls }));
  const budget = prefetch.createWarmBudget(() => now);
  let lane = createStackLines(deps(budget));
  const steps = [];
  /** Run the browser's idle callbacks, and what each read leads to, until none is left. */
  const runIdle = async () => {
    while (idle.length > 0) {
      idle.shift()();
      await settle();
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

  await step("the list draws #286 and #290: each heading waits, nothing is read yet", () =>
    lane.want(shared, SOURCE),
  );
  assert.equal(idle.length, 1, "one read waits for idle at a time");
  await step("the browser is idle: each is read in turn, #286 summed, #290 not cached", runIdle);
  const kept = changes.current.body;
  const key = stackChangeKey(kept.base, kept.head);
  assert.deepEqual(keep.snapshot().kept, [key], "the change is kept under its two commits");
  await step("drawn again: the line in the paint that draws it, and nothing is read", () =>
    lane.want(shared, SOURCE),
  );
  assert.equal(idle.length, 0);
  // A Pulls tab mounted again in the document: its lane shares the document's keep and index.
  lane.dispose();
  lane = createStackLines(deps(budget));
  await step("a Pulls tab mounted again: the line at once, from the keep", () =>
    lane.want(shared, SOURCE),
  );
  assert.equal(idle.length, 0, "a remount reads nothing");
  now += kept.fresh_for_s * 1000;
  await step("its window passed: each is read again, the line it had shown meanwhile", () =>
    lane.want(shared, SOURCE),
  );
  answers = (number) =>
    number === 286 ? { status: 500, body: { error: "boom" } } : answerFor(number);
  keep.clear();
  await step("the keep let it go and the read failed: no line, and no placeholder", runIdle);
  now += STACK_LINE_RETRY_MS;
  answers = (number) => answerFor(number);
  await step("a minute on, the failed read is asked again", async () => {
    lane.want(shared, SOURCE);
    await runIdle();
  });
  // A server that serves no GitHub repository refuses every stack: one answer says so.
  keep.clear();
  index.clear();
  answers = () => changes.not_github;
  await step("a server with no repository: one refusal, and no heading waits", async () => {
    lane.want(shared, SOURCE);
    await runIdle();
  });
  // The Pulls tab's hourly cap, which its comparison warms count against too.
  index.clear();
  const spent = prefetch.createWarmBudget(() => now, 0);
  lane.dispose();
  lane = createStackLines(deps(spent));
  await step("the hour's cap is spent: nothing is read, and no heading waits", async () => {
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
  /** The stack changes the server answers, by stack. */
  const changeFor = (number) => answerFor(number);
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
        return respond(answer.body, answer.status);
      }
      if (route.startsWith("/api/plugin/github/pulls?")) {
        return respond(listed);
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
    const stackRows = () =>
      list.childNodes
        .filter((item) => item.classList.contains("github-pulls-stack-item"))
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
    /** Each stack's heading as drawn: its label, its change slot, and its row's name. */
    const headings = () =>
      Object.fromEntries(
        stackRows().map((row) => {
          const heading = childByClass(row, "github-pulls-stack-heading");
          const label = childByClass(heading, "github-pull-stack-label");
          const change = childByClass(heading, "github-pulls-stack-change");
          return [
            `Stack #${row.dataset.stack}`,
            {
              heading: heading.childNodes.map((node) => node.className),
              label: label.textContent,
              text: textOf(change),
              change: shape(change.childNodes),
              name: row.getAttribute("aria-label"),
            },
          ];
        }),
      );
    const runIdle = async () => {
      while (idle.length > 0) {
        idle.shift()();
        await paint();
      }
    };
    const steps = [];
    await paint();
    steps.push({
      step: "mounted: each heading holds the pending placeholder; the browser is not idle yet",
      headings: headings(),
      requests: requests.splice(0),
    });
    // The placeholder and the label are the nodes the arrival keeps or replaces in place.
    const row286 = stackRows().find((row) => row.dataset.stack === "286");
    const labelBefore = childByClass(
      childByClass(row286, "github-pulls-stack-heading"),
      "github-pull-stack-label",
    );
    const pendingBefore = childByClass(
      childByClass(row286, "github-pulls-stack-heading"),
      "github-pulls-stack-change",
    ).childNodes[0];
    await paint();
    assert.equal(
      childByClass(childByClass(row286, "github-pulls-stack-heading"), "github-pulls-stack-change")
        .childNodes[0],
      pendingBefore,
      "the placeholder is one node across paints, so its quiet period and pulse run once",
    );
    await runIdle();
    const arrived = headings();
    steps.push({
      step: "idle: #286's line arrives in its heading, and #290's cannot be had",
      headings: arrived,
      requests: requests.splice(0),
    });
    const heading286 = childByClass(row286, "github-pulls-stack-heading");
    assert.equal(
      childByClass(heading286, "github-pull-stack-label"),
      labelBefore,
      "the label stays",
    );
    // The line is the shell's one component, through the SDK: the same nodes, part for part.
    const { stackLineInput } = await import(
      pathToFileURL(path.join(GITHUB, "stack-lines.js")).href
    );
    const tree = await sdk.loadChangedFilesTree();
    const said = sdk.changeLine(stackLineInput(changes.current.body, tree.statusBreakdown));
    const expected = shape([
      ...sdk.countPartsNodes([{ separator: "·" }]),
      ...sdk.changeLineNodes(said),
    ]);
    assert.deepEqual(arrived["Stack #286"].change, expected, "the heading draws the component");
    assert.equal(arrived["Stack #286"].name.startsWith(`Stack #286: ${said.label}; `), true);
    handle.dispose();
    for (const [name, descriptor] of Object.entries(saved)) {
      if (descriptor === undefined) {
        delete globalThis[name];
      } else {
        Object.defineProperty(globalThis, name, descriptor);
      }
    }
    return { steps, said: { text: said.text, label: said.label } };
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

(async () => {
  const lines = await import(pathToFileURL(path.join(GITHUB, "stack-lines.js")).href);
  const prefetch = await import(pathToFileURL(path.join(GITHUB, "comparison-prefetch.js")).href);
  const lane = await laneStory(lines, prefetch);
  // Every step: a heading waits only while a read of it is coming or queued, and a shown line
  // is the recorded summed change.
  for (const step of lane) {
    for (const [stack, shown] of Object.entries(step.shows)) {
      if (shown === "waiting") {
        assert.ok(
          step.lane.queue.includes(Number(stack.slice(7))) || step.lane.running !== null,
          `${step.step}: ${stack} waits for a read that is coming`,
        );
      }
    }
  }
  const heading = await headingStory();
  process.stdout.write(`${JSON.stringify({ lane, heading, invariants: true }, null, 2)}\n`);
})().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
