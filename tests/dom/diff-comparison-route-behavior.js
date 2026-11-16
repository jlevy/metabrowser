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
          "export const setChangeLoader = (load) => { globalThis.deferredLoader = load; }; export const mountDiffView = (_host, document, _api, options) => ({ document, options, dispose() {} }); export const mountDiffSummary = (_slot, document, _api, options) => ({ document, options, dispose() {} });",
      };
    }
    return nextLoad(url, context);
  },
});
const requests = [];
let registered;
const tree = require("./changed-files-tree-fixture.js").changedFilesTree();
/** How the next `loadChangedFilesTree` answers. */
let loadTree = () => Promise.resolve(tree);
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
    loadChangedFilesTree: () => loadTree(),
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

  // The rendered Markdown route is the server's too: the plugin appends only `file`, and
  // `prefetch` on the requests it sends ahead of Changes for the first screen's files.
  requests.length = 0;
  const rendered_route =
    "/api/plugin/github/pull-rendered-diff?number=7&left=base&right=head&store=route-store";
  const snapshot_route =
    "/api/plugin/github/pull-snapshot?number=7&left=base&right=head&store=route-store";
  const pull = { ...comparison, rendered_route, snapshot_route };
  const markdown = answer.manifest.files
    .filter((file) => /\.md$/.test((file.new ?? file.old).path))
    .map((file) => file.id);
  assert.ok(markdown.length > 0, "the recorded comparison changes a Markdown file");
  await registered.prefetch(pull, signal);
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
  assert.deepEqual(
    requests.map(({ hook, params }) => [hook, params.file, params.prefetch]),
    [
      ["pull-comparison", undefined, undefined],
      ...markdown.map((id) => ["pull-rendered-diff", id, "1"]),
    ],
  );
  assert.equal(requests.at(-1).params.store, "route-store");
  requests.length = 0;
  // The route codec a page has loaded; View file's own behavior is its session's.
  window.MetabrowserGitPath = { wire: () => "g1-UkVBRE1FLm1k" };
  const mounted = await registered.render({}, { comparison: pull });
  assert.equal(typeof mounted.options.renderMarkdown, "function");
  await mounted.options.renderMarkdown(markdown[0], signal);
  assert.deepEqual(requests.at(-1).params, {
    number: "7",
    left: "base",
    right: "head",
    store: "route-store",
    file: markdown[0],
  });
  assert.equal(requests.at(-1).signal, signal);
  const target = `${snapshot_route}&side=head&path=g1-UkVBRE1FLm1k`;
  assert.equal(mounted.options.isSnapshotTarget(target, false), true);
  assert.equal(mounted.options.isSnapshotTarget(`${target}&mode=image`, true), true);
  assert.equal(mounted.options.isSnapshotTarget("/api/tree", false), false);
  const plain = await registered.render({}, { comparison });
  assert.equal(plain.options.renderMarkdown, undefined, "no rendered route, no Rendered view");
  const errors = [];
  const logged = console.error;
  console.error = (...args) => errors.push(args[0]);
  try {
    const refused = await registered.render(
      {},
      { comparison: { ...pull, rendered_route: "https://example.org/api/plugin/x/y" } },
    );
    assert.equal(refused.options.renderMarkdown, undefined);
  } finally {
    console.error = logged;
  }
  assert.deepEqual(errors, ["metabrowser diff: rendered Markdown unavailable"]);

  // Every diff is given the shared changed-files tree. One whose tree does not load is mounted
  // without it, which keeps its totals line (diff-view-behavior.js), and says why; the next
  // diff asks again (A3 and A4 of review A on #448).
  assert.equal(plain.options.changedFiles, tree, "a diff is given the shared tree");
  errors.length = 0;
  loadTree = () => Promise.reject(new Error("the bundle did not load"));
  console.error = (...args) => errors.push(args[0]);
  let without;
  try {
    without = await registered.render({}, { comparison });
  } finally {
    console.error = logged;
  }
  assert.equal(without.options.changedFiles, null, "a tree that did not load is not given");
  assert.deepEqual(errors, ["metabrowser diff: the Diff summary is unavailable"]);
  loadTree = () => Promise.resolve(tree);
  const again = await registered.render({}, { comparison });
  assert.equal(again.options.changedFiles, tree, "the next diff asks for the tree again");

  // A commit's page gives the diff its own totals for the summary, which the view is handed
  // as they are (A3 of review A on #470).
  const totals = { files: 5, additions: 15, deletions: 3, exact: true };
  const counted = await registered.render({}, { comparison, summaryTotals: totals });
  assert.equal(counted.options.summaryTotals, totals, "a page's totals reach the view");
  assert.equal(again.options.summaryTotals, undefined, "and only where it gives them");

  // A page's Diff summary on its own reads the comparison's manifest alone, so its patches
  // are neither read nor validated, and one whose manifest is not valid draws nothing (A5 of
  // review A on #470).
  const broken = structuredClone(answer);
  for (const patch of Object.values(broken.patches)) {
    patch.hunks = "not hunks";
  }
  const slot = { replaceChildren() {} };
  const drawn = await registered.summary(slot, { raw: broken, openFile() {} });
  assert.deepEqual(drawn.document, { manifest: broken.manifest }, "drawn from the manifest");
  assert.equal(drawn.options.changedFiles, tree);
  const unlisted = structuredClone(answer);
  delete unlisted.manifest.totals;
  assert.equal(await registered.summary(slot, { raw: unlisted, openFile() {} }), null);
  console.log("diff comparison routes OK");
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
