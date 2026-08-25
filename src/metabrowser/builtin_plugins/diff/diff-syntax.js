// Side-specific syntax data for File Diff Format hunks.

/** @typedef {"context" | "add" | "del"} DiffLineOperation */

/**
 * @typedef {object} DiffLineRecord
 * @property {number | null} changedRun
 * @property {number | null} newNumber
 * @property {MetabrowserSyntaxTokenRun[] | null} newTokens
 * @property {boolean} noNewline
 * @property {number | null} oldNumber
 * @property {MetabrowserSyntaxTokenRun[] | null} oldTokens
 * @property {DiffLineOperation} op
 * @property {string} text
 */

/**
 * @typedef {object} DiffHunkRecord
 * @property {string | undefined} heading
 * @property {DiffLineRecord[]} lines
 * @property {number} newCount
 * @property {number | null} newInputBytes
 * @property {number[]} newLineIndices
 * @property {number} newStart
 * @property {string} newSource
 * @property {number} oldCount
 * @property {number | null} oldInputBytes
 * @property {number[]} oldLineIndices
 * @property {number} oldStart
 * @property {string} oldSource
 */

/**
 * @typedef {object} DiffFileSyntaxModel
 * @property {DiffHunkRecord[]} hunks
 * @property {number | null} inputBytes
 * @property {string} newLanguage
 * @property {string} oldLanguage
 */

/**
 * @typedef {object} DiffSyntaxApi
 * @property {(data: Record<string, unknown>) => boolean} isLargeTextPreview
 * @property {(source: string, language: string, options?: {signal?: AbortSignal, inputBytes?: number}) => Promise<MetabrowserSyntaxTokenLines | null>} highlightSyntax
 */

/** @type {TextEncoder | null} */
let syntaxTextEncoder = null;

/** @param {string} source */
function syntaxInputByteLength(source) {
  syntaxTextEncoder ??= new TextEncoder();
  return syntaxTextEncoder.encode(source).byteLength;
}

/**
 * Assign stable side numbers and source-stream membership to one validated hunk.
 * @param {Record<string, unknown>} hunk
 * @returns {DiffHunkRecord}
 */
export function buildHunkRecords(hunk) {
  let oldNumber = Number(hunk.old_start);
  let newNumber = Number(hunk.new_start);
  let changedRun = -1;
  let insideChangedRun = false;
  const rawLines = /** @type {Record<string, unknown>[]} */ (hunk.lines);
  /** @type {DiffLineRecord[]} */
  const lines = [];
  /** @type {number[]} */
  const oldLineIndices = [];
  /** @type {number[]} */
  const newLineIndices = [];

  for (const rawLine of rawLines) {
    const op = /** @type {DiffLineOperation} */ (String(rawLine.op));
    if (op === "context") {
      insideChangedRun = false;
    } else if (!insideChangedRun) {
      changedRun += 1;
      insideChangedRun = true;
    }
    const record = {
      changedRun: op === "context" ? null : changedRun,
      newNumber: op === "del" ? null : newNumber,
      newTokens: null,
      noNewline: rawLine.no_newline === true,
      oldNumber: op === "add" ? null : oldNumber,
      oldTokens: null,
      op,
      text: String(rawLine.text),
    };
    const index = lines.length;
    lines.push(record);
    if (op !== "add") {
      oldLineIndices.push(index);
      oldNumber += 1;
    }
    if (op !== "del") {
      newLineIndices.push(index);
      newNumber += 1;
    }
  }

  return {
    heading: typeof hunk.heading === "string" ? hunk.heading : undefined,
    lines,
    newCount: Number(hunk.new_count),
    newInputBytes: null,
    newLineIndices,
    newStart: Number(hunk.new_start),
    newSource: newLineIndices.map((index) => lines[index].text).join("\n"),
    oldCount: Number(hunk.old_count),
    oldInputBytes: null,
    oldLineIndices,
    oldStart: Number(hunk.old_start),
    oldSource: oldLineIndices.map((index) => lines[index].text).join("\n"),
  };
}

/**
 * Resolve one side through the host path registry.
 * @param {Record<string, unknown>} change
 * @param {"old" | "new"} sideName
 * @param {(pathOrName: string) => string} langForPath
 */
