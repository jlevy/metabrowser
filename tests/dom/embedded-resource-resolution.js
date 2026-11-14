// The identity the Markdown link enhancer asks /raw for when a served folder's document
// embeds each authored address: links.js `resolveStandardTarget` for an embed, then the
// enhancer's trailing-slash normalization (link-enhancer.js `normalizedFilePath`). Reads
// `[{authored, source}]` as JSON on stdin and prints the identity of each, or null for an
// address the enhancer does not serve, so tests/test_raw_versions.py can compare the
// server's prediction (src/metabrowser/embedded_resources.py) with the production resolver.
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const links = pathToFileURL(
  path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/markdown/links.js"),
).href;

let input = "";
process.stdin.on("data", (chunk) => {
  input += chunk;
});
process.stdin.on("end", async () => {
  const { resolveStandardTarget } = await import(links);
  const cases = JSON.parse(input);
  const identities = cases.map(({ authored, source }) => {
    const resolved = resolveStandardTarget({
      action: "embed",
      authoredTarget: authored,
      sourceKind: "filesystem",
      sourcePath: source,
      syntax: "html",
    });
    if (resolved.status !== "internal") {
      return null;
    }
    return resolved.path.endsWith("/") ? resolved.path.slice(0, -1) : resolved.path;
  });
  console.log(JSON.stringify(identities));
});
