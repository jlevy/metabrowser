// Contract checks for the source view's incremental growth.
//
// Both behaviors here replaced something measurably worse: a full re-render on
// every Load more (cost grew with the running total, not the chunk) and a
// fixed 128 KiB request (31 clicks to open a 4 MiB source file).

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

/** Minimal DOM double: just the shapes appendSourceText navigates. */
function makeNode(tag, className) {
  const classes = new Set(
    String(className || "")
      .split(/\s+/)
      .filter(Boolean),
  );
  return {
    tag,
    children: [],
    text: "",
    // Each call is one insertion into the live tree, which is what the browser styles
    // and lays out; a fragment's nodes arrive in one.
    insertions: 0,
    classList: {
      contains: (name) => classes.has(name),
      add: (name) => classes.add(name),
    },
    appendChild(node) {
      this.insertions += 1;
      for (const child of node?.fragment ? node.children.splice(0) : [node]) {
        this.children.push(child);
        if (typeof child === "string") {
          this.text += child;
        } else if (child && typeof child.data === "string") {
          this.text += child.data;
        }
      }
      return node;
    },
    querySelector(selector) {
      return this._map?.[selector] ?? null;
    },
  };
}

function makeWarning() {
  return {
    removed: false,
    outerHTML: '<div class="metabrowser-source-truncation-warning">old</div>',
    remove() {
      this.removed = true;
    },
  };
}

function makeDocument({ highlighted = false, missingCode = false, warning = null } = {}) {
  const code = makeNode("code", highlighted ? "hljs" : "plaintext");
  const host = makeNode("div", "metabrowser-source-host");
  host._map = { "pre.code-block > code": missingCode ? null : code };
  host.inserted = [];
  host.insertAdjacentHTML = function (position, html) {
    this.inserted.push({ position, html });
  };
  const doc = makeNode("#document", "");
  doc._map = {
    ".metabrowser-source-host": host,
    ".metabrowser-source-truncation-warning": warning,
  };
  return { doc, code, host, warning };
}

const sandbox = {
  console,
  document: {
    createTextNode: (data) => ({ data }),
    createDocumentFragment: () => ({
      fragment: true,
      children: [],
      appendChild(node) {
        this.children.push(node);
        return node;
      },
    }),
  },
  Math,
  Number,
  Object,
  String,
};
const moduleSource = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/source-append.js"),
  "utf-8",
);
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(moduleSource, sandbox, { filename: "source-append.js" });

const api = sandbox.MetabrowserSourceAppend;
check("the module installs its namespace", !!api, "MetabrowserSourceAppend missing");

// The same module in a runtime without Intl.Segmenter, which an engine may lack.
const bare = { Math, Number, Object, String };
bare.window = bare;
bare.globalThis = bare;
vm.createContext(bare);
vm.runInContext("delete Intl.Segmenter;", bare);
vm.runInContext(moduleSource, bare, { filename: "source-append.js" });
const bareApi = bare.MetabrowserSourceAppend;
check(
  "the bare runtime has no Intl.Segmenter",
  vm.runInContext("typeof Intl.Segmenter", bare) === "undefined",
);

// ── Growth ────────────────────────────────────────────────────────
check("growth doubles the last request", api.nextChunkBytes(1024, 1 << 30) === 2048);
check("growth stops at the cap", api.nextChunkBytes(6 * 1024, 8 * 1024) === 8 * 1024);
check("growth never exceeds the cap", api.nextChunkBytes(1 << 30, 8 * 1024) === 8 * 1024);
check("growth tolerates a zero start", api.nextChunkBytes(0, 4096) === 2);
check(
  "a sequence reaches a large file in few steps",
  (() => {
    let size = 2 * 1024 * 1024;
    let total = size;
    let clicks = 0;
    while (total < 32 * 1024 * 1024 && clicks < 50) {
      size = api.nextChunkBytes(size, 8 * 1024 * 1024);
      total += size;
      clicks += 1;
    }
    return clicks <= 6;
  })(),
  "took more than six clicks to reach 32 MiB",
);

// ── Appending ─────────────────────────────────────────────────────
{
  const { doc, code } = makeDocument();
  check("an append reports success", api.appendSourceText(doc, "hello") === true);
  check("the chunk lands as text", code.text === "hello", code.text);
  api.appendSourceText(doc, " world");
  check("appends accumulate", code.text === "hello world", code.text);
  check(
    "content is appended as a text node, never markup",
    code.children.every((child) => typeof child === "object" && typeof child.data === "string"),
    JSON.stringify(code.children),
  );
}

