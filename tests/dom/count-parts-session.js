// Browserless session: a count summary's parts, the markup their one painter draws for each
// kind, the brief change line, the one component built from them, and the words a change
// set's summary says.
//
// Every count summary comes in one shape of parts (docs/design-system.md, "Count Summaries
// Bold Their Numbers"): words as strings, a number as `{number}`, a list's comma as
// `{punctuation}`, the dot between a line's groups as `{separator}`, with `spoken` where the
// line has no name in words, and a status count, "21 A", as `{status, letter, count}`, its
// number and letter one span that the shell draws bold in the status's ink. formatters.js
// paints them, `countPartsNodes` as nodes and `countPartsHtml` as markup, and the plugin SDK's
// `mb.countPartsNodes` hands its parts to the same function, so the Diff summary, a pull
// request's Checks summary, a commit's hover card, and every shell count summary paint each
// kind in its one class.
//
// A brief change line, "10 A, 5 D, 4 M · +1,234 −567", is one component (docs/design-system.md,
// "Brief Change Line"; mb-9ekj): `changeLine` builds it from a change set's statuses and line
// totals, and `changeLineNodes` and `changeLineHtml` paint it, through the SDK as
// `mb.changeLine` and `mb.changeLineNodes`. The Diff summary's header draws it after its "N
// files changed · ", and a commit's hover card and totals line draw it too. `changeSummary`
// says what a change set holds: its file count and its brief change line.
//
// This runs the real formatters.js and plugin SDK and records each kind's nodes, the change
// line's nodes and markup, and each surface's parts as the markup they paint. It fails if the
// SDK's nodes ever differ from the shell's, if the markup ever says something other than the
// nodes, or if what is painted does not read as the parts' and the line's text.

const assert = require("node:assert/strict");
const { createSdkSandbox } = require("./sdk-sandbox.js");

/** The smallest document the nodes need: an element records its class, attributes, and content. */
const recording = {
  createElement(tag) {
    return {
      tag,
      className: "",
      attributes: {},
      textContent: "",
      children: [],
      setAttribute(name, value) {
        this.attributes[name] = value;
      },
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

/**
 * Nodes as plain data in this realm: a string is text, an element its class, attributes, and
 * its text or its children.
 */
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
          ...(node.children.length === 0
            ? { text: node.textContent }
            : { children: shape(node.children) }),
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
      const content = node.children === undefined ? escaped(node.text) : markupOf(node.children);
      return `<${node.tag} class="${node.class}"${attributes}>${content}</${node.tag}>`;
    })
    .join("");
}

/** What nodes read as on the page: their text, without what a screen reader alone is told. */
const readOf = (nodes) =>
  nodes
    .map((node) =>
      typeof node === "string"
        ? node
        : node.class === "visually-hidden"
          ? ""
          : node.children === undefined
            ? node.text
            : readOf(node.children),
    )
    .join("");

/**
 * What the parts read as: each number, status count, and mark as written, and no `spoken`.
 */
const textOf = (parts) =>
  parts
    .map((part) =>
      typeof part === "string"
        ? part
        : part.letter !== undefined
          ? `${part.count} ${part.letter}`
          : (part.number ?? part.separator ?? part.punctuation),
    )
    .join("");

/** Each kind of part on its own. */
const KINDS = [
  ["words", ["files changed"]],
  ["a number", [{ number: "12,797" }]],
  ["a list's comma", [{ punctuation: "," }]],
  ["a separator", [{ separator: "·" }]],
  ["a separator that says a comma in its place", [{ separator: "·", spoken: ", " }]],
  ["a status count", [{ status: "added", letter: "A", count: "21" }]],
  ["words with markup in them", ['<b> & "quotes"']],
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
  assert.equal(readOf(nodes), textOf(parts), `${label} reads as its parts`);
  return nodes;
}

/** A surface's parts, held as each kind is, and recorded as the markup they paint. */
const markup = (label, parts) => markupOf(painted(label, parts));

const kinds = Object.fromEntries(KINDS.map(([label, parts]) => [label, painted(label, parts)]));

const format = (count) => count.toLocaleString("en-US");
const family = (status, letter, word, count) => ({ status, letter, word, count });

