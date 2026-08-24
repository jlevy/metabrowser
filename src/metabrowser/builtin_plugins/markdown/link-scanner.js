/** Bounds one document's analysis work before resolution begins. */
const MAX_SCANNED_SOURCE_CHARACTERS = 2_000_000;
/** Bounds authored targets emitted from one document. */
const MAX_SCANNED_LINKS = 4096;
/** Bounds one reference label used as an index key. */
const MAX_REFERENCE_LABEL_CHARACTERS = 1024;

/** @typedef {Readonly<{action: "navigate" | "embed", authoredTarget: string, syntax: "markdown" | "html" | "wiki"}>} ScannedLink */
/** @typedef {Readonly<{complete: boolean, diagnostics: ReadonlyArray<Readonly<{code: string}>>, links: ReadonlyArray<ScannedLink>}>} ScanResult */

/**
 * Extract standard Markdown, sanitized-HTML, and Obsidian wiki destinations
 * without treating fenced or inline code as links.
 *
 * @param {string} source
 * @returns {ScanResult}
 */
export function scanMarkdownLinks(source) {
  if (typeof source !== "string") {
    throw new TypeError("Markdown link scanning requires source text");
  }
  if (source.length > MAX_SCANNED_SOURCE_CHARACTERS) {
    return result([], false, [diagnostic("source-limit")]);
  }

  const visibleLines = sourceLinesOutsideCode(source);
  const definitions = collectReferenceDefinitions(visibleLines);
  /** @type {ScannedLink[]} */
  const links = [];
  let complete = true;
  for (const entry of visibleLines) {
    if (entry.definition || !entry.text) {
      continue;
    }
    for (const link of scanLine(entry.text, definitions)) {
      if (links.length >= MAX_SCANNED_LINKS) {
        complete = false;
        break;
      }
      links.push(Object.freeze(link));
    }
    if (!complete) {
      break;
    }
  }
  return result(links, complete, complete ? [] : [diagnostic("link-limit")]);
}

/** @param {string} source */
function sourceLinesOutsideCode(source) {
  const entries = [];
  let fence = null;
  let codeDelimiter = 0;
  for (const line of source.split(/\r\n|\n|\r/)) {
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
      entries.push({ definition: false, text: "" });
      continue;
    }
    if (fenceRun && codeDelimiter === 0) {
      fence = { character: fenceRun[0], length: fenceRun.length };
      entries.push({ definition: false, text: "" });
      continue;
    }
    const masked = maskInlineCode(line, codeDelimiter);
    codeDelimiter = masked.delimiter;
    entries.push({ definition: false, text: masked.text });
  }
  return entries;
}

/** @param {string} line @param {number} initialDelimiter */
function maskInlineCode(line, initialDelimiter) {
  const output = [...line];
  let delimiter = initialDelimiter;
  for (let index = 0; index < line.length; ) {
    if (line[index] !== "`") {
      if (delimiter) {
        output[index] = " ";
      }
      index += 1;
      continue;
    }
    const run = repeatedCharacterLength(line, index, "`");
    const closes = delimiter === run;
    const opens = delimiter === 0;
    if (delimiter || opens) {
      output.fill(" ", index, index + run);
    }
    if (closes) {
      delimiter = 0;
    } else if (opens) {
      delimiter = run;
    }
    index += run;
  }
  return { delimiter, text: output.join("") };
}

/** @param {Array<{definition: boolean, text: string}>} entries */
function collectReferenceDefinitions(entries) {
  const definitions = new Map();
  for (const entry of entries) {
    const match = /^ {0,3}\[([^\]]+)]\s*:\s*(?:<([^>]+)>|(\S+))/.exec(entry.text);
    if (!match) {
      continue;
    }
    const label = normalizeReferenceLabel(match[1]);
    const target = match[2] || match[3];
    if (label && target && !definitions.has(label)) {
      definitions.set(label, target);
    }
    entry.definition = true;
  }
  return definitions;
}