{
  const { doc, code } = makeDocument();
  check("an empty chunk is a no-op success", api.appendSourceText(doc, "") === true);
  check("an empty chunk appends nothing", code.text === "");
}

{
  // A highlighted block carries markup a raw text append would corrupt, so the
  // caller must be told to fall back to a full render.
  const { doc, code } = makeDocument({ highlighted: true });
  check("a highlighted block refuses the append", api.appendSourceText(doc, "x") === false);
  check("a refused append changes nothing", code.text === "");
}

{
  const { doc } = makeDocument({ missingCode: true });
  check(
    "an unexpected shape refuses rather than dropping content",
    api.appendSourceText(doc, "x") === false,
  );
}

check("a missing root refuses", api.appendSourceText(null, "x") === false);

// ── Text nodes of at most 64 KiB ──────────────────────────────────
//
// WebKit lays out one text node of millions of characters several times slower than
// Chrome, and text nodes of the HTML parser's size faster. An append therefore goes in
// as nodes of at most TEXT_NODE_MAX_LENGTH UTF-16 code units, which is what a DOM text
// node's length counts, not bytes.
const LIMIT = api.TEXT_NODE_MAX_LENGTH;
check("the bound is the HTML parser's text node size", LIMIT === 65_536, String(LIMIT));

const lengths = (pieces) => JSON.stringify(Array.from(pieces, (piece) => piece.length));
const isHigh = (code) => code >= 0xd800 && code <= 0xdbff;
const isLow = (code) => code >= 0xdc00 && code <= 0xdfff;

/** Every invariant a split owes the view, whatever the text. */
function wellSplit(name, text, pieces, limit = LIMIT) {
  check(`${name}: the pieces join to the text`, pieces.join("") === text);
  check(
    `${name}: every piece is non-empty and within the bound`,
    pieces.every((piece) => piece.length > 0 && piece.length <= limit),
    lengths(pieces),
  );
  for (let index = 1; index < pieces.length; index += 1) {
    const before = pieces[index - 1];
    const after = pieces[index];
    check(
      `${name}: piece ${index} does not split a surrogate pair`,
      !(isHigh(before.charCodeAt(before.length - 1)) && isLow(after.charCodeAt(0))),
    );
    check(
      `${name}: piece ${index} does not split a CRLF`,
      !(before.endsWith("\r") && after.startsWith("\n")),
    );
  }
}