export function languageForSide(change, sideName, langForPath) {
  const side = /** @type {Record<string, unknown> | undefined} */ (change[sideName]);
  const path = typeof side?.path === "string" ? side.path : "";
  return langForPath(path);
}

/** @param {DiffHunkRecord[]} hunks */
export function syntaxInputBytes(hunks) {
  let total = 0;
  for (const hunk of hunks) {
    hunk.oldInputBytes ??= syntaxInputByteLength(hunk.oldSource);
    hunk.newInputBytes ??= syntaxInputByteLength(hunk.newSource);
    total += hunk.oldInputBytes + hunk.newInputBytes;
  }
  return total;
}

/**
 * Build the source facts that both diff projections consume.
 * Token fields remain mutable so progressive enhancement can attach its result.
 * @param {Record<string, unknown>} change
 * @param {Record<string, unknown>} patch
 * @param {(pathOrName: string) => string} langForPath
 * @returns {DiffFileSyntaxModel}
 */
export function buildFileSyntaxModel(change, patch, langForPath) {
  const rawHunks = /** @type {Record<string, unknown>[]} */ (patch.hunks);
  const hunks = rawHunks.map(buildHunkRecords);
  return {
    hunks,
    inputBytes: null,
    newLanguage: languageForSide(change, "new", langForPath),
    oldLanguage: languageForSide(change, "old", langForPath),
  };
}

/**
 * Attach one validated token stream to its semantic side.
 * @param {DiffHunkRecord} hunk
 * @param {"old" | "new"} sideName
 * @param {MetabrowserSyntaxTokenLines | null} tokenLines
 */
export function applySideTokens(hunk, sideName, tokenLines) {
  if (tokenLines === null) {
    return false;
  }
  const indices = sideName === "old" ? hunk.oldLineIndices : hunk.newLineIndices;
  const source = sideName === "old" ? hunk.oldSource : hunk.newSource;
  const sourceLines = source.split("\n");
  if (
    tokenLines.length !== indices.length ||
    tokenLines.length !== sourceLines.length ||
    tokenLines.some((runs, index) => runs.map((run) => run.text).join("") !== sourceLines[index])
  ) {
    console.warn("metabrowser diff: rejected syntax token round trip", {
      actualLines: tokenLines.length,
      expectedLines: indices.length,
      side: sideName,
    });
    return false;
  }
  for (const [tokenIndex, lineIndex] of indices.entries()) {
    const record = hunk.lines[lineIndex];
    if (sideName === "old") {
      record.oldTokens = tokenLines[tokenIndex];
    } else {
      record.newTokens = tokenLines[tokenIndex];
    }
  }
  return true;
}

/**
 * Highlight each nonempty hunk side independently after one whole-file bound decision.
 * @param {DiffFileSyntaxModel} model
 * @param {DiffSyntaxApi} api
 * @param {AbortSignal | undefined} signal
 */
export async function highlightFileSyntax(model, api, signal) {
  signal?.throwIfAborted();
  model.inputBytes ??= syntaxInputBytes(model.hunks);
  if (api.isLargeTextPreview({ size: model.inputBytes })) {
    return false;
  }
  let enhanced = false;
  for (const hunk of model.hunks) {
    if (hunk.oldLineIndices.length > 0 && model.oldLanguage) {
      signal?.throwIfAborted();
      const oldTokens = await api.highlightSyntax(hunk.oldSource, model.oldLanguage, {
        inputBytes: hunk.oldInputBytes ?? undefined,
        signal,
      });
      signal?.throwIfAborted();
      enhanced = applySideTokens(hunk, "old", oldTokens) || enhanced;
    }
    if (hunk.newLineIndices.length > 0 && model.newLanguage) {
      signal?.throwIfAborted();
      const newTokens = await api.highlightSyntax(hunk.newSource, model.newLanguage, {
        inputBytes: hunk.newInputBytes ?? undefined,
        signal,
      });
      signal?.throwIfAborted();
      enhanced = applySideTokens(hunk, "new", newTokens) || enhanced;
    }
  }
  return enhanced;
}