/** @param {string} line @param {Map<string, string>} definitions @returns {ScannedLink[]} */
function scanLine(line, definitions) {
  /** @type {ScannedLink[]} */
  const links = [];
  for (let index = 0; index < line.length; index += 1) {
    const embed = line[index] === "!";
    const opening = embed ? index + 1 : index;
    if (line[opening] !== "[" || isEscaped(line, opening)) {
      continue;
    }
    if (line.slice(opening, opening + 2) === "[[") {
      const closing = line.indexOf("]]", opening + 2);
      if (closing === -1) {
        break;
      }
      const authored = line
        .slice(opening + 2, closing)
        .split("|", 1)[0]
        .trim();
      if (authored) {
        links.push({
          action: embed ? "embed" : "navigate",
          authoredTarget: authored,
          syntax: "wiki",
        });
      }
      index = closing + 1;
      continue;
    }
    if (line[opening + 1] === "[") {
      continue;
    }
    const labelEnd = findUnescaped(line, "]", opening + 1);
    if (labelEnd === -1) {
      break;
    }
    const label = line.slice(opening + 1, labelEnd);
    if (line[labelEnd + 1] === "(") {
      const inline = inlineDestination(line, labelEnd + 2);
      if (inline?.target) {
        links.push({
          action: embed ? "embed" : "navigate",
          authoredTarget: inline.target,
          syntax: "markdown",
        });
      }
      index = inline?.end ?? line.length;
      continue;
    }
    const reference = referenceDestination(line, labelEnd, label, definitions);
    if (reference?.target) {
      links.push({
        action: embed ? "embed" : "navigate",
        authoredTarget: reference.target,
        syntax: "markdown",
      });
    }
    if (reference) {
      index = reference.end;
    }
  }

  const htmlPattern = /<(a|img|audio|video|source|object)\b([^>]*)>/gi;
  for (const match of line.matchAll(htmlPattern)) {
    const tag = match[1].toLowerCase();
    const attributePattern =
      tag === "a"
        ? /\bhref\s*=\s*(?:(["'])(.*?)\1|([^\s>]+))/i
        : tag === "object"
          ? /\bdata\s*=\s*(?:(["'])(.*?)\1|([^\s>]+))/i
          : /\bsrc\s*=\s*(?:(["'])(.*?)\1|([^\s>]+))/i;
    const attribute = attributePattern.exec(match[2]);
    const target = attribute?.[2] || attribute?.[3];
    if (target) {
      links.push({
        action: tag === "a" ? "navigate" : "embed",
        authoredTarget: target,
        syntax: "html",
      });
    }
  }
  return links;
}

/** @param {string} line @param {number} start */
function inlineDestination(line, start) {
  let index = start;
  while (/\s/.test(line[index] || "")) {
    index += 1;
  }
  if (line[index] === "<") {
    const end = findUnescaped(line, ">", index + 1);
    const closing = end === -1 ? -1 : findUnescaped(line, ")", end + 1);
    return end === -1 || closing === -1
      ? null
      : { end: closing, target: line.slice(index + 1, end) };
  }
  const targetStart = index;
  let depth = 0;
  for (; index < line.length; index += 1) {
    if (isEscaped(line, index)) {
      continue;
    }
    if (line[index] === "(") {
      depth += 1;
      continue;
    }
    if (line[index] === ")") {
      if (depth === 0) {
        return { end: index, target: line.slice(targetStart, index) };
      }
      depth -= 1;
      continue;
    }
    if (/\s/.test(line[index]) && depth === 0) {
      const closing = findUnescaped(line, ")", index + 1);
      return closing === -1 ? null : { end: closing, target: line.slice(targetStart, index) };
    }
  }
  return null;
}

/**
 * @param {string} line
 * @param {number} labelEnd
 * @param {string} label
 * @param {Map<string, string>} definitions
 */
function referenceDestination(line, labelEnd, label, definitions) {
  let referenceLabel = label;
  let end = labelEnd;
  if (line[labelEnd + 1] === "[") {
    const referenceEnd = findUnescaped(line, "]", labelEnd + 2);
    if (referenceEnd === -1) {
      return { end: line.length, target: null };
    }
    referenceLabel = line.slice(labelEnd + 2, referenceEnd) || label;
    end = referenceEnd;
  }
  const target = definitions.get(normalizeReferenceLabel(referenceLabel));
  return target ? { end, target } : null;
}

/** @param {string} value */
function normalizeReferenceLabel(value) {
  const normalized = value.trim().replace(/\s+/g, " ").toLowerCase();
  return normalized.length <= MAX_REFERENCE_LABEL_CHARACTERS ? normalized : "";
}

/** @param {string} source @param {string} character @param {number} start */
function findUnescaped(source, character, start) {
  for (let index = start; index < source.length; index += 1) {
    if (source[index] === character && !isEscaped(source, index)) {
      return index;
    }
  }
  return -1;
}

/** @param {string} source @param {number} index */
function isEscaped(source, index) {
  let escapes = 0;
  for (let probe = index - 1; probe >= 0 && source[probe] === "\\"; probe -= 1) {
    escapes += 1;
  }
  return escapes % 2 === 1;
}

/** @param {string} source @param {number} index @param {string} character */
function repeatedCharacterLength(source, index, character) {
  let length = 0;
  while (source[index + length] === character) {
    length += 1;
  }
  return length;
}

/** @param {string} code */
function diagnostic(code) {
  return Object.freeze({ code });
}

/** @param {ScannedLink[]} links @param {boolean} complete @param {Array<Readonly<{code: string}>>} diagnostics @returns {ScanResult} */
function result(links, complete, diagnostics) {
  return Object.freeze({
    complete,
    diagnostics: Object.freeze(diagnostics),
    links: Object.freeze(links),
  });
}
