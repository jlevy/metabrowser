const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

(async () => {
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki_parser.js"),
    "utf8",
  );
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const markdown = [
    "# Wiki",
    "## Parent",
    "### Child",
    "Setext &amp; `Code`",
    "-------------------",
    "",
    "[[Note]] [[Folder/Note|Label]] [[#Heading]] [[Note#Parent#Child]] [[#^block-id]]",
    "![[asset.png|640x480]]",
    "\\[[Escaped]] and `[[Inline code]]`",
    "[ordinary [[Not parsed]]](target.md)",
    "",
    "```markdown",
    "[[Fenced]]",
    "```",
    "",
    "Paragraph with block. ^stable-block",
    "^standalone-block",
    "Unsafe <name> [[A&B|<Label>]]",
    "",
  ].join("\n");
  const result = module.preprocessObsidianWiki(markdown);

  check("changed", result.changed === true);
  check("target count", result.targetCount === 7, String(result.targetCount));
  check("block count", result.blockCount === 2, String(result.blockCount));
  check("bare note metadata", result.source.includes('data-mb-wiki-target="Note"'));
  check("occurrence label", result.source.includes(">Label</span>"));
  check("hierarchical heading preserved", result.source.includes("Note#Parent#Child"));
  check("named block link preserved", result.source.includes("#^block-id"));
  check(
    "hierarchical heading anchor",
    result.source.includes('id="obsidian-heading-Wiki#Parent#Child"'),
  );
  check("short heading anchor", result.source.includes('id="obsidian-heading-Child"'));
  check(
    "relative hierarchical heading anchor",
    result.source.includes('id="obsidian-heading-Parent#Child"'),
  );
  check(
    "setext rendered-text heading anchor",
    result.source.includes('id="obsidian-heading-Setext &amp; Code"'),
  );
  check("media width", result.source.includes('data-mb-wiki-width="640"'));
  check("media height", result.source.includes('data-mb-wiki-height="480"'));
  check("escaped literal unchanged", result.source.includes(String.raw`\[[Escaped]]`));
  check("inline code unchanged", result.source.includes("`[[Inline code]]`"));
  check(
    "ordinary Markdown link unchanged",
    result.source.includes("[ordinary [[Not parsed]]](target.md)"),
  );
  check("fenced block unchanged", result.source.includes("[[Fenced]]"));
  check(
    "block marker becomes metadata",
    result.source.includes('id="obsidian-block-stable-block" data-mb-wiki-block="stable-block"'),
  );
  check("standalone block marker", result.source.includes('id="obsidian-block-standalone-block"'));
  check("target attribute escaped", result.source.includes('data-mb-wiki-target="A&amp;B"'));
  check("label text escaped", result.source.includes("&lt;Label&gt;"));

  const capped = module.preprocessObsidianWiki("[[Note]] ".repeat(4_100));
  check("target budget", capped.targetCount === 4_096, String(capped.targetCount));
  check("over-budget source remains visible", capped.source.includes("[[Note]]"));
  const oversized = module.preprocessObsidianWiki(`${"x".repeat(2_000_001)}[[Note]]`);
  check("oversized source unchanged", oversized.changed === false);
  check("oversized target count", oversized.targetCount === 0);

  if (failures.length) {
    console.error(`markdown wiki parser FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown wiki parser OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
