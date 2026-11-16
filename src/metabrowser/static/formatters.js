// Locale-aware numeric formatting, the conventional-commit split of a commit's or a pull
// request's title, a count summary's parts and their one painter, and the words a change
// set's summary says, shared by the shell and plugins.

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

  // A count summary's parts (`MetabrowserCountPart`) and their one painter, for the shell and,
  // through the SDK, plugins (docs/design-system.md, "Count Summaries Bold Their Numbers").
  // "12,797 files" is `[{number: "12,797"}, " files"]`, and its text is the parts joined.
  const SUMMARY_NUMBER_CLASS = "summary-number";
  const SUMMARY_PUNCTUATION_CLASS = "summary-punctuation";
  const FILE_CHANGE_STATUS_CLASS = "file-change-status";
  const VISUALLY_HIDDEN_CLASS = "visually-hidden";

  /**
   * Words as their text, or a span's class, attributes, and text or children.
   * @typedef {string | {className: string, attributes?: Array<[string, string]>, text?: string, children?: Paint[]}} Paint
   */

  /**
   * A part's paint. A separator is hidden from assistive technology, and its `spoken`
   * follows it in a span for a screen reader alone.
   * @param {MetabrowserCountPart} part
   * @returns {Paint[]}
   */
  function countPartPaints(part) {
    if (typeof part === "string") {
      return [part];
    }
    if ("number" in part) {
      return [{ className: SUMMARY_NUMBER_CLASS, text: part.number }];
    }
    if ("status" in part) {
      return [
        {
          className: FILE_CHANGE_STATUS_CLASS,
          text: part.letter,
          attributes: [["data-file-status", part.status]],
        },
      ];
    }
    if ("separator" in part) {
      /** @type {Paint} */
      const dot = {
        className: SUMMARY_PUNCTUATION_CLASS,
        text: part.separator,
        attributes: [["aria-hidden", "true"]],
      };
      return part.spoken === undefined
        ? [dot]
        : [dot, { className: VISUALLY_HIDDEN_CLASS, text: part.spoken }];
    }
    return [{ className: SUMMARY_PUNCTUATION_CLASS, text: part.punctuation }];
  }

  /**
   * @param {Document} doc
   * @param {Paint} paint
   * @returns {Node | string}
   */
  function paintNode(doc, paint) {
    if (typeof paint === "string") {
      return paint;
    }
    const span = doc.createElement("span");
    span.className = paint.className;
    for (const [name, value] of paint.attributes ?? []) {
      span.setAttribute(name, value);
    }
    if (paint.children === undefined) {
      span.textContent = paint.text ?? "";
    } else {
      span.append(...paint.children.map((child) => paintNode(doc, child)));
    }
    return span;
  }

  /**
   * @param {Paint} paint
   * @returns {string}
   */
  function paintHtml(paint) {
    if (typeof paint === "string") {
      return escaped(paint);
    }
    const attributes = (paint.attributes ?? [])
      .map(([name, value]) => ` ${name}="${escaped(value)}"`)
      .join("");
    const content =
      paint.children === undefined
        ? escaped(paint.text ?? "")
        : paint.children.map(paintHtml).join("");
    return `<span class="${paint.className}"${attributes}>${content}</span>`;
  }

  /**
   * A count summary's nodes. A caller puts one phrase's nodes in one inline element: in a
   * flex line, each would be an item of its own.
   * @param {Document} doc
   * @param {MetabrowserCountParts} parts
   * @returns {Array<Node | string>}
   */
  function countPartsNodes(doc, parts) {
    return parts.flatMap(countPartPaints).map((paint) => paintNode(doc, paint));
  }

  /**
   * `countPartsNodes` as escaped markup.
   * @param {MetabrowserCountParts} parts
   * @returns {string}
   */
  function countPartsHtml(parts) {
    return parts.flatMap(countPartPaints).map(paintHtml).join("");
  }

  /**
   * The text the parts read, without a separator's `spoken`.
   * @param {MetabrowserCountParts} parts
   * @returns {string}
   */
  function countText(parts) {
    return parts
      .map((part) =>
        typeof part === "string"
          ? part
          : "number" in part
            ? part.number
            : "letter" in part
              ? part.letter
              : "separator" in part
                ? part.separator
                : part.punctuation,
      )
      .join("");
  }

  const MINUS = "−";

  // A brief change line, "10 A, 5 D, 4 M · +1,234 −567", the one component for a change set
  // said in brief (docs/design-system.md, "Brief Change Line"; the SDK's `changeLine` and
  // `changeLineNodes`).
  const CHANGE_LINE_CLASS = "change-line";
  const CHANGE_LINE_GROUP_CLASS = "change-line-group";
  const CHANGE_LINE_STATUSES_CLASS = "change-line-statuses";
  const CHANGE_LINE_STATS_CLASS = "change-line-stats";

  /**
   * A brief change line, each count written with *formatCount* and an unknown one as "?":
   * `text` as it reads, and `label` in words, "10 added, 5 deleted, 4 modified; 1,234 lines
   * added, 567 deleted".
   * @param {MetabrowserChangeLineInput} change
   * @param {(count: number) => string} formatCount
   * @returns {MetabrowserChangeLine}
   */
  function changeLine(change, formatCount) {
    /** @param {number | null} count */
    const written = (count) => (count === null ? "?" : formatCount(count));
    /** @type {MetabrowserCountParts} */
    const statusParts = change.statuses.flatMap((entry, at) => [
      ...(at === 0 ? [] : [{ punctuation: "," }, " "]),
      { number: written(entry.count) },
      " ",
      { status: entry.status, letter: entry.letter },
    ]);
    const statuses = countText(statusParts);
    const added = written(change.additions);
    const deleted = written(change.deletions);
    const additions = `+${added}`;
    const deletions = `${MINUS}${deleted}`;
    const totals = `${additions} ${deletions}`;
    const text = statuses === "" ? totals : `${statuses} · ${totals}`;
    const lines =
      change.additions === null && change.deletions === null
        ? "line counts unknown"
        : `${added} ${change.additions === 1 ? "line" : "lines"} added, ${deleted} deleted`;
    const words = change.statuses
      .map((entry) => `${written(entry.count)} ${entry.word}`)
      .join(", ");
    const label = words === "" ? lines : `${words}; ${lines}`;
    return { statusParts, additions, deletions, text, label };
  }

  /**
   * One `span.change-line`: its statuses and the dot after them as one item, so a wrap
   * breaks after the dot, then its line totals. *options.spoken* is said in the dot's place.
   * @param {MetabrowserChangeLine} line
   * @param {MetabrowserChangeLineOptions} [options]
   * @returns {Paint}
   */
  function changeLinePaint(line, options = {}) {
    /** @type {Paint[]} */
    const children = [];
    if (line.statusParts.length > 0) {
      children.push({
        className: CHANGE_LINE_GROUP_CLASS,
        children: [
          {
            className: CHANGE_LINE_STATUSES_CLASS,
            children: line.statusParts.flatMap(countPartPaints),
          },
          ...countPartPaints(
            options.spoken === undefined
              ? { separator: "·" }
              : { separator: "·", spoken: options.spoken },
          ),
        ],
      });
    }
    children.push({
      className: CHANGE_LINE_STATS_CLASS,
      children: [
        { className: "diff-stat-add", text: line.additions },
        { className: "diff-stat-del", text: line.deletions },
      ],
    });
    return { className: CHANGE_LINE_CLASS, children };
  }

  /**
   * @param {Document} doc
   * @param {MetabrowserChangeLine} line
   * @param {MetabrowserChangeLineOptions} [options]
   * @returns {Array<Node | string>}
   */
  function changeLineNodes(doc, line, options) {
    return [paintNode(doc, changeLinePaint(line, options))];
  }

  /**
   * @param {MetabrowserChangeLine} line
   * @param {MetabrowserChangeLineOptions} [options]
   * @returns {string}
   */
  function changeLineHtml(line, options) {
    return paintHtml(changeLinePaint(line, options));
  }

  /**
   * What every summary of a change set says: its file count, "35 files changed", and its
   * brief change line (docs/design-system.md, "Diff Summary").
   * @param {{files: number | null, additions: number | null, deletions: number | null, exact: boolean}} totals
   * @param {MetabrowserChangeLineInput["statuses"]} entries
   * @param {(count: number) => string} formatCount
   * @returns {MetabrowserChangedFilesSummary}
   */
  function changeSummary(totals, entries, formatCount) {
    /** @type {MetabrowserCountParts} */
    const filesParts = [
      { number: totals.files === null ? "?" : formatCount(totals.files) },
      ` ${totals.files === 1 ? "file" : "files"} changed`,
    ];
    const line = changeLine(
      { statuses: entries, additions: totals.additions, deletions: totals.deletions },
      formatCount,
    );
    const files = countText(filesParts);
    const estimated = !totals.exact;
    const text = `${files} · ${line.text}${estimated ? " (estimated)" : ""}`;
    const label = `${files}${entries.length === 0 ? ";" : ":"} ${line.label}${estimated ? ", estimated" : ""}`;
    return { filesParts, line, estimated, text, label };
  }

  window.MetabrowserFormatters = Object.freeze({
    age,
    ageClass,
    changeLine,
    changeLineHtml,
    changeLineNodes,
    changeSummary,
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
