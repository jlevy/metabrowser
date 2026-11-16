// Locale-aware numeric formatting, the conventional-commit split of a commit's or a pull
// request's title, and a count summary's bold numbers, shared by the shell and plugins.

(() => {
  const integerFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
  const byteUnits = ["B", "KB", "MB", "GB", "TB", "PB"];
  /** Byte counts above this boundary receive the shared stronger emphasis. */
  const SIZE_LARGE_THRESHOLD_BYTES = 1024 * 1024;
  /** File counts at or above this boundary receive the shared stronger emphasis. */
  const COUNT_LARGE_THRESHOLD = 1000;

  /** @param {number} value */
  function formatBytes(value) {
    let amount = Number.isFinite(value) && value > 0 ? value : 0;
    let unit = 0;
    while (amount >= 1024 && unit < byteUnits.length - 1) {
      amount /= 1024;
      unit += 1;
    }
    if (unit === 0) {
      return `${Math.round(amount)} B`;
    }
    return `${amount.toFixed(1)} ${byteUnits[unit]}`;
  }

  /** @param {number} value */
  function formatInteger(value) {
    return integerFormatter.format(Math.max(0, Math.trunc(Number(value) || 0)));
  }

  /** @param {number} value */
  function formatFileCount(value) {
    const count = Math.max(0, Math.trunc(Number(value) || 0));
    return `${formatInteger(count)} ${count === 1 ? "file" : "files"}`;
  }

  /** @param {number} value */
  function sizeClass(value) {
    return (Number(value) || 0) > SIZE_LARGE_THRESHOLD_BYTES ? "size-large" : "";
  }

  /** @param {number} value */
  function countClass(value) {
    return (Number(value) || 0) >= COUNT_LARGE_THRESHOLD ? "count-large" : "";
  }

  // Age tiers, coarsest first, as [suffix, milliseconds, class].
  // One table so every age anywhere abbreviates and colours the same:
  // an age is an age, whether it belongs to a file or a commit.
  /** @type {ReadonlyArray<readonly [string, number, string]>} */
  const AGE_TIERS = Object.freeze([
    ["y", 365 * 24 * 60 * 60 * 1000, "age-old"],
    ["mo", 30 * 24 * 60 * 60 * 1000, "age-old"],
    ["w", 7 * 24 * 60 * 60 * 1000, "age-wk"],
    ["d", 24 * 60 * 60 * 1000, "age-day"],
    ["h", 60 * 60 * 1000, "age-hr"],
    ["m", 60 * 1000, "age-min"],
  ]);

  /**
   * Compact or relative age and its tier class for an epoch-seconds timestamp.
   *
   * @param {number} epochSeconds
   * @param {{style?: "compact" | "relative"}} [options]
   * @returns {{label: string, className: string}}
   */
  function age(epochSeconds, options = {}) {
    const value = Number(epochSeconds);
    if (!Number.isFinite(value) || value <= 0) {
      return { label: "", className: "" };
    }
    const delta = Date.now() - value * 1000;
    const elapsed = Math.abs(delta);
    const relative = options.style === "relative";
    for (const [suffix, span, className] of AGE_TIERS) {
      if (elapsed >= span) {
        const amount = `${Math.round(elapsed / span)}${suffix}`;
        return {
          label: relative ? (delta < 0 ? `in ${amount}` : `${amount} ago`) : amount,
          className,
        };
      }
    }
    return { label: relative ? "just now" : "<1m", className: "age-sec" };
  }

  /** @param {number} epochSeconds @returns {string} */
  function ageClass(epochSeconds) {
    return age(epochSeconds).className;
  }

  // A title's conventional-commit prefix, "feat(ledger):", is drawn regular and the rest at
  // the title's weight (docs/design-system.md, "Titles"): a type of lowercase letters, an
  // optional scope of anything but parentheses, an optional "!", and the colon, at most 16
  // code points, then whitespace and more of the title. The match is linear: each part is a
  // run of one class, which the first character outside it ends.
  const TITLE_PREFIX = /^[a-z]+(?:\([^()]+\))?!?:(?=\s+\S)/u;
  const TITLE_PREFIX_MAX_CHARS = 16;
  /** The one class that sets a prefix's weight (static/styles.css). */
  const TITLE_PREFIX_CLASS = "title-prefix";
  /** @type {Record<string, string>} */
  const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  /** @param {string} text */
  const escaped = (text) => text.replace(/[&<>"']/g, (character) => ESCAPES[character]);

  /**
   * A title's prefix and the rest after it, which together are the title, or null.
   * @param {string} title
   * @returns {{prefix: string, rest: string} | null}
   */
  function titlePrefix(title) {
    const match = typeof title === "string" ? TITLE_PREFIX.exec(title) : null;
    if (match === null || Array.from(match[0]).length > TITLE_PREFIX_MAX_CHARS) {
      return null;
    }
    return { prefix: match[0], rest: title.slice(match[0].length) };
  }

  /**
   * A title element's nodes: the prefix in a `span.title-prefix`, then the rest; with no
   * prefix, the title alone. `part(text, start)` makes a part's nodes, so a caller can mark
   * matches in it; by default a part is its text.
   * @param {Document} doc
   * @param {string} title
   * @param {(text: string, start: number) => Array<Node | string>} [part]
   * @returns {Array<Node | string>}
   */
  function titleNodes(doc, title, part = (text) => [text]) {
    const split = titlePrefix(title);
    if (split === null) {
      return part(title, 0);
    }
    const prefix = doc.createElement("span");
    prefix.className = TITLE_PREFIX_CLASS;
    prefix.append(...part(split.prefix, 0));
    return [prefix, ...part(split.rest, split.prefix.length)];
  }

  /**
   * `titleNodes` as escaped markup; with no prefix, the escaped title alone.
   * @param {string} title
   * @returns {string}
   */
  function titleHtml(title) {
    const split = titlePrefix(title);
    if (split === null) {
      return escaped(String(title));
    }
    return `<span class="${TITLE_PREFIX_CLASS}">${escaped(split.prefix)}</span>${escaped(split.rest)}`;
  }

  // A count summary's numbers are bold and its words keep the line's weight
  // (docs/design-system.md, "Count Summaries Bold Their Numbers"). Every count summary the
  // shell paints comes in one shape of parts: the words as strings, and each number, the
  // whole figure with its marks, sign, "+", or unit, as `{number}`. "12,797 files" is
  // `[{number: "12,797"}, " files"]`, and its text is the parts joined.
  /** The one class that sets a count summary's number's weight (static/styles.css). */
  const SUMMARY_NUMBER_CLASS = "summary-number";

  /**
   * A count summary's nodes: each number in a `span.summary-number`, the words as text. A
   * caller puts them in one inline element: in a flex line, each would be an item of its
   * own, parted by the line's gap and read as runs of their own.
   * @param {Document} doc
   * @param {MetabrowserCountParts} parts
   * @returns {Array<Node | string>}
   */
  function countPartsNodes(doc, parts) {
    return parts.map((part) => {
      if (typeof part === "string") {
        return part;
      }
      const number = doc.createElement("span");
      number.className = SUMMARY_NUMBER_CLASS;
      number.textContent = part.number;
      return number;
    });
  }

  /**
   * `countPartsNodes` as escaped markup.
   * @param {MetabrowserCountParts} parts
   * @returns {string}
   */
  function countPartsHtml(parts) {
    return parts
      .map((part) =>
        typeof part === "string"
          ? escaped(part)
          : `<span class="${SUMMARY_NUMBER_CLASS}">${escaped(part.number)}</span>`,
      )
      .join("");
  }

  window.MetabrowserFormatters = Object.freeze({
    age,
    ageClass,
    countClass,
    countPartsHtml,
    countPartsNodes,
    formatBytes,
    formatFileCount,
    formatInteger,
    sizeClass,
    titleHtml,
    titleNodes,
    titlePrefix,
  });
})();
