// The SDK's `loadChangedFilesTree`, as plugin-sdk-views.js ships it: it asks the asset loader
// for the `changed-files-tree` bundle and answers the model the bundle installs. A load that
// fails rejects, a bundle that installs no tree rejects, and a later call asks again and
// answers the tree once it is there, which a diff's next mount and a Pulls tree's Retry rely
// on (A4 of review A on #448).
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const { createSdkSandbox } = require("./sdk-sandbox.js");
const { source } = require("./changed-files-tree-fixture.js");

async function main() {
  const asked = [];
  let fails = true;
  const sandbox = createSdkSandbox({
    MetabrowserAssets: {
      ensureAsset(name) {
        asked.push(name);
        return fails ? Promise.reject(new Error("the bundle did not load")) : Promise.resolve();
      },
      assetLoaded: () => false,
    },
  });
  const sdk = sandbox.metabrowser;
  assert.equal(typeof sdk.loadChangedFilesTree, "function");
  await assert.rejects(sdk.loadChangedFilesTree(), /the bundle did not load/);
  fails = false;
  await assert.rejects(sdk.loadChangedFilesTree(), /installed no tree/);
  vm.runInContext(fs.readFileSync(source, "utf8"), sandbox, { filename: source });
  const tree = await sdk.loadChangedFilesTree();
  assert.equal(typeof tree.buildFileTree, "function");
  assert.equal(tree, sandbox.MetabrowserChangedFilesTree);
  assert.deepEqual(asked.filter((name) => name === "changed-files-tree").length, 3);
  console.log("changed-files tree loader OK");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
