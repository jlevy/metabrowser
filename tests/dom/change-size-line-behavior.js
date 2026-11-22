// The change size line (docs/design-system.md, "Change Size Line"): what
// `metabrowser.changeSizeLine` says of a change set and how its painters draw it, through the
// real view helpers (plugin-sdk-views.js), and the size a Pulls row's line ends with
// (row-lines.js, `rowSize`).
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { createSdkSandbox } = require("./sdk-sandbox.js");

async function main() {
  const repoRoot = path.resolve(process.argv[2]);
  const mb = createSdkSandbox().metabrowser;

  const full = mb.changeSizeLine({
    commits: 77,
    files: 83,
    pushedBytes: 2_411_724,
    diffBytes: 14_680_064,
  });
  assert.equal(
    full.text,
    "77 commits\u00a0· 83 files changed\u00a0· 2.3 MB compressed (14.0 MB raw diff)",
    "the whole line reads as its counts, then its size",
  );
  assert.equal(full.label, "77 commits, 83 files changed, 2.3 MB compressed, 14.0 MB raw diff");
  assert.match(full.tooltip ?? "", /^2\.3 MB compressed: what Git pushes/);
  assert.match(full.tooltip ?? "", /14\.0 MB raw diff: its patch, uncompressed\.$/);
  // Keep the same text for callers reading the line's numbers.
  // The sandbox's arrays are of another realm, so they are compared as JSON.
  assert.equal(
    JSON.stringify(
      full.parts
        .filter((part) => typeof part === "object" && "number" in part)
        .map((part) => part.number),
    ),
    JSON.stringify(["77", "83", "2.3 MB", "14.0 MB"]),
  );
  // Each dot is kept with the group before it and said as a comma.
  assert.ok(
    full.parts.every(
      (part, at) =>
        typeof part !== "object" ||
        !("separator" in part) ||
        (part.spoken === ", " && full.parts[at - 1] === " "),
    ),
    "each dot follows a no-break space and is said as a comma",
  );

  const counts = mb.changeSizeLine({ files: 1 });
  assert.equal(counts.text, "1 file changed", "no commits or size: the file count alone");
  assert.equal(counts.tooltip, null);
  assert.equal(counts.sizeParts.length, 0);
  assert.equal(mb.changeSizeLine({ commits: 1, files: null }).label, "1 commit, ? files changed");
  assert.equal(
    mb.changeSizeLine({ files: 2, pushedBytes: 900, diffBytes: null }).label,
    "2 files changed, 900 B compressed",
    "a size with no patch size says the pushed size alone",
  );

  const html = mb.changeSizeLineHtml(full);
  assert.ok(
    html.startsWith('<span class="change-size-line"><span class="summary-number">77</span>'),
  );
  assert.ok(
    html.includes(
      '<span class="change-size-line-size" data-tip-text="2.3 MB compressed: what Git pushes for this change. 14.0 MB raw diff: its patch, uncompressed.">' +
        '<span class="size size-large">2.3 MB</span> compressed (<span class="size size-large">14.0 MB</span> raw diff)</span>',
    ),
    html,
  );
  const overview = mb.changeSizeLine({
    commits: 8,
    files: 28,
    pushedBytes: 64_410,
    diffBytes: 217_600,
  });
  assert.equal(
    overview.text,
    "8 commits\u00a0· 28 files changed\u00a0· 62.9 KB compressed (212.5 KB raw diff)",
  );
  assert.equal(
    overview.label,
    "8 commits, 28 files changed, 62.9 KB compressed, 212.5 KB raw diff",
  );
  assert.ok(
    mb
      .changeSizeLineHtml(overview)
      .includes(`${mb.sizeHtml(64_410)} compressed (${mb.sizeHtml(217_600)} raw diff)`),
  );
  const limit = 1024 * 1024;
  const atLimit = mb.changeSizeLine({ files: 1, pushedBytes: limit });
  const overLimit = mb.changeSizeLine({ files: 1, pushedBytes: limit + 1 });
  assert.equal(atLimit.text, overLimit.text, "rounding conceals a one-byte threshold crossing");
  assert.ok(mb.changeSizeLineHtml(atLimit).includes('<span class="size">1.0 MB</span>'));
  assert.ok(
    mb.changeSizeLineHtml(overLimit).includes('<span class="size size-large">1.0 MB</span>'),
  );
  assert.ok(!html.includes("file-change-status"), "never a status's color");
  assert.ok(!mb.changeSizeLineHtml(counts).includes("change-size-line-size"));

  const { rowSize } = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/github/row-lines.js")).href
  );
  const format = (bytes) => `${bytes} B`;
  const row = (size) => ({ number: 1, statuses: [], additions: 1, deletions: 1, size });
  assert.equal(rowSize(row(null), format), null, "no size kept: nothing");
  assert.equal(
    rowSize(row({ state: "unknown", pushed_bytes: null, diff_bytes: null }), format),
    null,
    "a size that cannot be known: nothing",
  );
  const sized = rowSize(row({ state: "measured", pushed_bytes: 10, diff_bytes: 30 }), format);
  assert.deepEqual(sized?.parts, [" ", { separator: "·" }, " ", { number: "10 B" }]);
  assert.equal(sized?.label, "10 B compressed, 30 B raw diff");
  assert.equal(
    sized?.tooltip,
    "10 B compressed: what Git pushes for this pull request. 30 B raw diff: its patch, uncompressed.",
  );
  console.log("change size line OK");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
