// Byte-to-display transform for the binary plugin's Bytes view.
//
// Pure and DOM-free so the contract is exhaustively testable. Each input
// byte maps to exactly one display unit:
//
//   0x20-0x7E  the literal ASCII character
//   0x00-0x1F  the matching Unicode Control Picture (U+2400 + byte)
//   0x7F       U+2421, Symbol for Delete
//   0x80-0xFF  uppercase hex in guillemets, such as the two bytes of a
//              UTF-8 e-acute rendering as two separate hex tokens
//
// Nothing here decodes. The WHATWG Encoding Standard maps the `ascii`
// label to Windows-1252, so TextDecoder("ascii") would turn bytes above
// 0x7F into characters and break the one-byte-to-one-unit contract; the
// view therefore never runs content through a decoder at all.
//
// Lines are broken here rather than by CSS. Letting the browser wrap a
// large run is quadratic: laying one out costs 43 ms at 32 KiB, 560 ms at
// 128 KiB, 2.2 s at 256 KiB and 33 s at 1 MiB, because the line breaker
// searches for break opportunities across the whole run. Emitting explicit
// breaks lets the surface use `white-space: pre`, where layout is
// proportional to the number of lines: the same 1 MiB lands in ~50 ms.

/** Printable ASCII passes through; everything else is transformed. */
const PRINTABLE_MIN = 0x20;
const PRINTABLE_MAX = 0x7e;
const DELETE_BYTE = 0x7f;
/** U+2400 SYMBOL FOR NULL starts the Control Pictures block. */
const CONTROL_PICTURES_BASE = 0x2400;
/** U+2421 SYMBOL FOR DELETE sits past the C0 run. */
const DELETE_PICTURE = "␡";

/**
 * Accented runs allowed per rendered chunk.
 *
 * Run count tracks entropy rather than file size: high-entropy content
 * switches class roughly every 1.6 bytes, so a chunk of it yields tens of
 * thousands of runs while string-dense content yields far fewer. Past this
 * budget the accent is dropped, which loses no information — at that density
 * every token is special, so the color distinguishes nothing — and it bounds
 * the element count instead of approaching one element per byte.
 */
export const DEFAULT_ACCENT_RUN_BUDGET = 12000;

/** Fallback when a caller cannot measure the pane. */
export const DEFAULT_CHARS_PER_LINE = 160;

/** @type {string[]} */
const DISPLAY_TABLE = [];
for (let byte = 0; byte < 256; byte += 1) {
  if (byte >= PRINTABLE_MIN && byte <= PRINTABLE_MAX) {
    DISPLAY_TABLE.push(String.fromCharCode(byte));
  } else if (byte === DELETE_BYTE) {
    DISPLAY_TABLE.push(DELETE_PICTURE);
  } else if (byte < PRINTABLE_MIN) {
    DISPLAY_TABLE.push(String.fromCharCode(CONTROL_PICTURES_BASE + byte));
  } else {
    DISPLAY_TABLE.push(`‹${byte.toString(16).toUpperCase().padStart(2, "0")}›`);
  }
}

/** Display columns each byte occupies: 1 for a glyph, 4 for a hex token. */
const DISPLAY_WIDTH = DISPLAY_TABLE.map((unit) => unit.length);

/**
 * The display unit for one byte.
 *
 * @param {number} byte
 * @returns {string}
 */
export function displayForByte(byte) {
  return DISPLAY_TABLE[byte & 0xff];
}

/**
 * Columns one byte occupies once rendered.
 *
 * @param {number} byte
 * @returns {number}
 */
export function displayWidthForByte(byte) {
  return DISPLAY_WIDTH[byte & 0xff];
}

/**
 * True when the byte is rendered as a substitute glyph rather than itself.
 *
 * @param {number} byte
 * @returns {boolean}
 */
export function isSpecialByte(byte) {
  const value = byte & 0xff;
  return value < PRINTABLE_MIN || value > PRINTABLE_MAX;
}

/**
 * @param {Uint8Array} bytes
 * @param {number} start
 * @param {number} end
 * @returns {string}
 */
function renderRange(bytes, start, end) {
  /** @type {string[]} */
  const out = [];
  for (let index = start; index < end; index += 1) {
    out.push(DISPLAY_TABLE[bytes[index] & 0xff]);
  }
  return out.join("");
}

/**
 * Byte ranges that each fit within ``charsPerLine`` display columns.
 *
 * A byte's token is never split across a break, so every line still reads as
 * whole display units.
 *
 * @param {Uint8Array} bytes
 * @param {number} charsPerLine
 * @returns {Array<[number, number]>}
 */
