// Browserless check: a live tail's batch of agent-log events (app.js appendLiveEvents).
//
// The rows are drawn with the agent-log renderers' exported renderLogEvent once the agents
// plugin's `loadLogRenderers` settles, and the `appendLiveEvents` measure covers that
// render, not only the bookkeeping before it. A load that fails is said once on the
// console, however many batches arrive. `appendLiveEvents` is lifted verbatim from
// app.js, which cannot load without a document. Prints a JSON record; exits 1 on a
// failed invariant.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const appSource = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/app.js"), "utf8");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function lift(pattern, what) {
  const match = appSource.match(pattern);
  assert(match, `${what} was not found in app.js`);
  return match[0];
}

(async () => {
  const measures = [];
  const warnings = [];
  const pane = {
    style: { display: "" },
    html: "",
    insertAdjacentHTML(position, html) {
      assert(position === "beforeend", `rows were inserted at ${position}`);
      this.html += html;
    },
  };
  // The renderers' load, which each step holds open, settles, or fails.
  let load;
  const sandbox = {
    Array,
    Promise,
    console: { warn: (...args) => warnings.push(String(args[0])) },
    fileCache: new Map([["log.jsonl", { events: [{}], bytes_read: 10 }]]),
    queryHtml: (selector) => (selector === '[data-tab-content="log"]' ? pane : null),
    _perf: {
      measureAsync(label, fn, meta) {
        const record = { label, events: meta.events_appended, settled: false };
        measures.push(record);
        return Promise.resolve(fn()).finally(() => {
          record.settled = true;
          record.rowsWhenSettled = pane.html;
        });
      },
    },
    window: {
      metabrowser: {
        plugins: {
          load(name) {
            assert(name === "agents", `plugins.load asked for ${name}`);
            return Promise.resolve({ loadLogRenderers: () => load });
          },
        },
      },
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(
    `${lift(/\nvar liveEventsUndrawnLogged = false;/, "liveEventsUndrawnLogged")}\n${lift(
      /\nfunction appendLiveEvents\(path, batch\) \{[\s\S]*?\n\}/,
      "appendLiveEvents",
    )}`,
    sandbox,
    { filename: "app.js (lifted)" },
  );

  const agentLog = {
    renderLogEvent: (_pane, event, index) => `<row ${index}:${event.kind}>`,
  };
  let resolveLoad;
  load = new Promise((resolve) => {
    resolveLoad = resolve;
  });
  const drawn = sandbox.appendLiveEvents("log.jsonl", {
    events: [{ kind: "a" }, { kind: "b" }],
    cursor: 30,
  });
  const beforeLoad = { ...measures[0] };
  resolveLoad(agentLog);
  await drawn;
  const record = {
    "the measure is open until the rows are drawn": {
      settledBeforeTheLoad: beforeLoad.settled,
      rowsWhenSettled: measures[0].rowsWhenSettled,
      cursor: sandbox.fileCache.get("log.jsonl").bytes_read,
    },
  };
  assert(!beforeLoad.settled, "the measure ended before the plugin loaded");
  assert(
    measures[0].rowsWhenSettled === "<row 1:a><row 2:b>",
    "the measure ended before the rows were drawn",
  );

  load = Promise.reject(new Error("agent-log did not load"));
  load.catch(() => {});
  await sandbox.appendLiveEvents("log.jsonl", { events: [{ kind: "c" }] });
  await sandbox.appendLiveEvents("log.jsonl", { events: [{ kind: "d" }] });
  record["a failed load is said once"] = { warnings };
  assert(warnings.length === 1, `a failed load was said ${warnings.length} times`);
  assert(pane.html === "<row 1:a><row 2:b>", "a failed load drew rows");

  process.stdout.write(`${JSON.stringify(record, null, 2)}\n`);
})().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
