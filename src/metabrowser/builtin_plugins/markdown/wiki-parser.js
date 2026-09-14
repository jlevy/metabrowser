const MAX_WIKI_SOURCE_CHARACTERS = 2_000_000;
const MAX_WIKI_TARGETS = 4096;
const MAX_WIKI_TARGET_CHARACTERS = 16_384;
// `/api/kpress/render` accepts at most one full text-preview chunk for an
// explicitly transformed source. Keep the Worker reply inside the same contract.
const MAX_TRANSFORMED_SOURCE_BYTES = 8 * 1024 * 1024;
const MAX_UNICODE_CODE_POINT = 0x10ffff;
const MIN_UNICODE_SURROGATE = 0xd800;
const MAX_UNICODE_SURROGATE = 0xdfff;
const MAX_INLINE_DELIMITER_PASSES = 5;

/**
 * Convert Obsidian wiki syntax to inert, sanitizable metadata before Markdown rendering.
 *
 * Fenced code, inline code, ordinary Markdown links, and escaped opening brackets are
 * copied verbatim. The returned spans have no destination until the completed render is
 * resolved against the current inventory.
 *
 * @param {string} source
 */
export function preprocessObsidianWiki(source) {
  if (typeof source !== "string") {
    throw new TypeError("Obsidian preprocessing requires source text");
  }
  if (source.length > MAX_WIKI_SOURCE_CHARACTERS) {
    return incompletePreprocessingResult(source, createWorkMetrics(), "source-too-large");
  }

  const metrics = createWorkMetrics();
  if (!hasPreprocessingTrigger(source, metrics)) {
    return preprocessingResult(source, false, 0, 0, metrics, source.length);
  }

  let targetCount = 0;
  let blockCount = 0;
  let changed = false;
  let targetLimited = false;
  /** @type {{character: string, length: number} | null} */
  let fence = null;
  /** @type {string[]} */
  const headingStack = [];
  const anchorIds = new Set();
  const output = [];
  let outputOffset = 0;
  const outputBudget = createOutputBudget(source);
  const literal = markdownLiteralMask(source);
  metrics.literalMaskCodeUnitsVisited = literal.codeUnitsVisited;
  const lines = createLineCursor(source, metrics);
  let current = lines.next();
  let next = lines.next();

  while (current) {
    const line = source.slice(current.start, current.contentEnd);
    const lineEnding = source.slice(current.contentEnd, current.end);
    const fenceRun = /^ {0,3}(`{3,}|~{3,})/.exec(line)?.[1];
    if (fence) {
      if (
        fenceRun &&
        fenceRun[0] === fence.character &&
        fenceRun.length >= fence.length &&
        line.slice(line.indexOf(fenceRun) + fenceRun.length).trim() === ""
      ) {
        fence = null;
      }
    } else if (fenceRun) {
      fence = { character: fenceRun[0], length: fenceRun.length };
    } else {
      let block = findNamedBlock(line);
      if (block && literal.mask[current.start + block.start]) {
        block = null;
      }
      let blockMarkup = "";
      if (block) {
        const id = `obsidian-block-${block.id}`;
        const idAttribute = anchorIds.has(id) ? "" : ` id="${escapeAttribute(id)}"`;
        blockMarkup = `<span class="metabrowser-wiki-block"${idAttribute} data-mb-wiki-block="${escapeAttribute(block.id)}"></span>`;
        if (!claimReplacement(outputBudget, line.slice(block.start), blockMarkup)) {
          return outputLimitedResult(source, metrics);
        } else {
          anchorIds.add(id);
        }
      }
      const content = block ? line.slice(0, block.start).trimEnd() : line;
      const nextLine = next ? source.slice(next.start, next.contentEnd) : "";
      const firstContentOffset = content.search(/\S/);
      const nextContentOffset = nextLine.search(/\S/);
      // A masked next line (code, HTML, a comment) cannot be a setext
      // underline, but it must not suppress an ATX heading on this line.
      const nextLineMasked =
        next && nextContentOffset !== -1 && literal.mask[next.start + nextContentOffset];
      const heading =
        firstContentOffset !== -1 && literal.mask[current.start + firstContentOffset]
          ? null
          : findMarkdownHeading(content, nextLineMasked ? "" : nextLine);
      const inserted = [];
      if (heading) {
        headingStack.splice(heading.level - 1);
        headingStack[heading.level - 1] = heading.text;
        const hierarchy = headingStack.filter(Boolean);
        for (let index = 0; index < hierarchy.length; index += 1) {
          const key = hierarchy.slice(index).join("#");
          const id = `obsidian-heading-${key}`;
          if (!anchorIds.has(id)) {
            const anchor = `<span class="metabrowser-wiki-heading" id="${escapeAttribute(id)}"></span>${lineEnding || "\n"}`;
            if (claimReplacement(outputBudget, "", anchor)) {
              inserted.push(anchor);
              anchorIds.add(id);
            } else {
              return outputLimitedResult(source, metrics);
            }
          }
        }
      }
      const processed = processInline(
        content,
        MAX_WIKI_TARGETS - targetCount,
        metrics,
        outputBudget,
        literal.mask,
        current.start,
      );
      if (processed.outputLimited) {
        return outputLimitedResult(source, metrics);
      }
      targetCount += processed.targetCount;
      targetLimited ||= processed.targetLimited;
      const lineChanged = inserted.length > 0 || processed.changed || Boolean(block);
      if (lineChanged) {
        output.push(source.slice(outputOffset, current.start), ...inserted, processed.source);
        if (block) {
          blockCount += 1;
          output.push(blockMarkup);
        }
        output.push(lineEnding);
        outputOffset = current.end;
        changed = true;
      }
    }
    current = next;
    next = lines.next();
  }

  if (!changed) {
    return preprocessingResult(source, false, blockCount, targetCount, metrics, source.length);
  }
  output.push(source.slice(outputOffset));
  return preprocessingResult(
    output.join(""),
    true,
    blockCount,
    targetCount,
    metrics,
    source.length,
    targetLimited ? "wiki-target-limit" : null,
  );
}

/** @param {string} source @param {number} budget @param {ReturnType<typeof createWorkMetrics>} metrics @param {ReturnType<typeof createOutputBudget>} outputBudget @param {Uint8Array} literalMask @param {number} sourceOffset */
function processInline(source, budget, metrics, outputBudget, literalMask, sourceOffset) {
  let targetCount = 0;
  let targetLimited = false;
  let changed = false;
  const output = [];
  let literalStart = 0;
  const brackets = createBracketPairs(source, literalMask, sourceOffset, metrics);
  const destinationClose = createScanState();
  const wikiClose = createScanState();
  for (let index = 0; index < source.length; ) {
    metrics.inlineCursorSteps += 1;
    if (literalMask[sourceOffset + index]) {
      index += 1;
      continue;
    }
    if (source[index] === "[" && source[index + 1] === "[" && isEscaped(source, index, metrics)) {
      index += 2;
      continue;
    }
    const markdownLinkEnd = findMarkdownLinkEnd(source, index, brackets, destinationClose, metrics);
    if (markdownLinkEnd !== -1) {
      index = markdownLinkEnd;
      continue;
    }

    const embed = source[index] === "!" && source[index + 1] === "[" && source[index + 2] === "[";
    const link = source[index] === "[" && source[index + 1] === "[";
    if (embed || link) {
      const openingLength = embed ? 3 : 2;
      const closing = findPair(source, index + openingLength, "]", "]", wikiClose, metrics);
      if (closing !== -1 && closing - index - openingLength <= MAX_WIKI_TARGET_CHARACTERS) {
        const authored = source.slice(index + openingLength, closing);
        const parsed = parseOccurrence(authored, embed);
        if (parsed.target) {
          if (targetCount >= budget) {
            targetLimited = true;
            index = closing + 2;
            continue;
          }
          const rendered = renderPlaceholder(parsed, embed);
          if (!claimReplacement(outputBudget, source.slice(index, closing + 2), rendered)) {
            return {
              changed: false,
              outputLimited: true,
              source,
              targetCount: 0,
              targetLimited,
            };
          }
          output.push(source.slice(literalStart, index));
          output.push(rendered);
          targetCount += 1;
          changed = true;
          index = closing + 2;
          literalStart = index;
          continue;
        }
      }
    }

    index += 1;
  }
  if (!changed) {
    return { changed: false, source, targetCount, targetLimited };
  }
  output.push(source.slice(literalStart));
  return { changed: true, source: output.join(""), targetCount, targetLimited };
}

/** Prepare a primary document for KPress without cloning unchanged source through a Worker reply. @param {string} source */
export function preparePrimaryMarkdownSource(source) {
  const prepared = preprocessObsidianWiki(source);
  return Object.freeze({
    blockCount: prepared.blockCount,
    changed: prepared.changed,
    complete: prepared.complete,
    diagnostics: prepared.diagnostics,
    metrics: prepared.metrics,
    source: prepared.changed ? prepared.source : null,
    targetCount: prepared.targetCount,
  });
}

/** Select and preprocess one embedded Markdown region in a single pure operation. @param {string} source @param {string=} fragment */
export function prepareTransclusionMarkdownSource(source, fragment) {
  const selection = selectTransclusionSource(source, fragment);
  if (selection.status !== "selected") {
    return Object.freeze({
      metrics: Object.freeze({ selection: selection.metrics }),
      reason: selection.reason,
      status: /** @type {const} */ ("missing"),
    });
  }
  const prepared = preprocessObsidianWiki(selection.source);
  return Object.freeze({
    blockCount: prepared.blockCount,
    changed: prepared.changed,
    complete: prepared.complete,
    diagnostics: prepared.diagnostics,
    kind: selection.kind,
    metrics: Object.freeze({
      preprocessing: prepared.metrics,
      selection: selection.metrics,
    }),
    source: prepared.source,
    status: /** @type {const} */ ("selected"),
    targetCount: prepared.targetCount,
  });
}

/**
 * Select a whole note, heading section, or named block from Markdown source.
 *
 * The line cursor retains only offsets. Each source code unit participates in at
 * most one line-boundary scan, including missing near-tail selections.
 *
 * @param {string} source
 * @param {string=} fragment
 */
export function selectTransclusionSource(source, fragment) {
  if (typeof source !== "string") {
    throw new TypeError("Transclusion selection requires source text");
  }
  const metrics = createWorkMetrics();
  if (source.length > MAX_WIKI_SOURCE_CHARACTERS) {
    return selectionFailure("source-too-large", metrics);
  }
  if (!fragment) {
    return selected(source, "note", metrics);
  }
  if (fragment.startsWith("obsidian-block-")) {
    return selectNamedBlock(source, fragment.slice("obsidian-block-".length), metrics);
  }
  if (fragment.startsWith("obsidian-heading-")) {
    return selectHeadingSection(source, fragment.slice("obsidian-heading-".length), metrics);
  }
  return selectionFailure("unsupported-location", metrics);
}

/** @param {string} source @param {string} target @param {ReturnType<typeof createWorkMetrics>} metrics */
function selectHeadingSection(source, target, metrics) {
  if (!target) {
    return selectionFailure("missing-location", metrics);
  }
  const lines = createLineCursor(source, metrics);
  const headingStack = [];
  let fence = null;
  let selectedStart = -1;
  let selectedLevel = 0;
  let current = lines.next();
  let next = lines.next();
  while (current) {
    const line = source.slice(current.start, current.contentEnd);
    const fenceRun = /^ {0,3}(`{3,}|~{3,})/.exec(line)?.[1] || null;
    if (fence) {
      if (
        fenceRun &&
        fenceRun[0] === fence.character &&
        fenceRun.length >= fence.length &&
        line.slice(line.indexOf(fenceRun) + fenceRun.length).trim() === ""
      ) {
        fence = null;
      }
    } else if (fenceRun) {
      fence = { character: fenceRun[0], length: fenceRun.length };
    } else {
      const block = findNamedBlock(line);
      const content = block ? line.slice(0, block.start).trimEnd() : line;
      const nextLine = next ? source.slice(next.start, next.contentEnd) : "";
      const heading = findMarkdownHeading(content, nextLine);
      if (heading) {
        if (selectedStart !== -1 && heading.level <= selectedLevel) {
          return selected(source.slice(selectedStart, current.start), "heading", metrics);
        }
        headingStack.splice(heading.level - 1);
        headingStack[heading.level - 1] = heading.text;
        const hierarchy = headingStack.filter(Boolean);
        const matches = hierarchy.some(
          (_heading, offset) => hierarchy.slice(offset).join("#") === target,
        );
        if (selectedStart === -1 && matches) {
          selectedStart = current.start;
          selectedLevel = heading.level;
        }
      }
    }
    current = next;
    next = lines.next();
  }
  return selectedStart === -1
    ? selectionFailure("missing-location", metrics)
    : selected(source.slice(selectedStart), "heading", metrics);
}

