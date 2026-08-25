// Semantic source facts shared by every diff projection and enrichment pass.

import { refineChangedRun } from "./diff-intraline.js";
import { languageForSide } from "./diff-syntax.js";

/** @typedef {"context" | "add" | "del"} DiffLineOperation */
/** @typedef {import("./diff-intraline.js").IntralineRange} IntralineRange */
/** @typedef {import("./diff-intraline.js").IntralineStatus} IntralineStatus */
/** @typedef {import("./diff-intraline.js").IntralineBudget} IntralineBudget */

/**
 * @typedef {object} DiffSplitRow
 * @property {number | null} changedRun
 * @property {DiffLineRecord | null} new
 * @property {DiffLineRecord | null} old
 * @property {boolean} refined
 */

/**
 * @typedef {object} DiffLineRecord
 * @property {number | null} changedRun
 * @property {number | null} newNumber
 * @property {IntralineRange[]} newIntralineRanges
 * @property {MetabrowserSyntaxTokenRun[] | null} newTokens
 * @property {boolean} intralineRefined
 * @property {boolean} noNewline
 * @property {number | null} oldNumber
 * @property {IntralineRange[]} oldIntralineRanges
 * @property {MetabrowserSyntaxTokenRun[] | null} oldTokens
 * @property {DiffLineOperation} op
 * @property {string} text
 */

/**
 * @typedef {object} DiffHunkRecord
 * @property {string | undefined} heading
 * @property {Map<number, DiffSplitRow[]>} changedRunRows
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
 * @property {boolean} refinementComplete
 * @property {Map<number, IntralineStatus>} refinementStatusByRun
 */

/**
 * @typedef {object} DiffFileRenderModel
 * @property {DiffHunkRecord[]} hunks
 * @property {number | null} inputBytes
 * @property {string} newLanguage
 * @property {string} oldLanguage
 */

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
      intralineRefined: false,
      newIntralineRanges: [],
      newNumber: op === "del" ? null : newNumber,
      newTokens: null,
      noNewline: rawLine.no_newline === true,
      oldIntralineRanges: [],
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
    changedRunRows: new Map(),
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
    refinementComplete: false,
    refinementStatusByRun: new Map(),
  };
}

/**
 * Positional fallback rows retain both source streams without claiming similarity.
 * @param {number} changedRun
 * @param {DiffLineRecord[]} oldLines
 * @param {DiffLineRecord[]} newLines
 */
function positionalChangedRunRows(changedRun, oldLines, newLines) {
  return Array.from({ length: Math.max(oldLines.length, newLines.length) }, (_, index) => ({
    changedRun,
    new: newLines[index] ?? null,
    old: oldLines[index] ?? null,
    refined: false,
  }));
}

/**
 * Cache monotonic split rows and side-specific inner ranges for every changed run.
 * @param {DiffHunkRecord} hunk
 * @param {IntralineBudget} budget
 * @param {AbortSignal | undefined} signal
 */
export function refineHunkChangedRuns(hunk, budget, signal) {
  if (hunk.refinementComplete) {
    return false;
  }
  let enhanced = false;
  for (let index = 0; index < hunk.lines.length; ) {
    signal?.throwIfAborted();
    const line = hunk.lines[index];
    if (line.op === "context") {
      index += 1;
      continue;
    }
    const changedRun = line.changedRun;
    if (changedRun === null) {
      throw new Error("changed diff line is missing its run identity");
    }
    let end = index + 1;
    while (end < hunk.lines.length && hunk.lines[end].changedRun === changedRun) {
      end += 1;
    }
    const run = hunk.lines.slice(index, end);
    const oldLines = run.filter((record) => record.op === "del");
    const newLines = run.filter((record) => record.op === "add");
    let result;
    try {
      result = refineChangedRun(
        oldLines.map((record) => record.text),
        newLines.map((record) => record.text),
        budget,
      );
    } catch (error) {
      console.warn("metabrowser diff: intraline refinement failed", { changedRun, error });
      hunk.changedRunRows.set(changedRun, positionalChangedRunRows(changedRun, oldLines, newLines));
      hunk.refinementStatusByRun.set(changedRun, "plain");
      index = end;
      continue;
    }
    hunk.refinementStatusByRun.set(changedRun, result.status);
    const rows = result.rows.map((row) => {
      const oldLine = row.oldIndex === null ? null : oldLines[row.oldIndex];
      const newLine = row.newIndex === null ? null : newLines[row.newIndex];
      const oldRanges = row.oldIndex === null ? [] : result.oldSpansByIndex[row.oldIndex];
      const newRanges = row.newIndex === null ? [] : result.newSpansByIndex[row.newIndex];
      const refined = oldRanges.length > 0 || newRanges.length > 0;
      if (oldLine !== null) {
        oldLine.oldIntralineRanges = oldRanges;
        oldLine.intralineRefined = refined;
      }
      if (newLine !== null) {
        newLine.newIntralineRanges = newRanges;
        newLine.intralineRefined = refined;
      }
      enhanced = refined || enhanced;
      return { changedRun, new: newLine, old: oldLine, refined };
    });
    hunk.changedRunRows.set(changedRun, rows);
    index = end;
  }
  hunk.refinementComplete = true;
  return enhanced;
}

/**
 * Refine one file synchronously after the view queue has yielded to first paint.
 * @param {DiffFileRenderModel} model
 * @param {IntralineBudget} budget
 * @param {AbortSignal | undefined} signal
 */
export function refineFileChangedRuns(model, budget, signal) {
  let enhanced = false;
  for (const hunk of model.hunks) {
    signal?.throwIfAborted();
    enhanced = refineHunkChangedRuns(hunk, budget, signal) || enhanced;
  }
  return enhanced;
}

/**
 * Build the cached source facts consumed by every diff projection.
 * Token fields remain mutable so progressive syntax can attach its result.
 * @param {Record<string, unknown>} change
 * @param {Record<string, unknown>} patch
 * @param {(pathOrName: string) => string} langForPath
 * @returns {DiffFileRenderModel}
 */
export function buildFileRenderModel(change, patch, langForPath) {
  const rawHunks = /** @type {Record<string, unknown>[]} */ (patch.hunks);
  return {
    hunks: rawHunks.map(buildHunkRecords),
    inputBytes: null,
    newLanguage: languageForSide(change, "new", langForPath),
    oldLanguage: languageForSide(change, "old", langForPath),
  };
}
