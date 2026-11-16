// Browserless session: a count summary's parts, the markup their one painter draws for each
// kind, and the words a change set's summary says.
//
// Every count summary comes in one shape of parts (docs/design-system.md, "Count Summaries
// Bold Their Numbers"): words as strings, a number as `{number}`, a list's comma as
// `{punctuation}`, the dot between a line's groups as `{separator}`, with `spoken` where the
// line has no name in words, and a file change status as `{status, letter}`. formatters.js
// paints them, `countPartsNodes` as nodes and `countPartsHtml` as markup, and the plugin SDK's
// `mb.countPartsNodes` hands its parts to the same function, so the Diff summary, a pull
// request's Checks summary, a commit's hover card, and every shell count summary paint each
// kind in its one class. `changeSummary` beside them says what a change set holds, in the
// words the Diff summary's header and a commit's hover card share.
//
// This runs the real formatters.js and plugin SDK and records, for each kind and for each
// surface's parts, the nodes the painter draws. It fails if the SDK's nodes ever differ from
// the shell's, if the markup ever says something other than the nodes, or if a part's text
// is not the text the parts read as. Each kind is recorded as its nodes, and each surface's
// parts as the markup they paint.

const assert = require("node:assert/strict");
const { createSdkSandbox } = require("./sdk-sandbox.js");

/** The smallest document the nodes need: an element records its class, attributes, and text. */
const recording = {
  createElement(tag) {
    return {
      tag,
      className: "",
      attributes: {},
      textContent: "",
      setAttribute(name, value) {
        this.attributes[name] = value;
      },
    };
  },
};
const sandbox = createSdkSandbox();
// After the SDK's startup, which touches a document of its own: its nodes come from this one.
sandbox.document = recording;
const formatters = sandbox.MetabrowserFormatters;
const mb = sandbox.metabrowser;

/** Nodes as plain data in this realm: a string is text, an element its class, attributes, and text. */
function shape(nodes) {
  return Array.from(nodes, (node) =>
    typeof node === "string"
      ? node
      : {
          tag: node.tag,
          class: node.className,
          ...(Object.keys(node.attributes).length === 0
            ? {}
            : { attributes: { ...node.attributes } }),
          text: node.textContent,
        },
  );
}

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const escaped = (text) => text.replace(/[&<>"']/g, (character) => ESCAPES[character]);

/** The markup the nodes would be, so the two paints can be held to one answer. */
function markupOf(nodes) {
  return nodes
    .map((node) => {
      if (typeof node === "string") {
        return escaped(node);
      }
      const attributes = Object.entries(node.attributes ?? {})
        .map(([name, value]) => ` ${name}="${escaped(value)}"`)
        .join("");
      return `<${node.tag} class="${node.class}"${attributes}>${escaped(node.text)}</${node.tag}>`;
    })
    .join("");
}

/** What the parts read as: each number, letter, and mark as written, and no `spoken`. */
const textOf = (parts) =>
  parts
    .map((part) =>
      typeof part === "string"
        ? part
        : (part.number ?? part.letter ?? part.separator ?? part.punctuation),
    )
    .join("");

/** Each kind of part on its own, then each surface's parts as it hands them to the painter. */
const KINDS = [
  ["words", ["files changed"]],
  ["a number", [{ number: "12,797" }]],
  ["a list's comma", [{ punctuation: "," }]],
  ["a separator", [{ separator: "·" }]],
  ["a separator that says a comma in its place", [{ separator: "·", spoken: ", " }]],
  ["a status", [{ status: "added", letter: "A" }]],
  ["words with markup in them", ['<b> & "quotes"']],
];

/** What each summary of a change set says, from its totals and its statuses' counts. */
const format = (count) => count.toLocaleString("en-US");
const family = (status, letter, word, count) => ({ status, letter, word, count });
const SUMMARIES = [
  [
    "the Diff summary's header the reader asked for",
    { files: 19, additions: 1234, deletions: 567, exact: true },
    [
      family("added", "A", "added", 10),
      family("removed", "D", "deleted", 5),
      family("modified", "M", "modified", 4),
    ],
  ],
  [
    "one renamed file",
    { files: 1, additions: 5, deletions: 2, exact: true },
    [family("renamed", "R", "renamed", 1)],
  ],
  ["no files", { files: 0, additions: 0, deletions: 0, exact: true }, []],
  [
    "totals that are not exact",
    { files: 3, additions: null, deletions: null, exact: false },
    [family("modified", "M", "modified", 3)],
  ],
  [
    "a commit's hover card",
    { files: 32, additions: 1921, deletions: 160, exact: true },
    [family("added", "A", "added", 4), family("modified", "M", "modified", 28)],
  ],
  [
    "a commit's hover card whose counts are unknown",
    { files: null, additions: null, deletions: null, exact: true },
    [
      family("added", "A", "added", null),
      family("deleted", "D", "deleted", null),
      family("modified", "M", "modified", null),
    ],
  ],
];

/** Paint *parts* both ways and through the SDK, and hold the three to one answer: the nodes. */
function painted(label, parts) {
  const nodes = shape(formatters.countPartsNodes(recording, parts));
  assert.deepEqual(
    shape(mb.countPartsNodes(parts)),
    nodes,
    `the SDK paints ${label} as the shell does`,
  );
  assert.equal(formatters.countPartsHtml(parts), markupOf(nodes), `${label}'s markup is its nodes`);
  const read = nodes
    .filter((node) => typeof node === "string" || node.class !== "visually-hidden")
    .map((node) => (typeof node === "string" ? node : node.text))
    .join("");
  assert.equal(read, textOf(parts), `${label} reads as its parts`);
  return nodes;
}

/** A surface's parts, held as each kind is, and recorded as the markup they paint. */
const markup = (label, parts) => markupOf(painted(label, parts));

const kinds = Object.fromEntries(KINDS.map(([label, parts]) => [label, painted(label, parts)]));

const summaries = {};
for (const [label, totals, entries] of SUMMARIES) {
  const said = formatters.changeSummary(totals, entries, format);
  summaries[label] = {
    text: said.text,
    label: said.label,
    estimated: said.estimated,
    files: markup(`${label}'s file count`, said.filesParts),
    ...(said.breakdownParts.length === 0
      ? {}
      : { breakdown: markup(`${label}'s statuses`, said.breakdownParts) }),
    totals: [said.additions, said.deletions],
  };
}

// A pull request's Checks summary, as pull-page.js hands it to the SDK: a paragraph, which
// has no name, so each dot says a comma in its place, and a no-break space holds each dot to
// the count before it.
const checks = markup("the Checks summary", [
  { number: "3" },
  " success",
  " ",
  { separator: "·", spoken: ", " },
  " ",
  { number: "1" },
  " failure",
]);

console.log(JSON.stringify({ kinds, summaries, checks }, null, 2));