/** @param {string} source @param {string} target @param {ReturnType<typeof createWorkMetrics>} metrics */
function selectNamedBlock(source, target, metrics) {
  if (!/^[A-Za-z0-9-]+$/.test(target)) {
    return selectionFailure("missing-location", metrics);
  }
  const lines = createLineCursor(source, metrics);
  let fence = null;
  let blockStart = 0;
  let current = lines.next();
  let next = lines.next();
  while (current) {
    const line = source.slice(current.start, current.contentEnd);
    const lineEnding = source.slice(current.contentEnd, current.end);
    const fenceRun = /^ {0,3}(`{3,}|~{3,})/.exec(line)?.[1] || null;
    if (fence) {
      if (
        fenceRun &&
        fenceRun[0] === fence.character &&
        fenceRun.length >= fence.length &&
        line.slice(line.indexOf(fenceRun) + fenceRun.length).trim() === ""
      ) {
        fence = null;
        blockStart = current.end;
      }
    } else if (fenceRun) {
      fence = { character: fenceRun[0], length: fenceRun.length };
      blockStart = current.end;
    } else if (!line.trim()) {
      blockStart = current.end;
    } else {
      const block = findNamedBlock(line);
      if (block?.id === target) {
        return selected(
          `${source.slice(blockStart, current.start)}${line.slice(0, block.start).trimEnd()}${lineEnding}`,
          "block",
          metrics,
        );
      }
      const nextLine = next ? source.slice(next.start, next.contentEnd) : "";
      if (findMarkdownHeading(line, nextLine) || /^ {0,3}(?:=+|-+)[\t ]*$/.test(line)) {
        blockStart = current.end;
      }
    }
    current = next;
    next = lines.next();
  }
  return selectionFailure("missing-location", metrics);
}

/** @param {string} source @param {"note" | "heading" | "block"} kind @param {ReturnType<typeof createWorkMetrics>} metrics */
function selected(source, kind, metrics) {
  return Object.freeze({
    kind,
    metrics: frozenMetrics(metrics),
    source,
    status: /** @type {const} */ ("selected"),
  });
}

/** @param {string} reason @param {ReturnType<typeof createWorkMetrics>} metrics */
function selectionFailure(reason, metrics) {
  return Object.freeze({
    metrics: frozenMetrics(metrics),
    reason,
    status: /** @type {const} */ ("missing"),
  });
}

function createWorkMetrics() {
  return {
    delimiterSteps: 0,
    inlineCursorSteps: 0,
    literalMaskCodeUnitsVisited: 0,
    lineCodeUnitsVisited: 0,
    triggerCodeUnitsVisited: 0,
  };
}

/** @param {string} source @param {ReturnType<typeof createWorkMetrics>} metrics */
function hasPreprocessingTrigger(source, metrics) {
  for (let index = 0; index < source.length; index += 1) {
    metrics.triggerCodeUnitsVisited += 1;
    const character = source[index];
    if (
      character === "[" ||
      character === "#" ||
      character === "^" ||
      character === "=" ||
      character === "-"
    ) {
      return true;
    }
  }
  return false;
}

/** @param {string} source @param {ReturnType<typeof createWorkMetrics>} metrics */
function createLineCursor(source, metrics) {
  let offset = 0;
  return Object.freeze({
    next() {
      if (offset >= source.length) {
        return null;
      }
      const start = offset;
      while (offset < source.length && source[offset] !== "\n" && source[offset] !== "\r") {
        metrics.lineCodeUnitsVisited += 1;
        offset += 1;
      }
      const contentEnd = offset;
      if (offset < source.length) {
        metrics.lineCodeUnitsVisited += 1;
        const first = source[offset];
        offset += 1;
        if (first === "\r" && source[offset] === "\n") {
          metrics.lineCodeUnitsVisited += 1;
          offset += 1;
        }
      }
      return Object.freeze({ contentEnd, end: offset, start });
    },
  });
}

/** @param {string} source @param {boolean} changed @param {number} blockCount @param {number} targetCount @param {ReturnType<typeof createWorkMetrics>} metrics @param {number} inputLength @param {string | null=} diagnosticCode */
function preprocessingResult(
  source,
  changed,
  blockCount,
  targetCount,
  metrics,
  inputLength,
  diagnosticCode = null,
) {
  assertLinearWork(metrics, inputLength);
  return Object.freeze({
    blockCount,
    changed,
    complete: diagnosticCode === null,
    diagnostics: Object.freeze(diagnosticCode ? [Object.freeze({ code: diagnosticCode })] : []),
    metrics: frozenMetrics(metrics),
    source,
    targetCount,
  });
}

/** @param {ReturnType<typeof createWorkMetrics>} metrics @param {number} inputLength */
function assertLinearWork(metrics, inputLength) {
  if (
    metrics.inlineCursorSteps > inputLength ||
    metrics.delimiterSteps > MAX_INLINE_DELIMITER_PASSES * inputLength ||
    metrics.literalMaskCodeUnitsVisited > 6 * inputLength ||
    metrics.lineCodeUnitsVisited > inputLength ||
    metrics.triggerCodeUnitsVisited > inputLength
  ) {
    throw new Error("Markdown preprocessing exceeded its linear-work invariant");
  }
}

/** @param {string} source @param {ReturnType<typeof createWorkMetrics>} metrics */
function outputLimitedResult(source, metrics) {
  assertLinearWork(metrics, source.length);
  return incompletePreprocessingResult(source, metrics, "transformed-source-byte-limit");
}

/** @param {string} source @param {ReturnType<typeof createWorkMetrics>} metrics @param {string} code */
function incompletePreprocessingResult(source, metrics, code) {
  return Object.freeze({
    blockCount: 0,
    changed: false,
    complete: false,
    diagnostics: Object.freeze([Object.freeze({ code })]),
    metrics: frozenMetrics(metrics),
    source,
    targetCount: 0,
  });
}

/** @param {ReturnType<typeof createWorkMetrics>} metrics */
function frozenMetrics(metrics) {
  return Object.freeze({
    delimiterSteps: metrics.delimiterSteps,
    inlineCursorSteps: metrics.inlineCursorSteps,
    literalMaskCodeUnitsVisited: metrics.literalMaskCodeUnitsVisited,
    lineCodeUnitsVisited: metrics.lineCodeUnitsVisited,
    triggerCodeUnitsVisited: metrics.triggerCodeUnitsVisited,
  });
}

/** @param {string} authored @param {boolean} embed */
function parseOccurrence(authored, embed) {
  const separator = authored.indexOf("|");
  const target = (separator === -1 ? authored : authored.slice(0, separator)).trim();
  const display = separator === -1 ? "" : authored.slice(separator + 1).trim();
  const mediaSize = embed ? parseMediaSize(display) : null;
  return Object.freeze({
    display,
    label: display && !mediaSize ? display : target,
    mediaSize,
    target,
  });
}

/** @param {{display: string, label: string, mediaSize: {width: number, height?: number} | null, target: string}} occurrence @param {boolean} embed */
function renderPlaceholder(occurrence, embed) {
  const attributes = [
    `class="metabrowser-wiki-${embed ? "embed" : "link"}"`,
    `data-mb-wiki-target="${escapeAttribute(occurrence.target)}"`,
    `data-mb-wiki-action="${embed ? "embed" : "navigate"}"`,
  ];
  if (occurrence.mediaSize) {
    attributes.push(`data-mb-wiki-width="${occurrence.mediaSize.width}"`);
    if (occurrence.mediaSize.height) {
      attributes.push(`data-mb-wiki-height="${occurrence.mediaSize.height}"`);
    }
  }
  return `<span ${attributes.join(" ")}>${escapeText(occurrence.label)}</span>`;
}

/** @param {string} value */
function parseMediaSize(value) {
  const match = /^(\d{1,5})(?:x(\d{1,5}))?$/.exec(value);
  if (!match) {
    return null;
  }
  const width = Number(match[1]);
  const height = match[2] ? Number(match[2]) : undefined;
  if (width < 1 || width > 10_000 || (height !== undefined && (height < 1 || height > 10_000))) {
    return null;
  }
  return height ? Object.freeze({ height, width }) : Object.freeze({ width });
}

/** @param {string} line */
export function findNamedBlock(line) {
  const match = /(?:^|\s+)\^([A-Za-z0-9-]+)\s*$/.exec(line);
  if (!match || insideInlineCode(line, match.index)) {
    return null;
  }
  return Object.freeze({ id: match[1], start: match.index });
}

/** @param {string} line @param {string} nextLine */
export function findMarkdownHeading(line, nextLine) {
  const match = /^ {0,3}(#{1,6})[\t ]+(.+?)[\t ]*#*[\t ]*$/.exec(line);
  if (match) {
    const text = headingText(match[2]);
    return text ? Object.freeze({ level: match[1].length, text }) : null;
  }
  const setext = /^ {0,3}(=+|-+)[\t ]*$/.exec(nextLine);
  if (!setext) {
    return null;
  }
  const text = headingText(line);
  return text ? Object.freeze({ level: setext[1][0] === "=" ? 1 : 2, text }) : null;
}

/** @param {string} value */
function headingText(value) {
  return value
    .replace(/!?(\[([^\]]+)\])\([^)]*\)/g, "$2")
    .replace(/!?(\[([^\]]+)\])\[[^\]]*\]/g, "$2")
    .replace(/`+([^`]*)`+/g, "$1")
    .replace(/<[^>]*>/g, "")
    .replace(/[~*_]/g, "")
    .replace(/\\([!"#$%&'()*+,\-./:;<=>?@[\]^_`{|}~])/g, "$1")
    .replace(/&(?:#(\d+)|#x([\dA-Fa-f]+)|amp|apos|gt|lt|quot);/g, decodeHeadingEntity)
    .replace(/[\t ]+/g, " ")
    .trim();
}

/** @param {string} entity @param {string | undefined} decimal @param {string | undefined} hexadecimal */
function decodeHeadingEntity(entity, decimal, hexadecimal) {
  const digits = decimal || hexadecimal;
  if (digits) {
    const codePoint = Number.parseInt(digits, hexadecimal ? 16 : 10);
    return Number.isSafeInteger(codePoint) &&
      codePoint <= MAX_UNICODE_CODE_POINT &&
      (codePoint < MIN_UNICODE_SURROGATE || codePoint > MAX_UNICODE_SURROGATE)
      ? String.fromCodePoint(codePoint)
      : entity;
  }
  return { "&amp;": "&", "&apos;": "'", "&gt;": ">", "&lt;": "<", "&quot;": '"' }[entity] ?? entity;
}

/** @param {string} source @param {number} offset */
function insideInlineCode(source, offset) {
  let delimiter = 0;
  for (let index = 0; index < offset; ) {
    if (source[index] !== "`") {
      index += 1;
      continue;
    }
    const run = repeatedCharacterLength(source, index, "`");
    delimiter = delimiter === run ? 0 : delimiter || run;
    index += run;
  }
  return delimiter !== 0;
}

/**
 * @param {string} source
 * @param {number} index
 * @param {ReturnType<typeof createBracketPairs>} brackets
 * @param {ReturnType<typeof createScanState>} destinationClose
 * @param {ReturnType<typeof createWorkMetrics>} metrics
 */
function findMarkdownLinkEnd(source, index, brackets, destinationClose, metrics) {
  const image = source[index] === "!" && source[index + 1] === "[" && source[index + 2] !== "[";
  const link = source[index] === "[" && source[index + 1] !== "[";
  if (!image && !link) {
    return -1;
  }
  const labelEnd = brackets.closing(index + (image ? 1 : 0));
  if (labelEnd === -1) {
    return -1;
  }
  if (source[labelEnd + 1] === "(") {
    const destinationEnd = findCharacter(source, labelEnd + 2, ")", destinationClose, metrics);
    return destinationEnd === -1 ? -1 : destinationEnd + 1;
  }
  if (source[labelEnd + 1] === "[") {
    const referenceEnd = brackets.closing(labelEnd + 1);
    return referenceEnd === -1 ? -1 : referenceEnd + 1;
  }
  // A label closed by anything else is a task-list checkbox, a shortcut
  // reference, or plain text; it does not hide the wiki syntax after it.
  return -1;
}

/** @param {string} source @param {number} index @param {string} character @param {ReturnType<typeof createWorkMetrics>=} metrics */
function repeatedCharacterLength(source, index, character, metrics) {
  let end = index;
  while (source[end] === character) {
    if (metrics) {
      metrics.delimiterSteps += 1;
    }
    end += 1;
  }
  return end - index;
}

function createScanState() {
  return { cursor: 0, match: -1 };
}

/**
 * Pair ordinary Markdown brackets on one line the way CommonMark does: each
 * unescaped `]` outside literal text closes the nearest still-open `[`. A link
 * label therefore ends at its own opener's closer, so a task-list checkbox, a
 * shortcut reference, or an unmatched `[` cannot borrow a later link's `](` and
 * hide the wiki syntax between them. The single stack pass runs on first use
 * and is charged one delimiter step per code unit; every lookup is O(1).
 *
 * @param {string} source
 * @param {Uint8Array} literalMask
 * @param {number} sourceOffset
 * @param {ReturnType<typeof createWorkMetrics>} metrics
 */
function createBracketPairs(source, literalMask, sourceOffset, metrics) {
  /**
   * One array serves as both result and stack. A closed opener stores its
   * closer plus one. An opener still on the stack stores the negated position
   * of the opener beneath it, offset by one, so a finished pass leaves every
   * unmatched opener at zero or below.
   * @type {Int32Array | null}
   */
  let pairs = null;

  function build() {
    const built = new Int32Array(source.length);
    let top = -1;
    let backslashes = 0;
    for (let index = 0; index < source.length; index += 1) {
      metrics.delimiterSteps += 1;
      const character = source[index];
      if (literalMask[sourceOffset + index]) {
        backslashes = 0;
        continue;
      }
      const escaped = backslashes % 2 === 1;
      backslashes = character === "\\" ? backslashes + 1 : 0;
      if (escaped) {
        continue;
      }
      if (character === "[") {
        built[index] = -(top + 1);
        top = index;
      } else if (character === "]" && top !== -1) {
        const opener = top;
        top = -built[opener] - 1;
        built[opener] = index + 1;
      }
    }
    return built;
  }

  return Object.freeze({
    /** @param {number} opener @returns {number} */
    closing(opener) {
      pairs ||= build();
      const value = pairs[opener];
      return value > 0 ? value - 1 : -1;
    },
  });
}

/** @param {string} source @param {number} start @param {string} first @param {string} second @param {ReturnType<typeof createScanState>} state @param {ReturnType<typeof createWorkMetrics>} metrics */
function findPair(source, start, first, second, state, metrics) {
  if (state.match >= start) {
    return state.match;
  }
  if (state.match !== -1) {
    state.cursor = state.match + 1;
    state.match = -1;
  }
  state.cursor = Math.max(state.cursor, start);
  while (state.cursor + 1 < source.length) {
    const cursor = state.cursor;
    state.cursor += 1;
    metrics.delimiterSteps += 1;
    if (source[cursor] === first && source[cursor + 1] === second) {
      state.match = cursor;
      return cursor;
    }
  }
  state.cursor = source.length;
  return -1;
}

/** @param {string} source @param {number} start @param {string} character @param {ReturnType<typeof createScanState>} state @param {ReturnType<typeof createWorkMetrics>} metrics */
function findCharacter(source, start, character, state, metrics) {
  if (state.match >= start) {
    return state.match;
  }
  if (state.match !== -1) {
    state.cursor = state.match + 1;
    state.match = -1;
  }
  state.cursor = Math.max(state.cursor, start);
  while (state.cursor < source.length) {
    const cursor = state.cursor;
    state.cursor += 1;
    metrics.delimiterSteps += 1;
    if (source[cursor] === character) {
      state.match = cursor;
      return cursor;
    }
  }
  return -1;
}

/**
 * Mark fenced code, indented code, HTML comments, and exact-run CommonMark code
 * spans. The reverse successor table makes unmatched and asymmetric backtick
 * runs literal without rescanning a suffix for each opener. Code spans cannot
 * cross a block boundary, so pairing restarts at blank lines, headings, and
 * wholly literal lines.
 *
 * @param {string} source
 */
export function markdownLiteralMask(source) {
  const mask = new Uint8Array(source.length);
  let codeUnitsVisited = 0;
  let offset = 0;
  let fence = null;
  let inComment = false;
  let rawLiteralElement = "";
  let rawBlockUntilBlank = false;
  /** Line-start offsets where a code span must not continue, ascending. */
  const blockBoundaries = [];
  while (offset < source.length) {
    const start = offset;
    while (offset < source.length && source[offset] !== "\n" && source[offset] !== "\r") {
      offset += 1;
      codeUnitsVisited += 1;
    }
    const contentEnd = offset;
    if (offset < source.length) {
      const first = source[offset];
      offset += 1;
      codeUnitsVisited += 1;
      if (first === "\r" && source[offset] === "\n") {
        offset += 1;
        codeUnitsVisited += 1;
      }
    }
    const line = source.slice(start, contentEnd);
    const fenceRun = inComment ? null : /^ {0,3}(`{3,}|~{3,})/.exec(line)?.[1] || null;
    // An open fence owns every line until its closing fence. Raw-HTML and
    // indentation rules inside it are content, not block structure.
    if (fence) {
      mask.fill(1, start, offset);
      blockBoundaries.push(start, offset);
      if (
        fenceRun &&
        fenceRun[0] === fence.character &&
        fenceRun.length >= fence.length &&
        line.slice(line.indexOf(fenceRun) + fenceRun.length).trim() === ""
      ) {
        fence = null;
      }
      continue;
    }
    if (!inComment && (line.trim() === "" || /^ {0,3}#{1,6}(?:[\t ]|$)/.test(line))) {
      blockBoundaries.push(start, offset);
    }
    if (rawBlockUntilBlank) {
      if (line.trim() === "") {
        rawBlockUntilBlank = false;
      } else {
        mask.fill(1, start, offset);
        blockBoundaries.push(start, offset);
      }
      continue;
    }
    if (rawLiteralElement) {
      mask.fill(1, start, offset);
      blockBoundaries.push(start, offset);
      if (new RegExp(`</${rawLiteralElement}\\s*>`, "i").test(line)) {
        rawLiteralElement = "";
      }
      continue;
    }
    const rawOpening = inComment
      ? null
      : /^ {0,3}<(script|pre|style|textarea)(?:\s|>|$)/i.exec(line);
    if (rawOpening) {
      rawLiteralElement = rawOpening[1].toLowerCase();
      mask.fill(1, start, offset);
      blockBoundaries.push(start, offset);
      if (new RegExp(`</${rawLiteralElement}\\s*>`, "i").test(line)) {
        rawLiteralElement = "";
      }
      continue;
    }
    const rawBlockOpening = inComment
      ? null
      : /^ {0,3}<\/?(?:address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)(?:\s|\/?>|$)/i.exec(
          line,
        );
    if (rawBlockOpening) {
      rawBlockUntilBlank = true;
      mask.fill(1, start, offset);
      blockBoundaries.push(start, offset);
      continue;
    }
    if (fenceRun) {
      fence = { character: fenceRun[0], length: fenceRun.length };
      mask.fill(1, start, offset);
      blockBoundaries.push(start, offset);
      continue;
    }
    if (!inComment && /^(?: {4}|\t)/.test(line)) {
      mask.fill(1, start, offset);
      blockBoundaries.push(start, offset);
      continue;
    }
    for (let cursor = start; cursor < contentEnd; ) {
      codeUnitsVisited += 1;
      if (!inComment && source.startsWith("<!--", cursor)) {
        mask.fill(1, cursor, Math.min(cursor + 4, contentEnd));
        cursor += 4;
        inComment = true;
      } else if (inComment && source.startsWith("-->", cursor)) {
        mask.fill(1, cursor, Math.min(cursor + 3, contentEnd));
        cursor += 3;
        inComment = false;
      } else {
        if (inComment) {
          mask[cursor] = 1;
        }
        cursor += 1;
      }
    }
  }

  const nextEqualRun = new Int32Array(source.length);
  const lastRunByLength = new Map();
  let boundary = blockBoundaries.length - 1;
  for (let index = source.length - 1; index >= 0; ) {
    codeUnitsVisited += 1;
    if (boundary >= 0 && index < blockBoundaries[boundary]) {
      // Crossing into an earlier block: no later run can close a span here.
      lastRunByLength.clear();
      while (boundary >= 0 && index < blockBoundaries[boundary]) {
        boundary -= 1;
      }
    }
    if (mask[index] || source[index] !== "`") {
      index -= 1;
      continue;
    }
    const end = index + 1;
    while (index >= 0 && !mask[index] && source[index] === "`") {
      index -= 1;
    }
    const start = index + 1;
    const length = end - start;
    const next = lastRunByLength.get(length);
    if (next !== undefined) {
      nextEqualRun[start] = next + 1;
    }
    lastRunByLength.set(length, start);
  }

  for (let index = 0; index < source.length; ) {
    codeUnitsVisited += 1;
    if (mask[index] || source[index] !== "`") {
      index += 1;
      continue;
    }
    let end = index + 1;
    while (end < source.length && !mask[end] && source[end] === "`") {
      end += 1;
    }
    const closing = nextEqualRun[index] - 1;
    if (closing >= 0) {
      const spanEnd = closing + (end - index);
      mask.fill(1, index, spanEnd);
      codeUnitsVisited += spanEnd - index;
      index = spanEnd;
    } else {
      index = end;
    }
  }
  return Object.freeze({ codeUnitsVisited, mask });
}

/** @param {string} source */
function createOutputBudget(source) {
  return { bytes: utf8ByteLength(source), limit: MAX_TRANSFORMED_SOURCE_BYTES };
}

/** @param {ReturnType<typeof createOutputBudget>} budget @param {string} original @param {string} replacement */
function claimReplacement(budget, original, replacement) {
  const next = budget.bytes - utf8ByteLength(original) + utf8ByteLength(replacement);
  if (next > budget.limit) {
    return false;
  }
  budget.bytes = next;
  return true;
}

/** @param {string} value */
function utf8ByteLength(value) {
  return new TextEncoder().encode(value).byteLength;
}

/** @param {string} source @param {number} index @param {ReturnType<typeof createWorkMetrics>} metrics */
function isEscaped(source, index, metrics) {
  let escapes = 0;
  for (let probe = index - 1; probe >= 0 && source[probe] === "\\"; probe -= 1) {
    metrics.delimiterSteps += 1;
    escapes += 1;
  }
  return escapes % 2 === 1;
}

/** @param {string} value */
function escapeAttribute(value) {
  return escapeText(value).replaceAll('"', "&quot;");
}

/** @param {string} value */
function escapeText(value) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}
