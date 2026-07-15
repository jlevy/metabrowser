const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const listeners = [];
let chartDisposeCalls = 0;
let chartRenderCalls = 0;

const filterBar = {
  addEventListener: (type) => listeners.push(type),
};
const container = {
  innerHTML: "",
  querySelector: (selector) => (selector === ".filter-bar" ? filterBar : null),
};
const document = {
  createElement: () => ({ appendChild: () => {} }),
  documentElement: {},
  querySelector: () => null,
  querySelectorAll: () => [],
};
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
  "src/metabrowser/static/plugin_sdk.js",
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
    events: [{ kind: hostileKind, summary: "safe", raw: {} }],
    summary: {},
  },
});
const securityResult = {
  hasDelegatedClick: listeners.includes("click"),
  hasInlineKindHandler: container.innerHTML.includes("toggleKindFilter("),
  hasRawImage: container.innerHTML.includes("<img"),
  hasEscapedImage: container.innerHTML.includes("&lt;img"),
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
    }),
  );
})().catch((error) => {
  process.stderr.write(String(error?.stack || error));
  process.exitCode = 1;
});