export function lineRanges(bytes, charsPerLine) {
  const width = Math.max(4, Math.floor(charsPerLine) || DEFAULT_CHARS_PER_LINE);
  /** @type {Array<[number, number]>} */
  const ranges = [];
  let start = 0;
  let column = 0;
  for (let index = 0; index < bytes.length; index += 1) {
    const cost = DISPLAY_WIDTH[bytes[index] & 0xff];
    if (column > 0 && column + cost > width) {
      ranges.push([start, index]);
      start = index;
      column = 0;
    }
    column += cost;
  }
  if (start < bytes.length) {
    ranges.push([start, bytes.length]);
  }
  return ranges;
}

/**
 * Format one byte range, coalescing adjacent same-class bytes into runs so the
 * DOM never grows to one element per byte.
 *
 * Substitute glyphs come from a fixed internal table and contain no HTML
 * metacharacters, so only literal ASCII runs need escaping.
 *
 * @param {Uint8Array} bytes
 * @param {number} from
 * @param {number} to
 * @param {(value: string) => string} escapeHtml
 * @param {{remaining: number, dropped: boolean}} budget
 * @returns {string}
 */
function formatRange(bytes, from, to, escapeHtml, budget) {
  if (budget.dropped) {
    // Once the accent is spent it stays spent for the rest of the chunk, so
    // the treatment does not flicker back on partway down.
    return escapeHtml(renderRange(bytes, from, to));
  }
  /** @type {string[]} */
  const parts = [];
  let runStart = from;
  let runIsSpecial = false;
  let index = from;

  /** @param {number} end */
  const flush = (end) => {
    if (end <= runStart) {
      return;
    }
    const text = renderRange(bytes, runStart, end);
    parts.push(
      runIsSpecial ? `<span class="binary-byte-special">${text}</span>` : escapeHtml(text),
    );
    runStart = end;
  };

  for (; index < to; index += 1) {
    const special = isSpecialByte(bytes[index]);
    if (index > runStart) {
      if (special === runIsSpecial) {
        continue;
      }
      flush(index);
    }
    if (special && budget.remaining <= 0) {
      break;
    }
    if (special) {
      budget.remaining -= 1;
    }
    runIsSpecial = special;
  }

  flush(index);
  if (index < to) {
    budget.dropped = true;
    parts.push(escapeHtml(renderRange(bytes, index, to)));
  }
  return parts.join("");
}

/**
 * Render a byte window as one unbroken run.
 *
 * Retained for callers that own their own line breaking and for the display
 * contract tests.
 *
 * @param {Uint8Array} bytes
 * @param {(value: string) => string} escapeHtml
 * @param {number} [runBudget] Accented runs allowed before the accent is dropped.
 * @returns {{html: string, accentDropped: boolean}}
 */
export function formatByteRuns(bytes, escapeHtml, runBudget = DEFAULT_ACCENT_RUN_BUDGET) {
  const budget = { remaining: runBudget, dropped: false };
  const html = formatRange(bytes, 0, bytes.length, escapeHtml, budget);
  return { html, accentDropped: budget.dropped };
}

/**
 * Render a byte window as explicit lines joined by newlines.
 *
 * The result belongs in a `white-space: pre` surface. Breaking here instead of
 * in CSS is what keeps layout proportional to line count rather than quadratic
 * in the length of the run.
 *
 * ``lines`` is returned alongside the joined ``html`` because callers group
 * lines into render blocks, and the block size has to be small enough that
 * bringing one onscreen is cheap.
 *
 * @param {Uint8Array} bytes
 * @param {(value: string) => string} escapeHtml
 * @param {{charsPerLine?: number, runBudget?: number}} [options]
 * @returns {{html: string, lines: string[], accentDropped: boolean, lineCount: number}}
 */
export function formatByteLines(bytes, escapeHtml, options) {
  const charsPerLine = options?.charsPerLine ?? DEFAULT_CHARS_PER_LINE;
  const budget = { remaining: options?.runBudget ?? DEFAULT_ACCENT_RUN_BUDGET, dropped: false };
  const ranges = lineRanges(bytes, charsPerLine);
  /** @type {string[]} */
  const lines = [];
  for (const [from, to] of ranges) {
    lines.push(formatRange(bytes, from, to, escapeHtml, budget));
  }
  return {
    html: lines.join("\n"),
    lines,
    accentDropped: budget.dropped,
    lineCount: lines.length,
  };
}