check("empty text has no pieces", api.textPieces("").length === 0);
{
  const text = "x".repeat(LIMIT);
  const pieces = api.textPieces(text);
  check("exactly 64 KiB is one node", lengths(pieces) === `[${LIMIT}]`, lengths(pieces));
}
{
  const text = "x".repeat(LIMIT + 1);
  const pieces = api.textPieces(text);
  wellSplit("one code unit past 64 KiB", text, pieces);
  check("one code unit past 64 KiB is two nodes", lengths(pieces) === `[${LIMIT},1]`);
}
{
  // Source code: every node ends a line, so no line is laid out across two nodes and
  // nothing a line holds is shaped across a node boundary.
  const text = `${"x".repeat(99)}\n`.repeat(2_000);
  const pieces = api.textPieces(text);
  wellSplit("lines", text, pieces);
  check(
    "lines: every node ends at a newline",
    pieces.every((piece) => piece.endsWith("\n")),
    lengths(pieces),
  );
  check("lines: nodes are as full as whole lines allow", pieces[0].length === 65_500);
}
{
  const text = `${"x".repeat(LIMIT - 1)}\n${"y".repeat(10)}`;
  const pieces = api.textPieces(text);
  check(
    "a newline that is the 65,536th unit ends a full node",
    lengths(pieces) === `[${LIMIT},10]`,
    lengths(pieces),
  );
}
{
  // Multi-byte characters: 65,537 CJK characters are 196,611 UTF-8 bytes and 65,537
  // code units, and the bound counts code units.
  const text = "漢".repeat(LIMIT + 1);
  const pieces = api.textPieces(text);
  wellSplit("CJK", text, pieces);
  check("CJK splits by code units, not bytes", lengths(pieces) === `[${LIMIT},1]`);
}
{
  const text = `${"a".repeat(LIMIT - 1)}😀b`;
  const pieces = api.textPieces(text);
  wellSplit("a surrogate pair across the bound", text, pieces);
  check(
    "a surrogate pair across the bound moves whole to the next node",
    lengths(pieces) === `[${LIMIT - 1},3]` && pieces[1].startsWith("😀"),
    lengths(pieces),
  );
}
{
  const text = "😀".repeat(LIMIT);
  const pieces = api.textPieces(text);
  wellSplit("surrogate pairs only", text, pieces);
  check(
    "surrogate pairs fill a node exactly when they fit",
    lengths(pieces) === `[${LIMIT},${LIMIT}]`,
  );
}
{
  const text = `${"a".repeat(LIMIT - 1)}\r\nb`;
  const pieces = api.textPieces(text);
  wellSplit("a CRLF across the bound", text, pieces);
  check(
    "a CRLF across the bound moves whole to the next node",
    lengths(pieces) === `[${LIMIT - 1},3]`,
    lengths(pieces),
  );
}
{
  const text = `${"a".repeat(LIMIT - 10)}\r\n${"b".repeat(100)}`;
  const pieces = api.textPieces(text);
  check(
    "a CRLF inside the bound ends its node",
    lengths(pieces) === `[${LIMIT - 8},100]` && pieces[0].endsWith("\r\n"),
    lengths(pieces),
  );
}
{
  // A line longer than the bound is cut inside it, at a grapheme boundary, as WebKit's
  // parser cuts: a combining mark, an emoji sequence, or a flag stays whole.
  const graphemes = [
    ["a combining accent", "é"],
    ["a ZWJ family", "👩‍👩‍👧‍👦"],
    ["a flag", "🇺🇸"],
    ["a skin-tone emoji", "👍🏽"],
  ];
  for (const [label, cluster] of graphemes) {
    for (let shift = 1; shift < cluster.length; shift += 1) {
      const text = `${"a".repeat(LIMIT - shift)}${cluster}z`;
      const pieces = api.textPieces(text);
      wellSplit(`${label} ${shift} units before the bound`, text, pieces);
      check(
        `${label} ${shift} units before the bound moves whole to the next node`,
        pieces[0].length === LIMIT - shift && pieces[1].startsWith(cluster),
        lengths(pieces),
      );
    }
  }
}
// Grapheme boundaries depend on what comes before them: whether a regional indicator
// starts a flag depends on how many indicators precede it in its run. So a cut is
// checked against the boundaries of the whole text, from the engine's own segmenter,
// never against a piece of it.
const segmenter = new Intl.Segmenter(undefined, { granularity: "grapheme" });

/** Every grapheme boundary of the whole text, in order, with its end. */
function boundariesOf(text) {
  const found = Array.from(segmenter.segment(text), (segment) => segment.index);
  found.push(text.length);
  return found;
}

/**
 * Inside a line longer than the bound, each cut is the last grapheme boundary of the
 * whole text the bound allows; when the window holds none, one cluster is longer than
 * the bound and the cut falls back to a code point.
 */
function cutsAtGraphemes(name, text, pieces, limit = LIMIT) {
  const boundaries = boundariesOf(text);
  let start = 0;
  for (let index = 0; index < pieces.length - 1; index += 1) {
    const cut = start + pieces[index].length;
    const end = start + limit;
    if (!text.slice(start, end).includes("\n")) {
      const last = boundaries.filter((at) => at > start && at <= end).pop();
      check(
        `${name}: cut ${index + 1} at ${cut} is the last grapheme boundary by ${end}`,
        last === undefined || cut === last,
        `expected ${last}`,
      );
    }
    start = cut;
  }
}

