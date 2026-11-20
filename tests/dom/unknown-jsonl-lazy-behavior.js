const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

// Generic JSONL registers its views before its provider, agent-log, has loaded, draws with
// the provider's exports once `plugins.load` settles, and mounts nothing for a view
// disposed while that load was in flight.
(async () => {
  const registry = new Map();
  const calls = [];
  let finishLoad;
  const loaded = new Promise((resolve) => {
    finishLoad = resolve;
  });
  const mb = {
    registerView(kind, view, spec) {
      registry.set(`${kind}/${view}`, spec);
    },
    plugins: {
      load(name) {
        assert.equal(name, "agent-log");
        return loaded;
      },
    },
  };
  const source = fs.readFileSync(
    path.join(process.argv[2], "src/metabrowser/builtin_plugins/unknown_jsonl/index.js"),
    "utf8",
  );
  vm.runInNewContext(source, { window: { metabrowser: mb }, console });
  const log = registry.get("unknown-jsonl/log");
  const raw = registry.get("unknown-jsonl/raw");
  assert.ok(log && raw, "generic JSONL must register before agent-log has loaded");
  const disposed = {};
  const pending = log.render(disposed, { path: "events.jsonl" });
  log.dispose(disposed);
  finishLoad({
    renderLog(container, ctx) {
      calls.push(["log", container, ctx.path]);
    },
    renderRaw(container, ctx) {
      calls.push(["raw", container, ctx.path]);
    },
    disposeLog(container) {
      calls.push(["dispose", container]);
    },
  });
  await pending;
  assert.deepEqual(calls, [], "disposed loading views must not mount late");
  const live = {};
  await log.render(live, { path: "events.jsonl" });
  log.dispose(live);
  await raw.render(live, { path: "other.jsonl" });
  raw.dispose(live);
  assert.deepEqual(calls, [
    ["log", live, "events.jsonl"],
    ["dispose", live],
    ["raw", live, "other.jsonl"],
  ]);
  console.log("unknown JSONL lazy loading OK");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
