const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const listeners = {};
let chartDisposeCalls = 0;
let chartRenderCalls = 0;
const chartRenderPayloads = [];

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
  renderPayload: (target, payload) => {
    chartRenderCalls += 1;
    chartRenderPayloads.push({ container: target.name || "primary", id: payload.id });
  },
};

vm.createContext(sandbox);
for (const relative of [
  "src/metabrowser/static/request-error.js",
  "src/metabrowser/static/formatters.js",
  "src/metabrowser/static/inventory-scope.js",
  "src/metabrowser/static/resource-context.js",
  "src/metabrowser/static/view-state.js",
  "src/metabrowser/static/navigation.js",
  "src/metabrowser/static/plugin-sdk.js",
  "src/metabrowser/static/filter-controls.js",
  "src/metabrowser/static/icons.js",
  "src/metabrowser/builtin_plugins/agent_log/index.js",
]) {
  const filename = path.join(repoRoot, relative);
  const source = fs.readFileSync(filename, "utf8");
  vm.runInContext(source, sandbox, { filename });
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
function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

(async () => {
  // The plugin data and the independent chart bundle must share the wait,
  // rather than placing the bundle behind the network response.
  const firstData = deferred();
  const firstAsset = deferred();
  let dataStarts = 0;
  let assetStarts = 0;
  sandbox.metabrowser.fetchPluginData = () => {
    dataStarts += 1;
    return firstData.promise;
  };
  sandbox.metabrowser.ensureAsset = () => {
    assetStarts += 1;
    return firstAsset.promise;
  };
  const pendingRender = chartsView.render(container, { path: "events.jsonl" });
  await Promise.resolve();
  const independentWorkOverlaps = dataStarts === 1 && assetStarts === 1;
  chartsView.dispose(container);
  firstData.resolve({ id: "disposed" });
  firstAsset.resolve();
  await pendingRender;

  // Reopening the same view creates a new generation even when the path is
  // identical. The older response must not replace the newer render.
  const sameContainerRequests = [];
  sandbox.metabrowser.fetchPluginData = () => {
    const request = deferred();
    sameContainerRequests.push(request);
    return request.promise;
  };
  sandbox.metabrowser.ensureAsset = () => Promise.resolve();
  const older = chartsView.render(container, { path: "events.jsonl" });
  const newer = chartsView.render(container, { path: "events.jsonl" });
  sameContainerRequests[1].resolve({ id: "newer" });
  await newer;
  sameContainerRequests[0].resolve({ id: "older" });
  await older;

  // Separate staged containers are separate owners. Preparing a replacement
  // alongside the active chart must not cancel or redirect either payload.
  const left = { ...container, name: "left" };
  const right = { ...container, name: "right" };
  const separateRequests = [];
  sandbox.metabrowser.fetchPluginData = () => {
    const request = deferred();
    separateRequests.push(request);
    return request.promise;
  };
  const leftRender = chartsView.render(left, { path: "left.jsonl" });
  const rightRender = chartsView.render(right, { path: "right.jsonl" });
  separateRequests[0].resolve({ id: "left" });
  separateRequests[1].resolve({ id: "right" });
  await Promise.all([leftRender, rightRender]);

  process.stdout.write(
    `${JSON.stringify(
      {
        chartDisposeCalls,
        chartRenderCalls,
        chartRenderPayloads,
        independentWorkOverlaps,
        ...securityResult,
        ...filterRestoreResult,
        ...unknownKindResult,
        ...singleKindResult,
      },
      null,
      2,
    )}\n`,
  );
})().catch((error) => {
  process.stderr.write(String(error?.stack || error));
  process.exitCode = 1;
});
