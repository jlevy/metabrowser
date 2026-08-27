const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const listeners = new Map();
const chartInstances = [];
let resolvedTheme = "light";

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.className = "";
    this.isConnected = true;
    this.textContent = "";
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  addEventListener() {}

  set innerHTML(_value) {
    this.children = [];
  }
}

class FakeCanvas extends FakeElement {
  constructor() {
    super("canvas");
  }
}

class FakeChart {
  constructor(canvas, config) {
    this.canvas = canvas;
    this.config = config;
    this.data = config.data;
    this.options = config.options;
    this.destroyCalls = 0;
    this.updateCalls = [];
    chartInstances.push(this);
  }

  destroy() {
    this.destroyCalls += 1;
  }

  update(mode) {
    this.updateCalls.push(mode);
  }
}

class FakeCustomEvent {
  constructor(type, options) {
    this.type = type;
    this.detail = options.detail;
  }
}

const document = {
  addEventListener() {},
  createElement(tagName) {
    return tagName === "canvas" ? new FakeCanvas() : new FakeElement(tagName);
  },
  documentElement: new FakeElement("html"),
};

const sandbox = {
  Chart: FakeChart,
  CustomEvent: FakeCustomEvent,
  HTMLCanvasElement: FakeCanvas,
  Map,
  Promise,
  Set,
  URL,
  console,
  document,
  getComputedStyle() {
    const tokens =
      resolvedTheme === "dark"
        ? {
            "--chart-grid": "dark-grid",
            "--chart-label-text": "dark-label",
            "--chart-series-info": "dark-series",
          }
        : {
            "--chart-grid": "light-grid",
            "--chart-label-text": "light-label",
            "--chart-series-info": "light-series",
          };
    return {
      getPropertyValue(name) {
        return tokens[name] || "";
      },
    };
  },
  addEventListener(type, listener) {
    const current = listeners.get(type) || new Set();
    current.add(listener);
    listeners.set(type, current);
  },
  removeEventListener(type, listener) {
    listeners.get(type)?.delete(listener);
  },
  dispatchEvent(event) {
    for (const listener of listeners.get(event.type) || []) {
      listener(event);
    }
  },
  location: { origin: "http://127.0.0.1:8411" },
  setTimeout,
  clearTimeout,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);
for (const relative of [
  "src/metabrowser/static/theme-state.js",
  "src/metabrowser/static/request-error.js",
  "src/metabrowser/static/formatters.js",
  "src/metabrowser/static/inventory-scope.js",
  "src/metabrowser/static/resource-context.js",
  "src/metabrowser/static/view-state.js",
  "src/metabrowser/static/navigation.js",
  "src/metabrowser/static/plugin-sdk.js",
  "src/metabrowser/static/charts.js",
]) {
  const source = fs.readFileSync(path.join(repoRoot, relative), "utf8");
  vm.runInContext(source, sandbox, { filename: relative });
}

const lazyMountCreatesNoChart = chartInstances.length === 0;
const directCanvas = new FakeCanvas();
const directChart = sandbox.metabrowser.chart(
  directCanvas,
  "line",
  { datasets: [{ borderColor: "var(--chart-series-info)" }] },
  { color: "var(--chart-label-text)" },
);
const directInitialColors = {
  series: directChart.data.datasets[0].borderColor,
  label: directChart.options.color,
};
const staticData = { datasets: [{ borderColor: "red" }] };
const staticOptions = { color: "black" };
const staticChart = sandbox.metabrowser.chart(new FakeCanvas(), "line", staticData, staticOptions);
const staticInputsPreserved =
  staticChart.data === staticData && staticChart.options === staticOptions;

resolvedTheme = "dark";
sandbox.MetabrowserTheme.notifyChanged({ mode: "dark", resolved: "dark" });
const directDarkColors = {
  series: directChart.data.datasets[0].borderColor,
  label: directChart.options.color,
  updateCalls: directChart.updateCalls.slice(),
};
directChart.destroy();
const directUpdatesAfterDestroy = directChart.updateCalls.length;
const staticUpdateCalls = staticChart.updateCalls.length;
staticChart.destroy();

const firstContainer = new FakeElement("div");
const firstPayload = {
  charts: [
    {
      title: "First",
      type: "line",
      series: [
        { label: "First series", data: [1], color: "var(--chart-series-info)" },
        { label: "OKLCH series", data: [2], color: "oklch(70% 0.1 95)" },
      ],
    },
  ],
};
sandbox.MetabrowserCharts.renderPayload(firstContainer, firstPayload);
const firstRuntimeChart = chartInstances.at(-1);

resolvedTheme = "light";
sandbox.MetabrowserTheme.notifyChanged({ mode: "light", resolved: "light" });
const repaintedFirstRuntimeChart = chartInstances.at(-1);

const secondContainer = new FakeElement("div");
const secondPayload = {
  charts: [
    {
      title: "Second",
      type: "line",
      series: [{ label: "Second series", data: [2], color: "var(--chart-series-info)" }],
    },
  ],
};
sandbox.MetabrowserCharts.renderPayload(secondContainer, secondPayload);
const secondRuntimeChart = chartInstances.at(-1);

resolvedTheme = "dark";
sandbox.MetabrowserTheme.notifyChanged({ mode: "dark", resolved: "dark" });
const repaintedSecondRuntimeChart = chartInstances.at(-1);
const chartCountBeforeDispose = chartInstances.length;
sandbox.MetabrowserCharts.dispose();
resolvedTheme = "light";
sandbox.MetabrowserTheme.notifyChanged({ mode: "light", resolved: "light" });

process.stdout.write(
  JSON.stringify({
    lazyMountCreatesNoChart,
    directInitialColors,
    directDarkColors,
    directUpdatesAfterDestroy,
    staticInputsPreserved,
    staticUpdateCalls,
    firstRuntime: {
      initialSeries: firstRuntimeChart.data.datasets[0].borderColor,
      oklchAlpha: firstRuntimeChart.data.datasets[1].backgroundColor,
      destroyedOnRepaint: firstRuntimeChart.destroyCalls,
      repaintedSeries: repaintedFirstRuntimeChart.data.datasets[0].borderColor,
      specTokenPreserved: firstPayload.charts[0].series[0].color,
    },
    replacement: {
      firstRepaintDestroyed: repaintedFirstRuntimeChart.destroyCalls,
      secondDestroyedOnRepaint: secondRuntimeChart.destroyCalls,
      repaintedLabel: repaintedSecondRuntimeChart.data.datasets[0].label,
      repaintedSeries: repaintedSecondRuntimeChart.data.datasets[0].borderColor,
    },
    disposal: {
      activeDestroyed: repaintedSecondRuntimeChart.destroyCalls,
      chartCountBeforeDispose,
      chartCountAfterTheme: chartInstances.length,
    },
  }),
);
