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
  const { displayForByte, isSpecialByte, formatByteRuns, DEFAULT_ACCENT_RUN_BUDGET } = module;

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

  if (failures.length) {
    console.error(`binary byte format FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("binary byte format OK");
})();
