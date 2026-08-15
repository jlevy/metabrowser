// Byte-to-display transform for the binary plugin's Bytes view.
//
// Pure and DOM-free so the contract is exhaustively testable. Each input
// byte maps to exactly one display unit, and there are only two cases:
//
//   0x20-0x7E  the literal ASCII character
//   everything else
//              uppercase hex in guillemets, such as `‹00›`, `‹0A›`, `‹FF›`
//
// Non-printables were Unicode Control Pictures (U+2400 + byte, and U+2421
// for delete). They are typographically wrong for this surface: each is a
// full-size glyph containing a two- or three-letter abbreviation drawn at a
// fraction of the body size, so at the small monospace block size the label
// is illegible and the reader cannot tell `␁` from `␈` without zooming. Hex
// is the notation the rest of the tooling already speaks, and one form for
// every non-printable byte means the reader learns a single convention.
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

/** Printable ASCII passes through; everything else becomes a hex code. */
const PRINTABLE_MIN = 0x20;
const PRINTABLE_MAX = 0x7e;

/**
 * Class changes allowed across the whole mounted view before the two-tone
 * treatment is withdrawn.
 *
 * Run count tracks how often the content alternates between literal text and
 * byte codes, which is a property of structure rather than of size: a
 * string-dense artifact alternates every few hundred bytes, while
 * high-entropy content alternates roughly every 1.6. Only code runs become
 * elements, so a given run count costs about half that many.
 *
 * Set from measurement on a 7.2 MB record-structured artifact — readable
 * fields separated by control bytes, which is the shape that alternates most
 * per byte while still being worth coloring. Chromium 141, software raster:
 *
 * | Accented spans | DOM nodes | Scroll to end |
 * | --- | --- | --- |
 * | 87k (1 MiB loaded) | 87k | smooth, 4 ms forced layout |
 * | 629k (7.2 MB loaded) | 630k | 97 ms |
 * | 0 (same 7.2 MB) | 692 | 19 ms |
 *
 * So the elements are affordable by the megabyte and expensive by the file.
 * This sits at roughly 200k spans, which keeps the opening view of ordinary
 * mixed content colored — the case the treatment exists for — and withdraws
 * before scrolling degrades. Raising it trades scroll latency for color on
 * files large enough that the color has already stopped being scannable.
 *
 * The budget is spent across the view, not per chunk, because the DOM
 * accumulates across `Load more`, and it is applied as one decision for
 * everything mounted: a treatment that held above some line and not below it
 * reads as a rendering fault rather than as a limit.
 */
export const DEFAULT_ACCENT_RUN_BUDGET = 400000;

/** Fallback when a caller cannot measure the pane. */
export const DEFAULT_CHARS_PER_LINE = 160;

/** @type {string[]} */
const DISPLAY_TABLE = [];
for (let byte = 0; byte < 256; byte += 1) {
  if (byte >= PRINTABLE_MIN && byte <= PRINTABLE_MAX) {
    DISPLAY_TABLE.push(String.fromCharCode(byte));
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
 * Class changes in a byte window, which is how many elements the two-tone
 * treatment would cost.
 *
 * Counted without building any strings, so a caller can decide whether it can
 * afford the treatment before paying for it.
 *
 * @param {Uint8Array} bytes
 * @returns {number}
 */
export function countAccentRuns(bytes) {
  if (bytes.length === 0) {
    return 0;
  }
  let runs = 1;
  let previous = isSpecialByte(bytes[0]);
  for (let index = 1; index < bytes.length; index += 1) {
    const special = isSpecialByte(bytes[index]);
    if (special !== previous) {
      runs += 1;
      previous = special;
    }
  }
  return runs;
}

/**
 * Format one byte range, coalescing adjacent same-class bytes into runs so the
 * DOM never grows to one element per byte.
 *
 * Hex codes come from a fixed internal table and contain no HTML
 * metacharacters, so only literal ASCII runs need escaping.
 *
 * Literal text is left unwrapped and takes the surface's own color; only code
 * runs get an element. That is the cheaper side to wrap for the content this
 * view exists to show, and it means the unaccented fallback below still reads
 * correctly once the surface is told which color to default to.
 *
 * @param {Uint8Array} bytes
 * @param {number} from
 * @param {number} to
 * @param {(value: string) => string} escapeHtml
 * @param {boolean} accent Whether to emit the two-tone elements at all.
 * @returns {string}
 */
function formatRange(bytes, from, to, escapeHtml, accent) {
  if (!accent) {
    return escapeHtml(renderRange(bytes, from, to));
  }
  /** @type {string[]} */
  const parts = [];
  let runStart = from;

  /**
   * @param {number} end
   * @param {boolean} special
   */
  const flush = (end, special) => {
    if (end <= runStart) {
      return;
    }
    const text = renderRange(bytes, runStart, end);
    parts.push(special ? `<span class="binary-byte-code">${text}</span>` : escapeHtml(text));
    runStart = end;
  };

  let runIsSpecial = from < to ? isSpecialByte(bytes[from]) : false;
  for (let index = from; index < to; index += 1) {
    const special = isSpecialByte(bytes[index]);
    if (special !== runIsSpecial) {
      flush(index, runIsSpecial);
      runIsSpecial = special;
    }
  }
  flush(to, runIsSpecial);
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
 * @param {{accent?: boolean}} [options]
 * @returns {{html: string}}
 */
export function formatByteRuns(bytes, escapeHtml, options) {
  return { html: formatRange(bytes, 0, bytes.length, escapeHtml, options?.accent !== false) };
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
 * ``accent`` is the caller's decision, not this function's: whether the view
 * can afford the two-tone treatment depends on everything mounted, not on this
 * window, and the treatment has to be uniform across all of it.
 *
 * @param {Uint8Array} bytes
 * @param {(value: string) => string} escapeHtml
 * @param {{charsPerLine?: number, accent?: boolean}} [options]
 * @returns {{html: string, lines: string[], lineCount: number}}
 */
export function formatByteLines(bytes, escapeHtml, options) {
  const charsPerLine = options?.charsPerLine ?? DEFAULT_CHARS_PER_LINE;
  const accent = options?.accent !== false;
  const ranges = lineRanges(bytes, charsPerLine);
  /** @type {string[]} */
  const lines = [];
  for (const [from, to] of ranges) {
    lines.push(formatRange(bytes, from, to, escapeHtml, accent));
  }
  return {
    html: lines.join("\n"),
    lines,
    lineCount: lines.length,
  };
}