/**
 * Build a brief change line through the shell and the SDK, painted with *options*, paint it
 * both ways, hold the paints to one answer, and record it: its text, its words, and its
 * nodes or markup.
 */
function changeLine(label, change, options, record) {
  const line = formatters.changeLine(change, format);
  // The SDK's builder writes the shell's number format, which is this locale's here.
  assert.deepEqual(
    JSON.parse(JSON.stringify(mb.changeLine(change))),
    JSON.parse(JSON.stringify(formatters.changeLine(change, formatters.formatInteger))),
    `the SDK builds ${label} as the shell does`,
  );
  const nodes = shape(formatters.changeLineNodes(recording, line, options));
  assert.deepEqual(
    shape(mb.changeLineNodes(line, options)),
    nodes,
    `the SDK paints ${label} as the shell does`,
  );
  assert.equal(
    formatters.changeLineHtml(line, options),
    markupOf(nodes),
    `${label}'s markup is its nodes`,
  );
  assert.equal(
    readOf(nodes),
    line.text.replaceAll(" · ", "·").replace(" −", "−"),
    `${label} reads as its text, the line's gaps spacing its dot and its totals`,
  );
  return {
    text: line.text,
    label: line.label,
    ...(record === "nodes" ? { nodes } : { html: markupOf(nodes) }),
  };
}

const changeLines = {
  "the owner's example": changeLine(
    "the owner's example",
    {
      statuses: [
        family("added", "A", "added", 10),
        family("removed", "D", "deleted", 5),
        family("modified", "M", "modified", 4),
      ],
      additions: 1234,
      deletions: 567,
    },
    {},
    "nodes",
  ),
  "on a line with no name": changeLine(
    "on a line with no name",
    { statuses: [family("renamed", "R", "renamed", 1)], additions: 5, deletions: 2 },
    { spoken: ", " },
    "html",
  ),
  "no statuses": changeLine(
    "no statuses",
    { statuses: [], additions: 0, deletions: 0 },
    {},
    "html",
  ),
  "line counts unknown": changeLine(
    "line counts unknown",
    { statuses: [family("modified", "M", "modified", null)], additions: null, deletions: null },
    {},
    "html",
  ),
};

// Every line leaves out a total of zero (mb-efum, mb-ox6a): a side that is zero is not
// shown, both nonzero are both shown, an unknown one is "?", and a change of no lines is a
// muted "0 lines".
const omitZero = (label, change, record = "html") => changeLine(label, change, {}, record);
const zeroTotalsLeftOut = {
  "only additions": omitZero("only additions", { statuses: [], additions: 1234, deletions: 0 }),
  "only deletions": omitZero("only deletions", { statuses: [], additions: 0, deletions: 1 }),
  "both nonzero": omitZero("both nonzero", { statuses: [], additions: 1234, deletions: 567 }),
  "no lines": omitZero("no lines", { statuses: [], additions: 0, deletions: 0 }, "nodes"),
  "no lines, after a status": omitZero("no lines, after a status", {
    statuses: [family("modified", "M", "modified", 1)],
    additions: 0,
    deletions: 0,
  }),
  "an unknown total beside a zero": omitZero("an unknown total beside a zero", {
    statuses: [],
    additions: 0,
    deletions: null,
  }),
  "an unknown total beside a known one": omitZero("an unknown total beside a known one", {
    statuses: [],
    additions: 12,
    deletions: null,
  }),
  "line counts unknown": omitZero("line counts unknown", {
    statuses: [],
    additions: null,
    deletions: null,
  }),
};

/** What each summary of a change set says, from its totals and its statuses' counts. */
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

const summaries = {};
for (const [label, totals, entries] of SUMMARIES) {
  const said = formatters.changeSummary(totals, entries, format);
  // The summary is its file count and its brief change line, the one component.
  assert.deepEqual(
    said.line,
    formatters.changeLine(
      { statuses: entries, additions: totals.additions, deletions: totals.deletions },
      format,
    ),
    `${label}'s line is the brief change line`,
  );
  summaries[label] = {
    text: said.text,
    label: said.label,
    estimated: said.estimated,
    files: markup(`${label}'s file count`, said.filesParts),
    line: said.line.text,
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

console.log(JSON.stringify({ kinds, changeLines, zeroTotalsLeftOut, summaries, checks }, null, 2));
