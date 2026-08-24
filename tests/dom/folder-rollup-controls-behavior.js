const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/rollup-controls.js"),
  "utf8",
);
async function main() {
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );

  const stored = new Map();
  const renderedGroups = [];
  const renderedChecks = [];
  const mb = {
    prefs: {
      get: (key, fallback) => (stored.has(key) ? stored.get(key) : fallback),
      set: (key, value) => stored.set(key, value),
    },
    filterControls: {
      groupHtml: (options) => {
        renderedGroups.push(options);
        return "<span>metric</span>";
      },
      checkHtml: (options) => {
        renderedChecks.push(options);
        return "<span>ignored</span>";
      },
      bind: () => () => {},
    },
  };
  const state = module.createFolderRollupControls(mb);
  if (state.get().metric !== "files" || state.get().includeIgnored !== true) {
    throw new Error(`unexpected defaults: ${JSON.stringify(state.get())}`);
  }
  const container = {
    innerHTML: "",
    classList: { add() {} },
  };
  const unmount = state.mount(container, { metric: true, ignored: false });
  const metricGroup = renderedGroups.at(-1);
  if (
    metricGroup.value !== "files" ||
    metricGroup.options.map(({ value, label }) => `${value}:${label}`).join(",") !==
      "files:Files,size:Bytes"
  ) {
    throw new Error(`unexpected metric chooser: ${JSON.stringify(metricGroup)}`);
  }
  if (container.innerHTML !== "<span>metric</span>" || renderedChecks.length !== 0) {
    throw new Error(`metric-only mount leaked scope controls: ${container.innerHTML}`);
  }
  unmount();

  const scopeContainer = {
    innerHTML: "",
    classList: { add() {} },
  };
  const unmountScope = state.mount(scopeContainer, { metric: false, ignored: true });
  if (
    scopeContainer.innerHTML !== "<span>ignored</span>" ||
    renderedGroups.length !== 1 ||
    renderedChecks.at(-1).label !== "Show ignored" ||
    renderedChecks.at(-1).checked !== true
  ) {
    throw new Error(`scope-only mount leaked metric controls: ${scopeContainer.innerHTML}`);
  }
  unmountScope();

  const first = [];
  const second = [];
  const unsubscribeFirst = state.subscribe((value) => first.push(value));
  const unsubscribeSecond = state.subscribe((value) => second.push(value));
  state.set({ metric: "size" });
  state.set({ includeIgnored: true });
  if (
    first.at(-1).metric !== "size" ||
    second.at(-1).includeIgnored !== true ||
    stored.get("folder.rollup").metric !== "size" ||
    stored.get("folder.rollup").includeIgnored !== true
  ) {
    throw new Error("shared controls did not synchronize or persist");
  }
  unsubscribeFirst();
  unsubscribeSecond();

  const savedPrefs = new Map([["folder.rollup", { metric: "size", includeIgnored: false }]]);
  const saved = module.createFolderRollupControls({
    prefs: {
      get: (key, fallback) => (savedPrefs.has(key) ? savedPrefs.get(key) : fallback),
      set: (key, value) => savedPrefs.set(key, value),
    },
  });
  if (saved.get().metric !== "size" || saved.get().includeIgnored !== false) {
    throw new Error("explicit saved rollup choices were not retained");
  }

  const unrelatedPrefs = new Map([["folder.treemap", { metric: "size", includeIgnored: false }]]);
  const fresh = module.createFolderRollupControls({
    prefs: {
      get: (key, fallback) => (unrelatedPrefs.has(key) ? unrelatedPrefs.get(key) : fallback),
      set: (key, value) => unrelatedPrefs.set(key, value),
    },
  });
  if (
    fresh.get().metric !== "files" ||
    fresh.get().includeIgnored !== true ||
    unrelatedPrefs.has("folder.rollup")
  ) {
    throw new Error("an unrelated pre-release preference changed rollup defaults");
  }
  console.log(JSON.stringify({ ok: true }));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
