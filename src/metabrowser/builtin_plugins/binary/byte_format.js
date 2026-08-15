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
 * Render a byte window as HTML, coalescing adjacent same-class bytes into
 * runs so the DOM never grows to one element per byte.
 *
 * Substitute glyphs come from a fixed internal table and contain no HTML
 * metacharacters, so only literal ASCII runs need escaping.
 *
 * @param {Uint8Array} bytes
 * @param {(value: string) => string} escapeHtml
 * @param {number} [runBudget] Accented runs allowed before the accent is dropped.
 * @returns {{html: string, accentDropped: boolean}}
 */
export function formatByteRuns(bytes, escapeHtml, runBudget = DEFAULT_ACCENT_RUN_BUDGET) {
  /** @type {string[]} */
  const parts = [];
  let runStart = 0;
  let runIsSpecial = false;
  let accentedRuns = 0;
  let index = 0;

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

  for (; index < bytes.length; index += 1) {
    const special = isSpecialByte(bytes[index]);
    if (index > runStart) {
      if (special === runIsSpecial) {
        continue;
      }
      flush(index);
    }
    if (special && accentedRuns >= runBudget) {
      break;
    }
    if (special) {
      accentedRuns += 1;
    }
    runIsSpecial = special;
  }

  flush(index);
  if (index < bytes.length) {
    // The budget ran out mid-window. Render the rest as one plain run: the
    // glyph sequence is byte-for-byte unchanged, only the accent is gone.
    parts.push(escapeHtml(renderRange(bytes, index, bytes.length)));
    return { html: parts.join(""), accentDropped: true };
  }
  return { html: parts.join(""), accentDropped: false };
}
