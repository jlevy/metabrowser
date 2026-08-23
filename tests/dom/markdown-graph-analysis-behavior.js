const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

async function dataModule(file, replacements = []) {
  let source = fs.readFileSync(path.join(repoRoot, file), "utf8");
  for (const [specifier, replacement] of replacements) {
    source = source.replace(JSON.stringify(specifier), JSON.stringify(replacement));
  }
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

(async () => {
  const scannerUrl = await dataModule("src/metabrowser/builtin_plugins/markdown/link-scanner.js");
  const linksUrl = await dataModule("src/metabrowser/builtin_plugins/markdown/links.js");
  const wikiUrl = await dataModule("src/metabrowser/builtin_plugins/markdown/wiki-resolver.js");
  const adaptersUrl = await dataModule(
    "src/metabrowser/builtin_plugins/markdown/project-adapters.js",
  );
  const githubUrl = await dataModule(
    "src/metabrowser/builtin_plugins/markdown/github-localizer.js",
  );
  const graphUrl = await dataModule("src/metabrowser/builtin_plugins/markdown/graph-analysis.js", [
    ["./link-scanner.js", scannerUrl],
    ["./links.js", linksUrl],
    ["./wiki-resolver.js", wikiUrl],
    ["./project-adapters.js", adaptersUrl],
    ["./github-localizer.js", githubUrl],
  ]);
  const scanner = await import(scannerUrl);
  const graph = await import(graphUrl);

  const scanned = scanner.scanMarkdownLinks(`
[Inline](guide.md#Start)
[Reference][guide]
[guide]: guide.md
[[Notes/Topic]]
<a class="doc" href="html.md">HTML</a>
\`[Ignored](ignored.md)\`
\
\`\`\`md
[Fenced](fenced.md)
[[Fenced Wiki]]
\`\`\`
`);
  check("source scanner complete", scanned.complete);
  check("source scanner finds Markdown, wiki, and HTML links", scanned.links.length === 4);
  check(
    "source scanner skips code",
    scanned.links.every(
      (link) => !link.authoredTarget.includes("ignored") && !link.authoredTarget.includes("Fenced"),
    ),
  );

  const snapshot = Object.freeze({
    complete: true,
    files: Object.freeze([
      Object.freeze({ path: "a.md" }),
      Object.freeze({ path: "guide.md" }),
      Object.freeze({ path: "Notes/Topic.md" }),
    ]),
  });
  const sources = {
    "a.md": "[Guide](guide.md#Start)\n[[Notes/Topic]]\n[Missing](missing.md)\n",
    "guide.md": "# Start\n",
    "Notes/Topic.md": "[[/a]]\n",
  };
  const before = JSON.stringify(snapshot);
  const result = await graph.analyzeMarkdownGraph({
    readText: async (target) => sources[target.path],
    snapshot,
  });
  check("catalog snapshot remains immutable", JSON.stringify(snapshot) === before);
  check("complete graph", result.complete);
  check("all Markdown nodes", result.nodes.length === 3);
  check("three resolved edges", result.edges.length === 3, JSON.stringify(result.edges));
  check(
    "missing standard link reported",
    result.unresolved.some(
      (link) => link.authoredTarget === "missing.md" && link.status === "missing",
    ),
  );
  check(
    "backlink sources grouped",
    result.backlinks.some(
      (entry) => entry.target === "a.md" && JSON.stringify(entry.sources) === '["Notes/Topic.md"]',
    ),
  );

  const limited = await graph.analyzeMarkdownGraph({
    limits: { maxFiles: 1 },
    readText: async (target) => sources[target.path],
    snapshot,
  });
  check("file budget marks graph incomplete", !limited.complete);
  check(
    "file budget diagnostic",
    limited.diagnostics.some((diagnostic) => diagnostic.code === "file-limit"),
  );

  const incomplete = await graph.analyzeMarkdownGraph({
    readText: async () => "[[Unknown]]",
    snapshot: { complete: false, files: [{ path: "a.md" }] },
  });
  check("catalog incompleteness preserved", !incomplete.complete);
  check(
    "pending wiki link preserved",
    incomplete.unresolved.some((link) => link.status === "pending"),
  );

  const controller = new AbortController();
  controller.abort();
  let abortObserved = false;
  let abortReads = 0;
  try {
    await graph.analyzeMarkdownGraph({
      readText: async () => {
        abortReads += 1;
        return "";
      },
      signal: controller.signal,
      snapshot,
    });
  } catch (error) {
    abortObserved = error?.name === "AbortError";
  }
  check("pre-aborted analysis rejects", abortObserved);
  check("pre-aborted analysis performs no reads", abortReads === 0);

  if (failures.length) {
    console.error(`markdown graph analysis FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown graph analysis OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