{
  // A flag is two regional indicators, and a run of flags pairs from its start. A
  // window that begins between a flag's two indicators pairs them the other way.
  const text = `${"a".repeat(65_502)}${"\u{1F1FA}\u{1F1F8}".repeat(9)}z`;
  const pieces = api.textPieces(text);
  wellSplit("nine flags across the bound", text, pieces);
  cutsAtGraphemes("nine flags across the bound", text, pieces);
  check(
    "nine flags across the bound: the ninth flag moves whole to the next node",
    pieces[0].length === 65_534 && pieces[1].startsWith("\u{1F1FA}\u{1F1F8}"),
    lengths(pieces),
  );
}
{
  // Runs of indicators of every parity, ending at every position near the bound,
  // after a lone indicator that shifts which pairs are flags.
  for (const lead of ["", "\u{1F1EB}"]) {
    for (let flags = 1; flags <= 40; flags += 7) {
      for (let shift = 0; shift < 8; shift += 1) {
        const run = `${lead}${"\u{1F1FA}\u{1F1F8}".repeat(flags)}`;
        const text = `${"a".repeat(LIMIT - run.length + 1 + shift)}${run}z`;
        const label = `${lead ? "a lone indicator and " : ""}${flags} flags, shifted ${shift}`;
        const pieces = api.textPieces(text);
        wellSplit(label, text, pieces);
        cutsAtGraphemes(label, text, pieces);
      }
    }
  }
}
{
  // A cluster of a hundred code units, past any short lookbehind, still moves whole.
  const cluster = `e${"́".repeat(99)}`;
  const text = `${"a".repeat(LIMIT - 50)}${cluster}z`;
  const pieces = api.textPieces(text);
  wellSplit("a 100-unit cluster across the bound", text, pieces);
  check(
    "a 100-unit cluster across the bound moves whole to the next node",
    pieces[0].length === LIMIT - 50 && pieces[1].startsWith(cluster),
    lengths(pieces),
  );
}
{
  // One cluster longer than the bound has no boundary to cut at, so it is cut at the
  // last code point boundary: never inside a surrogate pair.
  const text = `e${"\u{1D167}".repeat(40_000)}`;
  const pieces = api.textPieces(text);
  wellSplit("a cluster longer than the bound", text, pieces);
  check(
    "a cluster longer than the bound is cut at a code point",
    pieces[0].length === LIMIT - 1,
    lengths(pieces),
  );
}
{
  // A cut inside a cluster longer than the bound leaves the next piece starting inside
  // it. Segmenting from there would pair the indicator run that follows the other way:
  // 65,534 Prepend characters and the first flag are one cluster of 65,538 units, so
  // the second cut must fall after a whole flag, at 131,070, not between two
  // indicators at 131,072.
  const text = `${"؀".repeat(65_534)}${"\u{1F1FA}\u{1F1F8}".repeat(16_386)}z`;
  const pieces = api.textPieces(text);
  wellSplit("a Prepend cluster and flags", text, pieces);
  cutsAtGraphemes("a Prepend cluster and flags", text, pieces);
  check(
    "a Prepend cluster and flags: the first cut is a code point inside the cluster",
    pieces[0].length === LIMIT,
    lengths(pieces),
  );
  check(
    "a Prepend cluster and flags: the second cut ends a whole flag",
    pieces[0].length + pieces[1].length === 131_070,
    lengths(pieces),
  );
}
{
  // Without Intl.Segmenter the cut is at a code point: a surrogate pair and a CRLF stay
  // whole, and a combining accent can be cut from its letter.
  const pair = `${"a".repeat(LIMIT - 1)}\u{1F600}b`;
  const pairPieces = bareApi.textPieces(pair);
  wellSplit("without a segmenter, a surrogate pair", pair, pairPieces);
  check(
    "without a segmenter, a surrogate pair across the bound moves whole",
    lengths(pairPieces) === `[${LIMIT - 1},3]`,
    lengths(pairPieces),
  );
  const crlf = `${"a".repeat(LIMIT - 1)}\r\nb`;
  const crlfPieces = bareApi.textPieces(crlf);
  wellSplit("without a segmenter, a CRLF", crlf, crlfPieces);
  check(
    "without a segmenter, a CRLF across the bound moves whole",
    lengths(crlfPieces) === `[${LIMIT - 1},3]`,
    lengths(crlfPieces),
  );
  const accent = `${"a".repeat(LIMIT - 1)}éz`;
  const accentPieces = bareApi.textPieces(accent);
  wellSplit("without a segmenter, an accent", accent, accentPieces);
  check(
    "without a segmenter, an accent across the bound is cut from its letter",
    lengths(accentPieces) === `[${LIMIT},2]` && accentPieces[1].startsWith("́"),
    lengths(accentPieces),
  );
}
{
  // Random text against small bounds, so every kind of boundary falls on every
  // position: lines, CRLF, lone CR, surrogate pairs, lone regional indicators that
  // pair with their neighbors, accents, emoji sequences, Prepend characters, and
  // clusters longer than the bound, which must still split rather than stall and must
  // not change how the text after them is cut. Every cut inside a line is checked
  // against the whole text's grapheme boundaries.
  let state = 0x9e3779b9;
  const random = () => {
    state ^= state << 13;
    state >>>= 0;
    state ^= state >>> 17;
    state ^= state << 5;
    state >>>= 0;
    return state;
  };
  const alphabet = [
    "a",
    "b",
    " ",
    "\n",
    "\r\n",
    "\r",
    "\u{1F600}",
    "́",
    "漢",
    "‍",
    "\u{1F469}",
    "\u{1F3FD}",
    "\u0600",
    "\u{1F1FA}",
    "\u{1F1F8}",
    "\u{1F1EB}",
  ];
  for (let trial = 0; trial < 2_000; trial += 1) {
    const parts = [];
    const count = 1 + (random() % 60);
    for (let index = 0; index < count; index += 1) {
      // A quarter of the draws are runs of up to 40 indicators, long enough for a
      // window to start inside one.
      const indicators = random() % 4 === 0 ? random() % 41 : 0;
      for (let run = 0; run < indicators; run += 1) {
        parts.push(alphabet[alphabet.length - 3 + (random() % 3)]);
      }
      // An eighth are runs of up to 100 Prepend characters or accents: one cluster
      // longer than most bounds here, with more text after it to cut.
      const joiners = random() % 8 === 0 ? random() % 101 : 0;
      const joiner = random() % 2 === 0 ? "\u0600" : "\u0301";
      for (let run = 0; run < joiners; run += 1) {
        parts.push(joiner);
      }
      parts.push(alphabet[random() % alphabet.length]);
    }
    const text = parts.join("");
    // Past 32 units, too, the lookbehind an earlier version trusted.
    const limit = 2 + (random() % 79);
    const label = `random text ${trial} at a bound of ${limit}`;
    const pieces = api.textPieces(text, limit);
    wellSplit(label, text, pieces, limit);
    cutsAtGraphemes(label, text, pieces, limit);
    wellSplit(`${label}, without a segmenter`, text, bareApi.textPieces(text, limit), limit);
  }
}
{
  const { doc, code } = makeDocument();
  const text = `${"x".repeat(99)}\n`.repeat(2_000);
  check("a long append reports success", api.appendSourceText(doc, text) === true);
  check("a long append keeps every character", code.text === text);
  check(
    "a long append lands as nodes within the bound",
    code.children.length === 4 && code.children.every((child) => child.data.length <= LIMIT),
    lengths(code.children.map((child) => child.data)),
  );
  check("a long append is one insertion", code.insertions === 1, String(code.insertions));
}

