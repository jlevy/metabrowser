// One Load more step, browserless, through the production client code.
//
// Usage: node load-more-notice-session.js <repo_root> '<json {cached, chunk}>'
//
// `cached` is the file payload the shell holds and `chunk` the `/api/file` window
// a Load more fetched. The step merges them with source-append.js's
// `nextCacheValue` (what `loadMoreCurrentText` commits), then renders the
// partial-content notices with the plugin SDK, exactly as the append path syncs
// them. Prints `{next, top, bottom}`: the merged value, whose `bytes_read` is the
// next Load more's offset, and each notice's readout ("" once nothing remains).

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const [repoRoot, input] = process.argv.slice(2);
const { cached, chunk } = JSON.parse(input);

const sandbox = {
  console,
  setTimeout,
  clearTimeout,
  Promise,
  Set,
  Map,
  document: {
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
    createElement: () => ({}),
    documentElement: {},
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
for (const name of [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "contribution-registry.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
  "plugin-sdk.js",
  "source-append.js",
]) {
  const file = path.join(repoRoot, "src/metabrowser/static", name);
  vm.runInContext(fs.readFileSync(file, "utf8"), sandbox, { filename: name });
}

function readout(markup) {
  const match = /<span class="partial-notice-readout">([^<]*)<\/span>/.exec(markup);
  return match ? match[1] : "";
}

const next = sandbox.MetabrowserSourceAppend.nextCacheValue(cached, chunk);
process.stdout.write(
  JSON.stringify({
    next,
    top: readout(sandbox.metabrowser.renderTextTruncationWarning(next)),
    bottom: readout(sandbox.metabrowser.renderTextLoadMoreFooter(next)),
  }),
);
