const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];
function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

class Element {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.className = "";
    this.dataset = {};
    this.hidden = false;
    this.attributes = {};
    this.listeners = {};
    this._innerHTML = "";
    this.classList = {
      toggle: (token, force) => {
        const tokens = new Set(this.className.split(/\s+/).filter(Boolean));
        if (force) {
          tokens.add(token);
        } else {
          tokens.delete(token);
        }
        this.className = [...tokens].join(" ");
      },
    };
  }
  append(...children) {
    this.children.push(...children);
  }
  replaceChildren(...children) {
    this.children = [...children];
    this._innerHTML = "";
  }
  setAttribute(name, value) {
    this.attributes[name] = value;
  }
  addEventListener(type, listener) {
    this.listeners[type] = listener;
  }
  removeEventListener(type, listener) {
    if (this.listeners[type] === listener) {
      delete this.listeners[type];
    }
  }
  set innerHTML(value) {
    this._innerHTML = value;
  }
  get innerHTML() {
    return this._innerHTML;
  }
  closest() {
    return null;
  }
}

global.document = { createElement: (tag) => new Element(tag) };
global.window = { METABROWSER_SETTINGS: {} };

(async () => {
  const fileTotalsPanelSource = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/file_totals_panel.js"),
      "utf8",
    )
    .replace(/^import[\s\S]*?from\s+"[^"]+";\n/gm, "")
    .replace(/^export\s+/gm, "");
  const fileTypeSummarySource = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/file_type_summary.js"),
      "utf8",
    )
    .replace(/^import[\s\S]*?from\s+"[^"]+";\n/gm, "")
    .replace(/^export\s+/gm, "");
  const createFileTotalsPanel = new Function(
    `${fileTotalsPanelSource}\nreturn createFileTotalsPanel;`,
  )();
  const fileTotalsPanel = createFileTotalsPanel({}, {}, {}, {});
  check(
    "Files totals are a separate open section",
    fileTotalsPanel.label === "Files" && fileTotalsPanel.defaultExpanded === true,
    JSON.stringify(fileTotalsPanel),
  );
  const createFileTypeSummaryPanel = new Function(
    `${fileTypeSummarySource}\nreturn createFileTypeSummaryPanel;`,
  )();
  const fileTypeSummaryPanel = createFileTypeSummaryPanel({}, {}, {}, {});
  check(
    "file breakdown is a separate closed section",
    fileTypeSummaryPanel.label === "File Breakdown" &&
      fileTypeSummaryPanel.defaultExpanded === false,
    JSON.stringify(fileTypeSummaryPanel),
  );
  const registrySource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/overview_registry.js"),
    "utf8",
  );
  const registryModule = await import(
    `data:text/javascript;base64,${Buffer.from(registrySource).toString("base64")}`
  );
  const builtInOrder = [
    { id: "folder.file-types", placement: "summary" },
    { id: "folder.file-totals", placement: "summary" },
  ].sort(registryModule.comparePanels);
  check(
    "Files precedes File Breakdown in deterministic panel order",
    builtInOrder.map((panel) => panel.id).join(",") === "folder.file-totals,folder.file-types",
  );

  let rollupApply = null;
  let rollupOptions = null;
  const controlListeners = [];
  const mountedControlParts = [];
  const totalsMetrics = [];
  const totalsCompositions = [];
  const summaryModelCalls = [];
  const summaryBody = new Element("div");
  summaryBody.querySelector = () => null;
  const mountFileTypeSummary = new Function(
    "mountDistributionView",
    "updateDistributionView",
    "buildFileTypeSummaryModel",
    "normalizeRollupEnvelope",
    `${fileTypeSummarySource}\nreturn mountFileTypeSummary;`,
  )(
    () => ({ body: summaryBody }),
    () => {},
    (envelope, showIgnored, _formatters, _fileTypes, metric) => {
      if (envelope?.incompatible) {
        throw new TypeError("registry mismatch");
      }
      summaryModelCalls.push({ showIgnored, metric });
      return { state: envelope ? "ready" : "pending", metric };
    },
    (raw) => raw,
  );
  const summaryMb = {
    countClass: () => "",
    errors: { classifyRequestError: () => ({ retryable: true }) },
    fileTypeIcon: () => "",
    fileTypes: {},
    directoryTotals: {
      subscribe: () => () => {},
    },
    filters: {
      get: () => ({ showIgnored: true }),
      subscribe: () => () => {},
    },
    formatFileCount: String,
    formatInteger: String,
    formatSize: String,
    sizeClass: () => "",
    viewState: {
      isActive: () => true,
      subscribeActive: () => () => {},
    },
    watchRollup(_path, options, apply) {
      rollupOptions = options;
      rollupApply = apply;
      return { dispose() {}, refresh: async () => {}, stale: () => false };
    },
  };
  const summaryPalette = {
    acquire: () => ({ classFor: () => "", release() {}, sync() {} }),
  };
  let projectedRollup;
  const projectionListeners = [];
  const projectionPool = {
    acquire: () => ({
      publish(value) {
        projectedRollup = value;
        for (const listener of [...projectionListeners]) {
          listener(value);
        }
      },
      subscribe(listener) {
        projectionListeners.push(listener);
        if (projectedRollup !== undefined) {
          listener(projectedRollup);
        }
        return () => {
          const index = projectionListeners.indexOf(listener);
          if (index !== -1) {
            projectionListeners.splice(index, 1);
          }
        };
      },
      release() {},
    }),
  };
  let sharedControlsState = { metric: "size", includeIgnored: false };
  const summaryControls = {
    get: () => sharedControlsState,
    mount(_container, parts) {
      mountedControlParts.push(parts);
      return () => {};
    },
    subscribe(listener) {
      controlListeners.push(listener);
      listener(sharedControlsState);
      return () => {
        const index = controlListeners.indexOf(listener);
        if (index !== -1) {
          controlListeners.splice(index, 1);
        }
      };
    },
  };
  const totalsCompositionScopes = [];
  const mountFileTotalsPanel = new Function(
    "buildFolderTotalsComposition",
    "mountFolderTotalsView",
    "normalizeFolderTotals",
    `${fileTotalsPanelSource}\nreturn mountFileTotalsPanel;`,
  )(
    (envelope, _fileTypes, metric, includeIgnored) => {
      totalsCompositionScopes.push(includeIgnored);
      return envelope?.totals
        ? {
            metric,
            files: { value: 8, segments: [] },
            ignored: { value: 2, segments: [] },
          }
        : null;
    },
    (_container, _totals, _mb, metric) => {
      totalsMetrics.push(metric);
      return {
        dispose() {},
        update() {},
        updateComposition(composition) {
          totalsCompositions.push(composition);
        },
        updateMetric(nextMetric) {
          totalsMetrics.push(nextMetric);
        },
      };
    },
    (raw) => raw || { state: "pending" },
  );
  const panelContext = {
    path: "",
    raw: {
      dir: {
        total_files: 10,
        total_size: 100,
        unignored_files: 8,
        unignored_size: 80,
      },
    },
  };
  mountFileTotalsPanel(
    new Element("div"),
    panelContext,
    summaryMb,
    summaryPalette,
    projectionPool,
    summaryControls,
    {},
  );
  mountFileTypeSummary(
    new Element("div"),
    panelContext,
    summaryMb,
    summaryPalette,
    projectionPool,
    summaryControls,
    {},
  );
  check(
    "Overview mounts one metric control in Files and one ignored checkbox in File Breakdown",
    mountedControlParts.length === 2 &&
      mountedControlParts[0].metric === true &&
      mountedControlParts[0].ignored === false &&
      mountedControlParts[1].metric === false &&
      mountedControlParts[1].ignored === true &&
      totalsMetrics[0] === "size",
    JSON.stringify({ mountedControlParts, totalsMetrics }),
  );
  function publishControls(nextState) {
    sharedControlsState = nextState;
    for (const listener of [...controlListeners]) {
      listener(sharedControlsState);
    }
  }
  const totalsUpdatesBeforeScopeChange = totalsMetrics.length;
  publishControls({ metric: "size", includeIgnored: true });
  check(
    "Show ignored changes the breakdown population and shared composition ordering",
    totalsMetrics.length === totalsUpdatesBeforeScopeChange &&
      summaryModelCalls.at(-1).showIgnored === true &&
      summaryModelCalls.at(-1).metric === "size" &&
      totalsCompositionScopes.at(-1) === true,
    JSON.stringify({ totalsMetrics, summaryModelCalls, totalsCompositionScopes }),
  );
  publishControls({ metric: "files", includeIgnored: true });
  check(
    "metric changes update totals and the breakdown together",
    totalsMetrics.at(-1) === "files" && summaryModelCalls.at(-1).metric === "files",
    JSON.stringify({ totalsMetrics, summaryModelCalls }),
  );
  try {
    rollupApply({ incompatible: true, breakdown: null, families: [], tallies: [] });
  } catch (error) {
    rollupOptions.onError(error);
  }
  check(
    "an incompatible first rollup replaces the pending skeleton with an error",
    summaryBody.innerHTML.includes("rollup data is incompatible"),
    summaryBody.innerHTML,
  );
  rollupApply({
    indexStatus: "done",
    totals: { allFiles: 10, unignoredFiles: 8 },
    groups: [],
    specialTypes: null,
  });
  check(
    "File Breakdown projects its completed rollup into Files without another watcher",
    totalsCompositions.at(-1)?.metric === "files" &&
      totalsCompositions.at(-1)?.files.value === 8 &&
      projectedRollup?.indexStatus === "done",
    JSON.stringify({ totalsCompositions, projectedRollup }),
  );

  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/overview.js"),
    "utf8",
  );
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  let contextListener = null;
  let activeListener = null;
  let updateCount = 0;
  let updateShouldFail = false;
  let disposeCount = 0;
  let summaryMountSignal = null;
  const printStates = [];
  const envelope = { kind: "folder", path: "src", readme_path: "src/README.md" };
  const mb = {
    errors: {
      isAbortError: (error) => error?.name === "AbortError",
      classifyRequestError: () => ({ message: "Panel failed.", retryable: true }),
    },
    folderContext: {
      subscribe(_path, listener) {
        contextListener = listener;
        listener(envelope);
        return () => {
          contextListener = null;
        };
      },
    },
    viewState: {
      isActive: () => true,
      subscribeActive(_container, listener) {
        activeListener = listener;
        listener(true);
        return () => {
          activeListener = null;
        };
      },
    },
    setViewPrintState(_container, state) {
      printStates.push(state);
    },
  };
  const descriptors = [
    {
      id: "folder.file-totals",
      label: "Files",
      placement: "summary",
      presentation: "surface",
      collapsible: true,
      defaultExpanded: true,
      required: true,
      printable: false,
      resolve: (context) => ({ key: context.path, data: "summary" }),
      mount(container, _context, _data, options) {
        container.innerHTML = "summary";
        summaryMountSignal = options.signal;
        return {
          dispose: () => (disposeCount += 1),
          update() {
            updateCount += 1;
            if (updateShouldFail) {
              throw new Error("update failed");
            }
          },
        };
      },
    },
    {
      id: "folder.file-types",
      label: "File Breakdown",
      placement: "summary",
      presentation: "surface",
      collapsible: true,
      defaultExpanded: false,
      required: true,
      printable: false,
      resolve: (context) => ({ key: context.path, data: "breakdown" }),
      mount(container) {
        container.innerHTML = "breakdown";
      },
    },
    {
      id: "folder.readme",
      label: "README",
      placement: "content",
      presentation: "document",
      printable: true,
      resolve: () => null,
      mount() {
        throw new Error("optional null panel must not mount");
      },
    },
    {
      id: "example.license",
      label: "License",
      placement: "supplemental",
      presentation: "surface",
      printable: true,
      resolve: () => Promise.resolve({ key: "license", data: "MIT" }),
      mount(container, _context, data) {
        container.innerHTML = data;
        return { dispose: () => (disposeCount += 1) };
      },
    },
  ];
  const container = new Element("div");
  const handle = module.mountOverview(container, { path: "src", raw: envelope }, mb, {
    listPanels: () => descriptors,
  });
  await new Promise((resolve) => setImmediate(resolve));
  const stack = container.children[0];
  check(
    "deterministic slots",
    stack.children.map((slot) => slot.dataset.panelId).join(",") ===
      "folder.file-totals,folder.file-types,folder.readme,example.license",
  );
  check(
    "panels receive visible headings",
    stack.children.map((slot) => slot.children[0].children[0].textContent).join(",") ===
      "Files,File Breakdown,README,License",
  );
  check(
    "panel headings use a shared semantic level",
    stack.children.every((slot) => slot.children[0].tagName === "H2"),
  );
  check(
    "collapsible panel headings expose their requested default state",
    stack.children.every((slot, index) => {
      const button = slot.children[0].children[0];
      const expectedExpanded = index === 1 ? "false" : "true";
      return (
        button.tagName === "BUTTON" &&
        button.className.includes("section-disclosure-trigger") &&
        button.attributes["aria-expanded"] === expectedExpanded &&
        button.attributes["aria-controls"] === slot.children[1].attributes.id &&
        slot.attributes["aria-labelledby"] === button.attributes.id
      );
    }),
  );
  check(
    "File Breakdown starts collapsed",
    stack.children[1].children[1].className.includes("folder-overview-panel-body-collapsed"),
  );
  check("optional panel hidden", stack.children[2].hidden === true);
  check("synthetic panel mounted", stack.children[3].children[1].innerHTML === "MIT");
  check(
    "print aggregation",
    printStates.some((state) => state.printable === true),
  );

  const filesToggle = stack.children[0].children[0].children[0];
  const filesBody = stack.children[0].children[1];
  filesToggle.listeners.click();
  check(
    "overview panels collapse",
    filesBody.className.includes("folder-overview-panel-body-collapsed"),
  );
  check(
    "collapsed state is announced",
    filesToggle.attributes["aria-expanded"] === "false",
    filesToggle.attributes["aria-expanded"],
  );
  check("collapse preserves the mounted panel", disposeCount === 0, String(disposeCount));
  filesToggle.listeners.click();
  check(
    "overview panels reopen",
    !filesBody.className.includes("folder-overview-panel-body-collapsed"),
  );
  check(
    "expanded state is announced",
    filesToggle.attributes["aria-expanded"] === "true",
    filesToggle.attributes["aria-expanded"],
  );

  contextListener({ ...envelope, readme_search_truncated: true });
  await new Promise((resolve) => setImmediate(resolve));
  check("same-key update", updateCount === 1, String(updateCount));
  check("same-key update keeps the mounted panel active", summaryMountSignal.aborted === false);
  activeListener(false);
  contextListener({ ...envelope, readme_search_truncated: false });
  await new Promise((resolve) => setImmediate(resolve));
  check("inactive context gated", updateCount === 1, String(updateCount));
  activeListener(true);
  await new Promise((resolve) => setImmediate(resolve));
  check("stale context reconciled", updateCount === 2, String(updateCount));

  updateShouldFail = true;
  contextListener({ ...envelope, readme_search_truncated: true });
  await new Promise((resolve) => setImmediate(resolve));
  check("failed update disposes old mount", disposeCount === 1, String(disposeCount));
  check("failed update aborts the mounted panel", summaryMountSignal.aborted === true);
  check(
    "failed update renders panel error",
    stack.children[0].children[1].children[0].attributes.role === "alert",
  );

  handle.dispose();
  handle.dispose();
  check("handles disposed exactly once", disposeCount === 2, String(disposeCount));
  check("subscriptions disposed", contextListener === null && activeListener === null);
  check(
    "disclosure listeners disposed",
    stack.children.every((slot) => !slot.children[0].children[0].listeners.click),
  );

  if (failures.length) {
    console.error(`folder overview FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("folder overview OK");
})();
