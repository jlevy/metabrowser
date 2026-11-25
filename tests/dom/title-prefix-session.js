// Browserless session: which part of a commit's or pull request's title is its
// conventional-commit prefix, and the markup every title surface draws from it.
//
// One function splits a title, `titlePrefix` in formatters.js: a type of lowercase letters,
// an optional parenthetical scope, an optional "!", and the colon, 32 characters at most
// (TITLE_PREFIX_MAX_CHARS), with whitespace and something else after it. `titleNodes` and
// `titleHtml` beside it draw the prefix in a `span.title-prefix`, which the shell's
// stylesheet sets at regular weight, and the plugin SDK's `mb.titleNodes` hands its title
// to the same function. The Pulls rows, the pull request page's title, its stack menu, its
// Conversation's commits, Quick Search's pull requests, the Commits tab's rows, a commit's
// page, and its tooltip all draw a title through one of them (docs/design-system.md,
// "Titles").
//
// Why 32 (mb-htmy). The measurement lives here, beside the cases that pin it, because
// formatters.js is a startup script and its comments count against the startup-script
// transfer budget (devtools/check_startup_scripts.py). The cap keeps a lowercase word and a
// parenthetical sentence before a colon, "note(this is how … keep a row):", the title's own
// text, since a scope may hold spaces. The first cap, 16, cut real scopes such as
// "feat(view-on-github):" (21). Measured 2026-11-24 with TITLE_PREFIX over deduplicated
// `git log --all --format=%s` subjects: all 3,788 prefixes in this repository are 24 or
// fewer; of 52,066 in 188 other repositories, 99.94% are 32 or fewer, and most of the 29
// longer ones scope a list of issue IDs or a phrase such as "review A of #12, finding 1",
// which reads as a sentence.
//
// This runs the real formatters.js and plugin SDK and records, for each case, what the split
// answers. It fails if a part ever drops a character of the title, if the SDK's nodes differ
// from the shell's, or if a title with no prefix draws anything but itself: its text alone
// as nodes, and as markup exactly what the SDK's escapeHtml writes, as the commit's subject
// was written before it had a prefix.

const assert = require("node:assert/strict");
const { createSdkSandbox } = require("./sdk-sandbox.js");

/** The smallest document the nodes need: an element records its class and its children. */
const recording = {
  createElement(tag) {
    return {
      tag,
      className: "",
      children: [],
      append(...nodes) {
        this.children.push(...nodes);
      },
    };
  },
};
const sandbox = createSdkSandbox();
// After the SDK's startup, which touches a document of its own: its nodes come from this one.
sandbox.document = recording;
const formatters = sandbox.MetabrowserFormatters;
const mb = sandbox.metabrowser;

/** Nodes as plain data in this realm: a string is text, an element its tag, class, and children. */
function shape(nodes) {
  return Array.from(nodes, (node) =>
    typeof node === "string"
      ? node
      : { tag: node.tag, class: node.className, children: shape(node.children) },
  );
}

const LONG_REST = ` ${"decide every region's box at first paint, ".repeat(8).trim()}`;