// ── Truncation banner ─────────────────────────────────────────────
//
// The append skips the plugin's render, so a banner left untouched keeps the
// byte counts from the previous chunk and survives past the final one.
{
  const warning = makeWarning();
  const { doc } = makeDocument({ warning });
  check("a completed load removes the banner", api.syncTruncationWarning(doc, "") === true);
  check("the stale banner is actually gone", warning.removed === true);
}

{
  const warning = makeWarning();
  const { doc } = makeDocument({ warning });
  const fresh =
    '<div class="metabrowser-source-truncation-warning">Showing 4.0 MB of 8.0 MB.</div>';
  check("a partial load refreshes the banner", api.syncTruncationWarning(doc, fresh) === true);
  check("the banner reports the new counts", warning.outerHTML === fresh, warning.outerHTML);
  check("refreshing does not remove it", warning.removed === false);
}

{
  const { doc, host } = makeDocument();
  const fresh =
    '<div class="metabrowser-source-truncation-warning">Showing 2.0 MB of 8.0 MB.</div>';
  check("an absent banner is inserted", api.syncTruncationWarning(doc, fresh) === true);
  check(
    "the banner leads the source host",
    host.inserted.length === 1 && host.inserted[0].position === "afterbegin",
    JSON.stringify(host.inserted),
  );
}

check("syncing a missing root refuses", api.syncTruncationWarning(null, "") === false);

if (failures.length) {
  console.error(`source append FAILURES:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.log("source append OK");
