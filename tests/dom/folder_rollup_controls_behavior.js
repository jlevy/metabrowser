const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/rollup_controls.js"),
  "utf8",
);
async function main() {
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );

  const stored = new Map();
  const mb = {
    prefs: {
      get: (key, fallback) => (stored.has(key) ? stored.get(key) : fallback),
      set: (key, value) => stored.set(key, value),
    },
  };
  const state = module.createFolderRollupControls(mb);
  if (state.get().metric !== "size" || state.get().includeIgnored !== false) {
    throw new Error(`unexpected defaults: ${JSON.stringify(state.get())}`);
  }

  const first = [];
  const second = [];
  const unsubscribeFirst = state.subscribe((value) => first.push(value));
  const unsubscribeSecond = state.subscribe((value) => second.push(value));
  state.set({ metric: "files" });
  state.set({ includeIgnored: true });
  if (
    first.at(-1).metric !== "files" ||
    second.at(-1).includeIgnored !== true ||
    stored.get("folder.rollup").includeIgnored !== true
  ) {
    throw new Error("shared controls did not synchronize or persist");
  }
  unsubscribeFirst();
  unsubscribeSecond();

  const migratedPrefs = new Map([["folder.treemap", { metric: "files", includeIgnored: true }]]);
  const migrated = module.createFolderRollupControls({
    prefs: {
      get: (key, fallback) => (migratedPrefs.has(key) ? migratedPrefs.get(key) : fallback),
      set: (key, value) => migratedPrefs.set(key, value),
    },
  });
  if (migrated.get().metric !== "files" || migrated.get().includeIgnored !== true) {
    throw new Error("legacy treemap preference was not migrated");
  }
  console.log(JSON.stringify({ ok: true }));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
