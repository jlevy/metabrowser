// Contract checks for the binary plugin's pure byte formatter.
//
// The display contract is exhaustive over all 256 byte values, so this
// asserts it that way rather than sampling. Run coalescing and the accent
// budget are asserted through element counts and a glyph-sequence
// comparison, not wall-clock timings, so the test is not machine-dependent.

const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** Recover the visible glyph sequence from rendered HTML. */
function glyphs(html) {
  return html
    .replace(/<\/?span[^>]*>/g, "")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&");
}

function countSpans(html) {
  return (html.match(/<span/g) || []).length;
}

function expectedDisplay(byte) {
  if (byte >= 0x20 && byte <= 0x7e) {
    return String.fromCharCode(byte);
  }
  if (byte <= 0x1f) {
    return String.fromCharCode(0x2400 + byte);
  }
  if (byte === 0x7f) {
    return "␡";
  }
  return `‹${byte.toString(16).toUpperCase().padStart(2, "0")}›`;
}

(async () => {
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/binary/byte_format.js"),
    "utf8",
  );
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const {
    displayForByte,
    displayWidthForByte,
    isSpecialByte,
    formatByteRuns,
    formatByteLines,
    lineRanges,
    DEFAULT_ACCENT_RUN_BUDGET,
  } = module;

  // ── Display contract, exhaustively ──────────────────────────────
  const wrong = [];
  for (let byte = 0; byte < 256; byte += 1) {
    if (displayForByte(byte) !== expectedDisplay(byte)) {
      wrong.push(`0x${byte.toString(16)}=${JSON.stringify(displayForByte(byte))}`);
    }
  }
  check(
    "all 256 byte values map to the contract",
    wrong.length === 0,
    wrong.slice(0, 8).join(", "),
  );

  check("space stays a space", displayForByte(0x20) === " ", displayForByte(0x20));
  check("line feed is a control picture", displayForByte(0x0a) === "␊");
  check("delete is its own picture", displayForByte(0x7f) === "␡");
  check("high bytes use uppercase hex", displayForByte(0xc3) === "‹C3›");
  check("high bytes pad to two digits", displayForByte(0x80) === "‹80›");

  const specials = [];
  for (let byte = 0; byte < 256; byte += 1) {
    if (isSpecialByte(byte) !== !(byte >= 0x20 && byte <= 0x7e)) {
      specials.push(byte);
    }
  }
  check("isSpecialByte matches the printable range", specials.length === 0, specials.join(","));

  // ── No decoding ─────────────────────────────────────────────────
  const utf8 = formatByteRuns(Uint8Array.from([0xc3, 0xa9]), escapeHtml, 100);
  check("UTF-8 C3 A9 renders as two hex tokens", glyphs(utf8.html) === "‹C3›‹A9›", utf8.html);
  check("UTF-8 C3 A9 never decodes to e-acute", !utf8.html.includes("é"), utf8.html);

  // ── Escaping ────────────────────────────────────────────────────
  const meta = formatByteRuns(Uint8Array.from([0x3c, 0x3e, 0x26, 0x22, 0x27]), escapeHtml, 100);
  check(
    "printable HTML metacharacters are escaped",
    meta.html === "&lt;&gt;&amp;&quot;&#39;",
    meta.html,
  );

  // ── Run coalescing ──────────────────────────────────────────────
  const ordinary = formatByteRuns(new Uint8Array(10).fill(0x41), escapeHtml, 100);
  check("an ordinary run emits no element", countSpans(ordinary.html) === 0, ordinary.html);
  check("an ordinary run keeps its glyphs", glyphs(ordinary.html) === "A".repeat(10));

  const special = formatByteRuns(new Uint8Array(10).fill(0xff), escapeHtml, 100);
  check("a special run emits one element", countSpans(special.html) === 1, special.html);
  check("a special run keeps its glyphs", glyphs(special.html) === "‹FF›".repeat(10), special.html);

  const mixed = formatByteRuns(
    Uint8Array.from([0x41, 0x41, 0xff, 0xff, 0x42, 0x00, 0x00]),
    escapeHtml,
    100,
  );
  check("adjacent same-class bytes coalesce", countSpans(mixed.html) === 2, mixed.html);
  check("mixed content keeps its glyph order", glyphs(mixed.html) === "AA‹FF›‹FF›B␀␀", mixed.html);

  const empty = formatByteRuns(new Uint8Array(0), escapeHtml, 100);
  check("empty input renders nothing", empty.html === "" && empty.accentDropped === false);

  // ── Accent budget ───────────────────────────────────────────────
  const alternating = new Uint8Array(2048);
  for (let i = 0; i < alternating.length; i += 1) {
    alternating[i] = i % 2 === 0 ? 0x41 : 0xff;
  }
  const unbudgeted = formatByteRuns(alternating, escapeHtml, Number.MAX_SAFE_INTEGER);
  check(
    "alternating input emits one element per special byte when affordable",
    countSpans(unbudgeted.html) === 1024,
    String(countSpans(unbudgeted.html)),
  );
  check("an affordable render keeps the accent", unbudgeted.accentDropped === false);

  const budgeted = formatByteRuns(alternating, escapeHtml, 4);
  check("budget exhaustion is reported", budgeted.accentDropped === true);
  check(
    "budget exhaustion bounds the element count",
    countSpans(budgeted.html) <= 4,
    String(countSpans(budgeted.html)),
  );
  check(
    "budget exhaustion preserves the glyph sequence",
    glyphs(budgeted.html) === glyphs(unbudgeted.html),
    `${glyphs(budgeted.html).slice(0, 40)} vs ${glyphs(unbudgeted.html).slice(0, 40)}`,
  );

  const zeroBudget = formatByteRuns(alternating, escapeHtml, 0);
  check("a zero budget emits no element", countSpans(zeroBudget.html) === 0, zeroBudget.html);
  check(
    "a zero budget still preserves the glyph sequence",
    glyphs(zeroBudget.html) === glyphs(unbudgeted.html),
  );

  // Worst case at the shipped chunk size: 64 KiB alternating, default budget.
  const pathological = new Uint8Array(64 * 1024);
  for (let i = 0; i < pathological.length; i += 1) {
    pathological[i] = i % 2 === 0 ? 0x41 : 0xff;
  }
  const shipped = formatByteRuns(pathological, escapeHtml, DEFAULT_ACCENT_RUN_BUDGET);
  check(
    "the shipped budget bounds a pathological chunk",
    countSpans(shipped.html) <= DEFAULT_ACCENT_RUN_BUDGET,
    String(countSpans(shipped.html)),
  );
  check(
    "a pathological chunk still renders every byte",
    glyphs(shipped.html).length === 32 * 1024 + 32 * 1024 * 4,
    String(glyphs(shipped.html).length),
  );

  // Realistic mixed content stays under the budget and keeps the accent.
  const realistic = new Uint8Array(64 * 1024);
  for (let i = 0; i < realistic.length; i += 1) {
    realistic[i] = i % 64 < 60 ? 0x41 : 0xff;
  }
  const kept = formatByteRuns(realistic, escapeHtml, DEFAULT_ACCENT_RUN_BUDGET);
  check("string-dense content keeps the accent", kept.accentDropped === false);

  // ── Line breaking ───────────────────────────────────────────────
  //
  // Breaks are emitted here rather than left to CSS: letting the browser wrap
  // one large run is quadratic (2.2 s at 256 KiB, 33 s at 1 MiB measured),
  // while `white-space: pre` over explicit lines is proportional to line count.

  const widths = [];
  for (let byte = 0; byte < 256; byte += 1) {
    if (displayWidthForByte(byte) !== expectedDisplay(byte).length) {
      widths.push(byte);
    }
  }
  check("display width matches the rendered unit", widths.length === 0, widths.join(","));

  // 1-column bytes: 10 per line at width 10.
  const ascii = new Uint8Array(25).fill(0x41);
  check(
    "ranges pack single-column bytes to the limit",
    JSON.stringify(lineRanges(ascii, 10)) ===
      JSON.stringify([
        [0, 10],
        [10, 20],
        [20, 25],
      ]),
    JSON.stringify(lineRanges(ascii, 10)),
  );

  // 4-column bytes: only 2 fit in 10 columns, and a token is never split.
  const high = new Uint8Array(5).fill(0xff);
  check(
    "ranges never split a byte token across a break",
    JSON.stringify(lineRanges(high, 10)) ===
      JSON.stringify([
        [0, 2],
        [2, 4],
        [4, 5],
      ]),
    JSON.stringify(lineRanges(high, 10)),
  );

  const lines = formatByteLines(ascii, escapeHtml, { charsPerLine: 10 });
  check("line count is reported", lines.lineCount === 3, String(lines.lineCount));
  check(
    "lines are joined with newlines",
    lines.html.split("\n").length === 3,
    JSON.stringify(lines.html),
  );
  check(
    "breaking changes no glyph, only where they sit",
    lines.html.split("\n").join("") === "A".repeat(25),
    lines.html,
  );

  // No line may exceed the column budget once tags are stripped.
  const mixedBytes = new Uint8Array(4096);
  for (let i = 0; i < mixedBytes.length; i += 1) {
    mixedBytes[i] = i % 5 === 0 ? 0x80 + (i % 100) : 0x41 + (i % 26);
  }
  const mixedLines = formatByteLines(mixedBytes, escapeHtml, { charsPerLine: 80 });
  const overLong = mixedLines.html
    .split("\n")
    .map((line) => glyphs(line).length)
    .filter((len) => len > 80);
  check(
    "no rendered line exceeds the column budget",
    overLong.length === 0,
    overLong.slice(0, 5).join(","),
  );
  check(
    "line breaking preserves the whole byte sequence",
    mixedLines.html.split("\n").map(glyphs).join("") ===
      glyphs(formatByteRuns(mixedBytes, escapeHtml, Number.MAX_SAFE_INTEGER).html),
  );

  // The accent budget is per chunk, not per line, and stays dropped once spent.
  const dense = new Uint8Array(4096);
  for (let i = 0; i < dense.length; i += 1) {
    dense[i] = i % 2 === 0 ? 0x41 : 0xff;
  }
  const denseLines = formatByteLines(dense, escapeHtml, { charsPerLine: 40, runBudget: 8 });
  check("the budget spans lines rather than resetting", denseLines.accentDropped === true);
  check(
    "a spent budget bounds elements across the whole chunk",
    countSpans(denseLines.html) <= 8,
    String(countSpans(denseLines.html)),
  );
  check(
    "a spent budget still renders every byte",
    denseLines.html.split("\n").map(glyphs).join("") ===
      glyphs(formatByteRuns(dense, escapeHtml, Number.MAX_SAFE_INTEGER).html),
  );

  const emptyLines = formatByteLines(new Uint8Array(0), escapeHtml, { charsPerLine: 40 });
  check(
    "an empty window produces no lines",
    emptyLines.html === "" && emptyLines.lineCount === 0,
    JSON.stringify(emptyLines),
  );

  if (failures.length) {
    console.error(`binary byte format FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("binary byte format OK");
})();
