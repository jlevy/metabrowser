// Side-specific syntax enrichment for the shared diff render model.

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

/** @param {import("./diff-render-model.js").DiffHunkRecord[]} hunks */
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
 * Attach one validated token stream to its semantic side.
 * @param {import("./diff-render-model.js").DiffHunkRecord} hunk
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
 * @param {import("./diff-render-model.js").DiffFileRenderModel} model
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
