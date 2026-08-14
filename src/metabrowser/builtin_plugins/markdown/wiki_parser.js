const MAX_WIKI_SOURCE_CHARACTERS = 2_000_000;
const MAX_WIKI_TARGETS = 4096;
const MAX_WIKI_TARGET_CHARACTERS = 16_384;

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
    return Object.freeze({ blockCount: 0, changed: false, source, targetCount: 0 });
  }

  let targetCount = 0;
  let blockCount = 0;
  let changed = false;
  /** @type {{character: string, length: number} | null} */
  let fence = null;
  const output = [];

  for (const lineWithEnding of source.match(/.*(?:\r\n|\n|\r|$)/g) || []) {
    if (!lineWithEnding) {
      continue;
    }
    const lineEnding = /\r\n$|[\n\r]$/.exec(lineWithEnding)?.[0] || "";
    const line = lineEnding ? lineWithEnding.slice(0, -lineEnding.length) : lineWithEnding;
    const fenceRun = /^ {0,3}(`{3,}|~{3,})/.exec(line)?.[1];
    if (fence) {
      output.push(line, lineEnding);
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
    if (fenceRun) {
      fence = { character: fenceRun[0], length: fenceRun.length };
      output.push(line, lineEnding);
      continue;
    }

    const block = findNamedBlock(line);
    const content = block ? line.slice(0, block.start).trimEnd() : line;
    const processed = processInline(content, MAX_WIKI_TARGETS - targetCount);
    targetCount += processed.targetCount;
    changed ||= processed.changed;
    output.push(processed.source);
    if (block) {
      blockCount += 1;
      changed = true;
      output.push(
        `<span class="metabrowser-wiki-block" data-mb-wiki-block="${escapeAttribute(block.id)}"></span>`,
      );
    }
    output.push(lineEnding);
  }

  return Object.freeze({
    blockCount,
    changed,
    source: output.join(""),
    targetCount,
  });
}

/** @param {string} source @param {number} budget */
function processInline(source, budget) {
  let targetCount = 0;
  let changed = false;
  const output = [];
  for (let index = 0; index < source.length; ) {
    if (source[index] === "\\" && source.slice(index + 1, index + 3) === "[[") {
      output.push(source.slice(index, index + 3));
      index += 3;
      continue;
    }
    if (source[index] === "`") {
      const runLength = repeatedCharacterLength(source, index, "`");
      const closing = source.indexOf("`".repeat(runLength), index + runLength);
      const end = closing === -1 ? source.length : closing + runLength;
      output.push(source.slice(index, end));
      index = end;
      continue;
    }
    const markdownLinkEnd = findMarkdownLinkEnd(source, index);
    if (markdownLinkEnd !== -1) {
      output.push(source.slice(index, markdownLinkEnd));
      index = markdownLinkEnd;
      continue;
    }

    const embed = source[index] === "!" && source.slice(index + 1, index + 3) === "[[";
    const link = source.slice(index, index + 2) === "[[";
    if ((embed || link) && targetCount < budget) {
      const openingLength = embed ? 3 : 2;
      const closing = source.indexOf("]]", index + openingLength);
      if (closing !== -1 && closing - index - openingLength <= MAX_WIKI_TARGET_CHARACTERS) {
        const authored = source.slice(index + openingLength, closing);
        const parsed = parseOccurrence(authored, embed);
        if (parsed.target) {
          output.push(renderPlaceholder(parsed, embed));
          targetCount += 1;
          changed = true;
          index = closing + 2;
          continue;
        }
      }
    }

    output.push(source[index]);
    index += 1;
  }
  return { changed, source: output.join(""), targetCount };
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
function findNamedBlock(line) {
  const match = /\s+\^([A-Za-z0-9-]+)\s*$/.exec(line);
  if (!match || insideInlineCode(line, match.index)) {
    return null;
  }
  return Object.freeze({ id: match[1], start: match.index });
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

/** @param {string} source @param {number} index */
function findMarkdownLinkEnd(source, index) {
  const image = source[index] === "!" && source[index + 1] === "[" && source[index + 2] !== "[";
  const link = source[index] === "[" && source[index + 1] !== "[";
  if (!image && !link) {
    return -1;
  }
  const labelStart = index + (image ? 2 : 1);
  const inlineEnd = source.indexOf("](", labelStart);
  const referenceEnd = source.indexOf("][", labelStart);
  const labelEnd =
    inlineEnd === -1
      ? referenceEnd
      : referenceEnd === -1
        ? inlineEnd
        : Math.min(inlineEnd, referenceEnd);
  if (labelEnd === -1) {
    return -1;
  }
  if (labelEnd === inlineEnd) {
    const destinationEnd = source.indexOf(")", labelEnd + 2);
    return destinationEnd === -1 ? -1 : destinationEnd + 1;
  }
  if (labelEnd === referenceEnd) {
    const referenceEnd = source.indexOf("]", labelEnd + 2);
    return referenceEnd === -1 ? -1 : referenceEnd + 1;
  }
  return -1;
}

/** @param {string} source @param {number} index @param {string} character */
function repeatedCharacterLength(source, index, character) {
  let end = index;
  while (source[end] === character) {
    end += 1;
  }
  return end - index;
}

/** @param {string} value */
function escapeAttribute(value) {
  return escapeText(value).replaceAll('"', "&quot;");
}

/** @param {string} value */
function escapeText(value) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}
