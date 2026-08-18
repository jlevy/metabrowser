const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const listeners = {};
let chartDisposeCalls = 0;
let chartRenderCalls = 0;

const dynamicChipAttributes = new Map([
  ["data-chip-key", "agent-event-kind"],
  ["data-chip-value", "queue-operation"],
  ["aria-pressed", "true"],
]);
const dynamicGroup = {
  getAttribute: (name) => (name === "data-select" ? "many" : null),
};
const dynamicChip = {
  getAttribute: (name) => dynamicChipAttributes.get(name) || null,
  setAttribute: (name, value) => dynamicChipAttributes.set(name, String(value)),
  closest: (selector) => {
    if (selector === "[data-chip-key]") {
      return dynamicChip;
    }
    if (selector === ".chip-group") {
      return dynamicGroup;
    }
    return null;
  },
};
const dynamicEvent = { dataset: { kind: "queue-operation" }, style: { display: "" } };
const dynamicUnknownEvent = { dataset: { kind: "unknown" }, style: { display: "" } };
const container = {
  innerHTML: "",
  addEventListener: (type, listener) => {
    listeners[type] = listener;
  },
  removeEventListener: () => {},
  contains: () => true,
  querySelector: () => null,
  querySelectorAll: (selector) => {
    if (selector.includes("data-chip-key")) {
      return [dynamicChip];
    }
    if (selector === ".log-event[data-kind]") {
      return [dynamicEvent, dynamicUnknownEvent];
    }
    return [];
  },
};
const document = {
  addEventListener: () => {},
  removeEventListener: () => {},
  createElement: () => ({ appendChild: () => {} }),
  documentElement: {},
  querySelector: () => null,
  querySelectorAll: () => [],
};
container.ownerDocument = document;
const sandbox = {
  console,
  document,
  fetch: async () => ({ ok: true, json: async () => ({}) }),
  HTMLCanvasElement: function HTMLCanvasElement() {},
  Map,
  Promise,
  Set,
  URL,
  setTimeout,
  clearTimeout,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.MetabrowserCharts = {
  dispose: () => {
    chartDisposeCalls += 1;
  },
  renderPayload: () => {
    chartRenderCalls += 1;
  },
};

vm.createContext(sandbox);
for (const relative of [
  "src/metabrowser/static/request_error.js",
  "src/metabrowser/static/formatters.js",
  "src/metabrowser/static/inventory_scope.js",
  "src/metabrowser/static/resource_context.js",
  "src/metabrowser/static/view_state.js",
  "src/metabrowser/static/navigation.js",
  "src/metabrowser/static/plugin_sdk.js",
  "src/metabrowser/static/filter_controls.js",
  "src/metabrowser/static/icons.js",
  "src/metabrowser/builtin_plugins/agent_log/index.js",
]) {
  const source = fs.readFileSync(path.join(repoRoot, relative), "utf8");
  vm.runInContext(source, sandbox, { filename: relative });
}

const logView = sandbox.metabrowser.getRegisteredView("agent-log", "log");
const chartsView = sandbox.metabrowser.getRegisteredView("agent-log", "charts");
const hostileKind = 'custom"><img src=x onerror="globalThis.pwned=1">';
logView.render(container, {
  raw: {
    events: [
      { kind: hostileKind, summary: "safe", raw: {} },
      { kind: "queue-operation", summary: "queued", raw: {} },
      { kind: "unknown", summary: "[unknown] unclassified", raw: {} },
    ],
    summary: {},
  },
});
if (listeners.click) {
  listeners.click({ target: dynamicChip });
}
const securityResult = {
  hasDelegatedClick: typeof listeners.click === "function",
  hasInlineKindHandler: container.innerHTML.includes("toggleKindFilter("),
  hasRawImage: container.innerHTML.includes("<img"),
  hasEscapedImage: container.innerHTML.includes("&lt;img"),
  usesSharedMultiSelect: container.innerHTML.includes('data-select="many"'),
  usesWrappedChipCluster: container.innerHTML.includes('data-layout="wrap"'),
  dynamicStartsPressed: container.innerHTML.includes(
    'data-chip-value="queue-operation" aria-pressed="true"',
  ),
  dynamicEndsUnpressed: dynamicChip.getAttribute("aria-pressed") === "false",
  dynamicEventHidden: dynamicEvent.style.display === "none",
  unknownEventHiddenWhenFiltering: dynamicUnknownEvent.style.display === "none",
  mixedUnknownKindHasNoChip: !container.innerHTML.includes('data-chip-value="unknown"'),
  dynamicLabelIsReadable: container.innerHTML.includes(">queue operation (1)</button>"),
};
if (listeners.click) {
  listeners.click({ target: dynamicChip });
}
const filterRestoreResult = {
  unknownEventRestoredWithAllKinds: dynamicUnknownEvent.style.display === "",
};

logView.render(container, {
  raw: {
    events: [{ kind: "unknown", summary: "[unknown] visible value", raw: {} }],
    summary: {},
  },
});
const unknownKindResult = {
  unknownKindLabelHidden: !container.innerHTML.includes("log-event-kind"),
  unknownSummaryLabelHidden: !container.innerHTML.includes("[unknown]"),
  unknownSummaryValueVisible: container.innerHTML.includes("visible value"),
  unknownFilterHidden: !container.innerHTML.includes("agent-log-filter-bar"),
};

logView.render(container, {
  raw: {
    events: [{ kind: "text", summary: "[text] one event", raw: {} }],
    summary: {},
  },
});
const singleKindResult = {
  singleKnownKindVisible: container.innerHTML.includes(">text</span>"),
  singleKindFilterHidden: !container.innerHTML.includes("agent-log-filter-bar"),
};
let resolveChartFetch;
sandbox.location = { origin: "http://127.0.0.1:8411" };
sandbox.fetch = () =>
  new Promise((resolve) => {
    resolveChartFetch = resolve;
  });

(async () => {
  const pendingRender = chartsView.render(container, { path: "events.jsonl" });
  chartsView.dispose();
  resolveChartFetch({ ok: true, json: async () => ({ series: [] }) });
  await pendingRender;

  process.stdout.write(
    JSON.stringify({
      chartDisposeCalls,
      chartRenderCalls,
      ...securityResult,
      ...filterRestoreResult,
      ...unknownKindResult,
      ...singleKindResult,
    }),
  );
})().catch((error) => {
  process.stderr.write(String(error?.stack || error));
  process.exitCode = 1;
});
