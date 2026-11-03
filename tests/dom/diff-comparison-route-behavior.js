// The plugin owns transport identity; render paint is outside this routing contract.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { registerHooks } = require("node:module");
const { pathToFileURL } = require("node:url");
const root = path.resolve(__dirname, "../..");
const answer = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/diff-view-file-responses.json"), "utf8"),
).commit.body;
registerHooks({
  load(url, context, nextLoad) {
    if (url.endsWith("/builtin_plugins/diff/diff-view.js")) {
      return {
        format: "module",
        shortCircuit: true,
        source:
          "export const setChangeLoader = (load) => { globalThis.deferredLoader = load; }; export const mountDiffView = (_host, document) => ({ document, dispose() {} });",
      };
    }
    return nextLoad(url, context);
  },
});
const requests = [];
let registered;
globalThis.window = {
  METABROWSER_SETTINGS: { BUILD_TAG: "page-build", STORE_TAG: "page-store" },
  metabrowser: {
    registerView(_kind, _view, spec) {
      registered = spec;
    },
    async fetchPluginData(plugin, hook, params, options) {
      requests.push({ plugin, hook, params, signal: options?.signal });
      return structuredClone(answer);
    },
  },
};
async function main() {
  await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/diff/index.js")).href
  );
  const signal = new AbortController().signal;
  const route =
    "/api/plugin/github/pull-comparison?number=7&left=base&right=head&base_policy=merge_base&build=route-build&store=route-store";
  const comparison = { left: "base", right: "head", base_policy: "merge_base", route };
  await registered.prefetch(comparison, signal);
  const rendered = await registered.render({}, { comparison });
  await globalThis.deferredLoader(rendered.document.__revision, " lead\nfile ", { signal });
  assert.equal(requests.length, 3);
  for (const request of requests) {
    assert.equal(request.plugin, "github");
    assert.equal(request.hook, "pull-comparison");
    assert.equal(request.params.build, "route-build");
    assert.equal(request.params.store, "route-store");
    assert.equal(request.params.left, "base");
  }
  assert.deepEqual(requests[0].params, requests[1].params);
  assert.deepEqual(requests[2].params, { ...requests[0].params, file: " lead\nfile " });
  assert.equal(requests[0].signal, signal);
  assert.equal(requests[2].signal, signal);
  for (const route of [
    "https://example.org/api/plugin/github/pull-comparison",
    "//example.org/api/plugin/github/pull-comparison",
    "/api/source/pin",
    "/api/plugin/github/pull-comparison#fragment",
  ]) {
    assert.throws(
      () => registered.prefetch({ ...comparison, route }, signal),
      /same-origin plugin route/,
    );
  }
  assert.equal(requests.length, 3, "an invalid route reached transport");
  await registered.prefetch({ left: "base", right: "head", base_policy: "merge_base" });
  assert.equal(requests[3].plugin, "diff");
  assert.equal(requests[3].hook, "comparison");
  assert.equal(requests[3].params.build, "page-build");
  console.log("diff comparison routes OK");
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
