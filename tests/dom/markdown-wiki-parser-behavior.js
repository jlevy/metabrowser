const fs = require("node:fs");
const path = require("node:path");
const { createHash } = require("node:crypto");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

(async () => {
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki-parser.js"),
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

  const literalCases = [
    ["unmatched inline delimiter", "`broken [[Target]]", 1],
    ["multiline exact-run code span", "`code\n[[Target]]`", 0],
    ["short opener cannot use longer closer", "`code [[Target]] ``", 1],
    ["long opener cannot use shorter closer", "``code [[Target]] `", 1],
    ["wiki before ordinary link", "[[Target]] [ordinary](target.md)", 1],
    ["wiki after ordinary link", "[ordinary](target.md) [[Target]]", 1],
    ["wiki inside ordinary link label", "[ordinary [[Hidden]]](target.md)", 0],
    ["wiki inside reference link label", "[ordinary [[Hidden]]][target]", 0],
    ["wiki inside fenced CRLF code", "```md\r\n[[Target]]\r\n```\r\n", 0],
    ["wiki inside indented code", "    [[Target]]\n", 0],
    ["wiki inside HTML comment", "<!-- [[Target]] -->\n", 0],
    ["wiki inside raw HTML block", "<details>\n[[Target]]\n</details>\n\n", 0],
  ];
  for (const [name, input, targetCount] of literalCases) {
    const actual = module.preprocessObsidianWiki(input);
    check(name, actual.targetCount === targetCount, String(actual.targetCount));
  }

  // A bracket only opens an ordinary link when its own balanced `]` is followed
  // by `(` or `[`. A task-list checkbox, a shortcut reference, or an unmatched
  // `[` must not pair with a later link's `](` and hide the wiki links between.
  const taskListSource = "- [ ] Review [[Meeting Notes]] per [spec](https://x)";
  const taskList = module.preprocessObsidianWiki(taskListSource);
  check(
    "wiki link after an unchecked task box converts",
    taskList.targetCount === 1 &&
      taskList.source ===
        '- [ ] Review <span class="metabrowser-wiki-link" data-mb-wiki-target="Meeting Notes" data-mb-wiki-action="navigate">Meeting Notes</span> per [spec](https://x)',
    taskList.source,
  );
  const bracketPairingCases = [
    ["checked task box", "- [x] Review [[Meeting Notes]] per [spec](https://x)", 1],
    ["uppercase checked task box", "* [X] Review [[Meeting Notes]] per [spec](https://x)", 1],
    ["ordered task box", "1. [ ] Step [[Setup]] then [guide](guide.md)", 1],
    [
      "nested task list",
      "- [ ] Parent [[Top]]\n  - [x] Child [[Nested Note]] see [link](https://x)\n   1. [ ] Step [[Deep]] [ref][id]\n",
      3,
    ],
    ["task box before an embed and an image", "- [ ] ![[diagram.png]] and ![alt](a.png)", 1],
    ["wiki inside a real link after a task box", "- [ ] See [the [[Hidden]] spec](https://x)", 0],
    ["shortcut reference before a link", "[note] then [[Target]] and [link](target.md)", 1],
    ["unmatched opener before a link", "[draft [[Target]] [link](target.md)", 1],
    ["balanced brackets inside a link label", "[a [b] c](target.md) [[Target]]", 1],
    ["escaped closer inside a link label", String.raw`[a \] [[Hidden]]](target.md)`, 0],
    ["code-span closer inside a link label", "[a `]` [[Hidden]]](target.md)", 0],
    // An outer label with no later `)` must not hide the destination of the
    // real link nested inside it, whose own `)` comes earlier.
    ["destination of a link nested in an unclosed outer label", "[x [b]([[W]]) d](e", 0],
    ["label of a link nested in an unclosed outer label", "[a [see [[W]]](c) d](e", 0],
    // CommonMark forbids a link inside link text: once a link forms inside a
    // label, the enclosing `[` is plain text and its wiki links convert.
    ["inline link inside link text", "[a [b](c) [[W]]](e)", 1],
    ["reference link inside link text", "[a [b][c] [[W]]](e)", 1],
    ["escaped image marker inside link text is a link", String.raw`[x \![a](b) [[W]]](c)`, 1],
    ["link inside image text keeps the image", "![a [b](c) [[W]]](e)", 0],
    ["image inside link text keeps the link", "[a ![b](c) [[W]]](e)", 0],
  ];
  for (const [name, input, targetCount] of bracketPairingCases) {
    const actual = module.preprocessObsidianWiki(input);
    check(name, actual.targetCount === targetCount, `${actual.targetCount}: ${actual.source}`);
  }

  const escapedCounts = [1, 2, 3, 4].map(
    (slashes) => module.preprocessObsidianWiki(`${"\\".repeat(slashes)}[[Target]]`).targetCount,
  );
  check(
    "wiki escape uses odd/even backslash parity",
    JSON.stringify(escapedCounts) === JSON.stringify([0, 1, 0, 1]),
    JSON.stringify(escapedCounts),
  );

  // Literal masking must never outlive its block. Each case pins what the
  // pre-worker parser emitted: HTML-looking lines are fence content, a stray
  // backtick cannot pair with a code span blocks later, and a masked line after
  // an ATX heading only rules out a setext underline.
  const literalScopeCases = [
    [
      "HTML lines inside a fence do not open a raw block",
      '```html\n<div class="card">\n  <p>Hello</p>\n</div>\n```\n\nSee [[Note]] and ![[Other#Part]]\n\n## Later Heading\n\nParagraph ^block-1\n',
      { anchors: 1, blocks: 1, targets: 2 },
    ],
    [
      "an iframe line inside a fence does not swallow the closing fence",
      '```html\n<iframe src="x"></iframe>\n```\n\n## After\n[[Target]]\n',
      { anchors: 1, blocks: 0, targets: 1 },
    ],
    [
      "a script line inside a tilde fence does not open a raw element",
      "~~~html\n<script>\nlet a = 1;\n~~~\n\n## After Script\n[[T]]\n",
      { anchors: 1, blocks: 0, targets: 1 },
    ],
    [
      "a stray backtick does not pair with a code span in a later block",
      "Type a ` to start code.\n\n# Heading\n\n[[Note]]\n\nuse `x` here\n",
      { anchors: 1, blocks: 0, targets: 1 },
    ],
    [
      "an ATX heading directly before code keeps its anchor",
      "## Setup\n```bash\nmake\n```\n\n## API\n`foo()` returns bar\n\n[[Doc#Setup]]\n",
      { anchors: 2, blocks: 0, targets: 1 },
    ],
  ];
  for (const [name, input, expected] of literalScopeCases) {
    const result = module.preprocessObsidianWiki(input);
    const actual = {
      anchors: (result.source.match(/obsidian-heading-/g) || []).length,
      blocks: result.blockCount,
      targets: result.targetCount,
    };
    check(name, JSON.stringify(actual) === JSON.stringify(expected), JSON.stringify(actual));
  }

  let seed = 0x5eed1234;
  const random = () => {
    seed = (Math.imul(seed, 1_664_525) + 1_013_904_223) >>> 0;
    return seed;
  };
  const corpusTokens = [
    "plain",
    "[[Note]]",
    "![[image.png|640x480]]",
    "`[[code]]`",
    "[ordinary [[hidden]]](target.md)",
    String.raw`\[[escaped]]`,
    "# Heading\n",
    "paragraph ^block-id\n",
    "```md\n[[fenced]]\n```\n",
    "<em>inline</em>",
    "A&amp;B",
    "\r\n",
  ];
  const seededOutputs = Array.from({ length: 512 }, () => {
    const pieces = 1 + (random() % 12);
    let input = "";
    for (let index = 0; index < pieces; index += 1) {
      input += corpusTokens[random() % corpusTokens.length];
      input += random() % 2 ? " " : "\n";
    }
    const actual = module.preprocessObsidianWiki(input);
    return [actual.blockCount, actual.changed, actual.source, actual.targetCount];
  });
  const seededDigest = createHash("sha256").update(JSON.stringify(seededOutputs)).digest("hex");
  // This fixed seed and digest are the intended legacy-output oracle for syntax
  // unaffected by the explicit CommonMark bug corrections above. It catches a
  // precedence or escaping drift without retaining the retired quadratic parser.
  // The digest was re-derived when literal masking was scoped to blocks; every
  // one of the 55 seeds that changed then matches the pre-worker parser exactly.
  check(
    "seeded intended-output differential corpus",
    seededDigest === "5e5c2cd7ef10f04ec0efa3e38e061f483d39bca8052757c3d681dd75a7664fe5",
    seededDigest,
  );

  const capped = module.preprocessObsidianWiki("[[Note]] ".repeat(4_100));
  check("target budget", capped.targetCount === 4_096, String(capped.targetCount));
  check("over-budget source remains visible", capped.source.includes("[[Note]]"));
  check(
    "target budget reports explicit incompleteness",
    capped.complete === false && capped.diagnostics[0]?.code === "wiki-target-limit",
  );
  const oversized = module.preprocessObsidianWiki(`${"x".repeat(2_000_001)}[[Note]]`);
  check("oversized source unchanged", oversized.changed === false);
  check("oversized target count", oversized.targetCount === 0);
  check(
    "oversized source is explicitly incomplete",
    oversized.complete === false && oversized.diagnostics[0]?.code === "source-too-large",
  );

  const bracketHeavy = module.preprocessObsidianWiki("[".repeat(2_000_000));
  const nestedHeavySource = `${"[a".repeat(999_999)}x]`;
  const nestedHeavy = module.preprocessObsidianWiki(nestedHeavySource);
  const taskBoxHeavySource = `${"[ ] [[a]] ".repeat(199_999)}[b](c)`;
  const taskBoxHeavy = module.preprocessObsidianWiki(taskBoxHeavySource);
  const closerHeavySource = `${"[".repeat(999_990)}${"]".repeat(999_990)}(x)`;
  const closerHeavy = module.preprocessObsidianWiki(closerHeavySource);
  for (const [name, inputLength, actual] of [
    ["bracket-heavy", 2_000_000, bracketHeavy],
    ["nested-bracket", nestedHeavySource.length, nestedHeavy],
    ["task-box-heavy", taskBoxHeavySource.length, taskBoxHeavy],
    ["balanced-bracket-heavy", closerHeavySource.length, closerHeavy],
  ]) {
    const totalWork = Object.values(actual.metrics).reduce((total, count) => total + count, 0);
    check(
      `${name} work is linearly bounded`,
      totalWork <= inputLength * 14,
      `${totalWork}/${inputLength}`,
    );
  }

  const expandingOccurrence = `[[${"&".repeat(480)}]]\n`;
  const expandingSource = expandingOccurrence.repeat(4096);
  const outputLimited = module.preprocessObsidianWiki(expandingSource);
  check(
    "transformed output cap rejects atomically",
    outputLimited.changed === false &&
      outputLimited.complete === false &&
      outputLimited.source === expandingSource &&
      outputLimited.targetCount === 0 &&
      outputLimited.diagnostics[0]?.code === "transformed-source-byte-limit",
    JSON.stringify({
      changed: outputLimited.changed,
      complete: outputLimited.complete,
      diagnostics: outputLimited.diagnostics,
      targetCount: outputLimited.targetCount,
    }),
  );

  const missingSelectionSource = "line\r\n".repeat(250_000);
  const missingSelection = module.selectTransclusionSource(
    missingSelectionSource,
    "obsidian-heading-not-present",
  );
  check(
    "missing tail selection streams line offsets once",
    missingSelection.status === "missing" &&
      missingSelection.metrics.lineCodeUnitsVisited <= missingSelectionSource.length,
    JSON.stringify(missingSelection),
  );

  if (failures.length) {
    console.error(`markdown wiki parser FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown wiki parser OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