/** @type {Array<[string, string]>} */
const CASES = [
  [
    "the request's example",
    "feat(ledger): chart strategies, range bands and Extended default (valuation, WIP)",
  ],
  ["a type alone", "fix: keep the scroller rule and the Tab stop of a lost landing"],
  ["a breaking change", "refactor(api)!: drop the version 1 routes"],
  ["a breaking change, no scope", "feat!: separate cache and config roots"],
  ["16 characters, the first cap", "refactor(stack): name the stack's Control chords"],
  ["17 characters", "refactor(stacks): name the stack's Control chords"],
  ["17 characters, from this repository", "revert(markdown): restore the table of contents"],
  // The shape of the owner's report (mb-htmy): 21 characters, past the first cap.
  [
    "a hyphenated scope, 21 characters",
    "feat(view-on-github): open the pull request on github.com",
  ],
  ["24 characters, from this repository", "fix(provider-resources): bound the resource reads"],
  ["a scope with a space", "fix(ui, git): a landing waits for the HEAD read"],
  [
    "a scope with a space, 20 characters",
    "fix(commits, pulls): a landing waits for the HEAD read; stack keys wait",
  ],
  ["exactly 32 characters", "fix(source-freshness, checkout): read the HEAD once"],
  ["33 characters", "test(source-freshness, checkout): read the HEAD once"],
  // 32 code points and 53 UTF-16 units: a character is a code point.
  ["32 characters in code points", `refactor(${"🚀".repeat(21)}): launch the stack`],
  // A lowercase word and a parenthetical sentence before a colon look like a prefix; the
  // cap keeps them the title's own text.
  [
    "a sentence that looks like a prefix",
    "note(this is how the cache and the scroller keep a row): read on",
  ],
  ["an empty scope", "fix(): keep the scroller rule"],
  ["no space after the colon", "fix:keep the scroller rule"],
  ["no space after the colon, with a scope", "feat(ledger):chart strategies"],
  ["an uppercase type", "Docs: link every shortcut description"],
  ["an uppercase draft marker", "WIP: draft the next page"],
  ["a digit in the type", "exp-040: measure large pull requests against github.com"],
  ["a merge commit", "Merge pull request #400 from jlevy/claude/keymap-commits-landing-focus"],
  ["a revert", 'Revert "fix(git): keep the scroller rule"'],
  ["a revert typed as one", 'revert: "fix(git): keep the scroller rule"'],
  ["an empty rest", "fix:"],
  ["a rest of whitespace", "fix:   "],
  ["a long title", `perf:${LONG_REST}`],
  ["a long title with no prefix", `Perf:${LONG_REST}`],
  ["markup in the title", 'fix(<b>): escape <em> & "quotes"'],
];

const reads = {};
let unchanged = 0;
for (const [label, title] of CASES) {
  const split = formatters.titlePrefix(title);
  const nodes = formatters.titleNodes(recording, title);
  assert.deepEqual(
    shape(mb.titleNodes(title)),
    shape(nodes),
    `the SDK draws ${label} as the shell does`,
  );
  if (split === null) {
    // No prefix: the title is drawn as it was before there were prefixes.
    assert.deepEqual(shape(nodes), [title], `${label} is its text alone`);
    assert.equal(formatters.titleHtml(title), mb.escapeHtml(title), `${label} is its escaped text`);
    unchanged += 1;
    reads[label] = {
      title: title.length > 80 ? `${title.slice(0, 40)}… (${title.length} characters)` : title,
      prefix: null,
    };
    continue;
  }
  assert.equal(split.prefix + split.rest, title, `${label} keeps every character`);
  assert.deepEqual(shape(nodes), [
    { tag: "span", class: "title-prefix", children: [split.prefix] },
    split.rest,
  ]);
  assert.equal(
    formatters.titleHtml(title),
    `<span class="title-prefix">${mb.escapeHtml(split.prefix)}</span>${mb.escapeHtml(split.rest)}`,
  );
  reads[label] = {
    title: title.length > 80 ? `${title.slice(0, 40)}… (${title.length} characters)` : title,
    prefix: split.prefix,
    characters: Array.from(split.prefix).length,
  };
}

// A caller that marks matches in a title, as Quick Search does, gets each part with where it
// starts in the title, so a match lands in the part it is in.
const parts = [];
formatters.titleNodes(recording, "feat(ledger): chart strategies", (text, start) => {
  parts.push({ text, start });
  return [text];
});

console.log(
  JSON.stringify(
    {
      cases: reads,
      noPrefixDrawsItsTextAlone: unchanged,
      markup: {
        nodes: shape(formatters.titleNodes(recording, "feat(ledger): chart strategies")),
        html: formatters.titleHtml('fix(<b>): escape <em> & "quotes"'),
      },
      parts,
    },
    null,
    2,
  ),
);
