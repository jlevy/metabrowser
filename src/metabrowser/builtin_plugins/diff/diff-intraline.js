/*---------------------------------------------------------------------------------------------
 * Portions adapted from Microsoft Visual Studio Code at commit
 * 77f86f3d3a05cf5d6f765705e816341c918b7dae:
 * defaultLinesDiffComputer/algorithms/{diffAlgorithm,dynamicProgrammingDiffing,myersDiffAlgorithm}.ts,
 * heuristicSequenceOptimizations.ts, and linesSliceCharSequence.ts.
 * Copyright (c) Microsoft Corporation. Licensed under the MIT License.
 * See static/vendor/licenses/vscode.txt.
 *--------------------------------------------------------------------------------------------*/

/** Weighted dynamic programming gives more readable results for small character runs. */
const DYNAMIC_PROGRAMMING_INPUT_LENGTH = 500;
/** Tiny equal islands inside an edit are less readable than one contiguous range. */
const SHORT_EQUAL_MATCH_LENGTH = 2;
/** At least this many stable non-whitespace characters establish a similar line. */
const MIN_MEANINGFUL_EQUAL_CHARACTERS = 3;
/** Similar lines retain a substantial fraction of their non-whitespace text. */
const MIN_LINE_SIMILARITY = 0.35;
/** Mostly changed words are clearer when highlighted as a complete word. */
const WORD_EXTENSION_EQUAL_FRACTION = 2 / 3;
/** Repeated-character insertions may shift only within a local readable neighborhood. */
const MAX_BOUNDARY_SHIFT = 100;

/** @typedef {{start: number, end: number}} IntralineRange */
/** @typedef {{oldIndex: number | null, newIndex: number | null}} IntralineRow */
/** @typedef {"refined" | "plain" | "timed_out" | "over_budget"} IntralineStatus */

/**
 * @typedef {object} IntralineBudget
 * @property {(() => boolean) | undefined} [isValid]
 * @property {number | undefined} [maxWork]
 * @property {((metrics: {editDistance: number | null, inputCharacters: number, work: number}) => void) | undefined} [onMetrics]
 */

/**
 * @typedef {object} ChangedRunRefinement
 * @property {IntralineRange[][]} newSpansByIndex
 * @property {IntralineRange[][]} oldSpansByIndex
 * @property {IntralineRow[]} rows
 * @property {IntralineStatus} status
 */

/** @typedef {{oldStart: number, oldEnd: number, newStart: number, newEnd: number}} SequenceDiff */
/** @typedef {{diffs: SequenceDiff[], status: "complete" | "timed_out" | "over_budget"}} DiffResult */
/** @typedef {{prev: SnakePath | null, x: number, y: number, length: number}} SnakePath */
/** @typedef {{oldRanges: IntralineRange[], newRanges: IntralineRange[], meaningful: number}} LineCandidate */
/** @typedef {{oldIndex: number, newIndex: number, candidate: LineCandidate, similarity: number}} PairCandidate */
/** @typedef {{score: number, pair: PairCandidate, previous: PairNode | null}} PairNode */

/**
 * Count deterministic algorithm work separately from the caller's time seam.
 * @param {IntralineBudget | undefined} budget
 */
function createBudgetTracker(budget) {
  let work = 0;
  let status = /** @type {"complete" | "timed_out" | "over_budget"} */ ("complete");
  return {
    /** @param {number} amount */
    consume(amount) {
      work += amount;
      if (budget?.maxWork !== undefined && work > budget.maxWork) {
        status = "over_budget";
        return false;
      }
      if (budget?.isValid !== undefined && !budget.isValid()) {
        status = "timed_out";
        return false;
      }
      return true;
    },
    get status() {
      return status;
    },
    get work() {
      return work;
    },
  };
}

/** @param {number} oldLength @param {number} newLength */
function positionalRows(oldLength, newLength) {
  return Array.from({ length: Math.max(oldLength, newLength) }, (_, index) => ({
    newIndex: index < newLength ? index : null,
    oldIndex: index < oldLength ? index : null,
  }));
}

/**
 * Return the progressive-enhancement fallback without changing text or order.
 * @param {number} oldLength
 * @param {number} newLength
 * @param {Exclude<IntralineStatus, "refined">} status
 * @returns {ChangedRunRefinement}
 */
function plainRefinement(oldLength, newLength, status) {
  return {
    newSpansByIndex: Array.from({ length: newLength }, () => []),
    oldSpansByIndex: Array.from({ length: oldLength }, () => []),
    rows: positionalRows(oldLength, newLength),
    status,
  };
}

/** @param {string} source @param {number} offset */
function boundaryScore(source, offset) {
  const previous = categoryAt(source, offset - 1);
  const next = categoryAt(source, offset);
  if (previous === "line-feed") {
    return 150;
  }
  if (previous === "carriage-return" && next === "line-feed") {
    return 0;
  }
  let score = categoryScore(previous) + categoryScore(next);
  if (previous !== next) {
    score += 10;
    if (previous === "lower" && next === "upper") {
      score += 1;
    }
  }
  return score;
}

/** @param {string} source @param {number} offset */
function categoryAt(source, offset) {
  if (offset < 0 || offset >= source.length) {
    return "end";
  }
  const character = source[offset];
  if (character === "\n") {
    return "line-feed";
  }
  if (character === "\r") {
    return "carriage-return";
  }
  if (/\s/u.test(character)) {
    return "space";
  }
  if (/[a-z]/u.test(character)) {
    return "lower";
  }
  if (/[A-Z]/u.test(character)) {
    return "upper";
  }
  if (/[0-9]/u.test(character)) {
    return "number";
  }
  if (character === "," || character === ";") {
    return "separator";
  }
  return "other";
}

/** @param {string} category */
function categoryScore(category) {
  switch (category) {
    case "separator":
      return 30;
    case "end":
    case "line-feed":
    case "carriage-return":
      return 10;
    case "space":
      return 3;
    case "other":
      return 2;
    default:
      return 0;
  }
}

/** Count stable evidence without copying a potentially patch-sized string. @param {string} text */
function meaningfulCharacterCount(text) {
  let whitespace = 0;
  for (const match of text.matchAll(/\s/gu)) {
    whitespace += match[0].length;
  }
  return text.length - whitespace;
}

/**
 * Compute changed ranges with weighted longest-common-subsequence alignment.
 * @param {string} oldSource
 * @param {string} newSource
 * @param {ReturnType<typeof createBudgetTracker>} budget
 * @returns {DiffResult}
 */
function dynamicProgrammingDiff(oldSource, newSource, budget) {
  if (oldSource.length === 0 || newSource.length === 0) {
    return {
      diffs: [{ oldStart: 0, oldEnd: oldSource.length, newStart: 0, newEnd: newSource.length }],
      status: "complete",
    };
  }
  const columns = newSource.length + 1;
  const cells = (oldSource.length + 1) * columns;
  if (!budget.consume(cells)) {
    return { diffs: [], status: budget.status };
  }
  const scores = new Float64Array(cells);
  const directions = new Uint8Array(cells);
  for (let oldIndex = 1; oldIndex <= oldSource.length; oldIndex += 1) {
    if (!budget.consume(0)) {
      return { diffs: [], status: budget.status };
    }
    for (let newIndex = 1; newIndex <= newSource.length; newIndex += 1) {
      const index = oldIndex * columns + newIndex;
      const above = scores[index - columns];
      const left = scores[index - 1];
      const diagonal = scores[index - columns - 1];
      const equal = oldSource.charCodeAt(oldIndex - 1) === newSource.charCodeAt(newIndex - 1);
      const equalScore = equal
        ? diagonal + 1 + (directions[index - columns - 1] === 3 ? 0.1 : 0)
        : -1;
      if (equalScore >= above && equalScore >= left) {
        scores[index] = equalScore;
        directions[index] = 3;
      } else if (above >= left) {
        scores[index] = above;
        directions[index] = 1;
      } else {
        scores[index] = left;
        directions[index] = 2;
      }
    }
  }

  /** @type {{old: number, new: number}[]} */
  const equals = [];
  let oldIndex = oldSource.length;
  let newIndex = newSource.length;
  while (oldIndex > 0 && newIndex > 0) {
    const direction = directions[oldIndex * columns + newIndex];
    if (direction === 3) {
      equals.push({ old: oldIndex - 1, new: newIndex - 1 });
      oldIndex -= 1;
      newIndex -= 1;
    } else if (direction === 1) {
      oldIndex -= 1;
    } else {
      newIndex -= 1;
    }
  }
  equals.reverse();
  return {
    diffs: changesFromEqualPositions(equals, oldSource.length, newSource.length),
    status: "complete",
  };
}

/**
 * Compute changed ranges with VS Code's Myers edit-distance frontier and path representation.
 * @param {string} oldSource
 * @param {string} newSource
 * @param {ReturnType<typeof createBudgetTracker>} budget
 * @returns {DiffResult}
 */
function myersDiff(oldSource, newSource, budget) {
  if (oldSource.length === 0 || newSource.length === 0) {
    return {
      diffs: [{ oldStart: 0, oldEnd: oldSource.length, newStart: 0, newEnd: newSource.length }],
      status: "complete",
    };
  }
  /** @type {Map<number, number>} */
  const furthest = new Map();
  /** @type {Map<number, SnakePath | null>} */
  const paths = new Map();
  /** @param {number} x @param {number} y */
  const snake = (x, y) => {
    while (
      x < oldSource.length &&
      y < newSource.length &&
      oldSource.charCodeAt(x) === newSource.charCodeAt(y)
    ) {
      x += 1;
      y += 1;
    }
    return x;
  };
  const initialX = snake(0, 0);
  furthest.set(0, initialX);
  paths.set(0, initialX === 0 ? null : { prev: null, x: 0, y: 0, length: initialX });

  let finalDiagonal = 0;
  let found = initialX === oldSource.length && initialX === newSource.length;
  for (let distance = 1; !found; distance += 1) {
    if (!budget.consume(distance * 2 + 1)) {
      return { diffs: [], status: budget.status };
    }
    const lower = -Math.min(distance, newSource.length + (distance % 2));
    const upper = Math.min(distance, oldSource.length + (distance % 2));
    for (let diagonal = lower; diagonal <= upper; diagonal += 2) {
      const fromTop = diagonal === upper ? -1 : (furthest.get(diagonal + 1) ?? -1);
      const fromLeft = diagonal === lower ? -1 : (furthest.get(diagonal - 1) ?? -1) + 1;
      const x = Math.min(Math.max(fromTop, fromLeft), oldSource.length);
      const y = x - diagonal;
      if (x < 0 || y < 0 || y > newSource.length) {
        continue;
      }
      const endX = snake(x, y);
      furthest.set(diagonal, endX);
      const previousPath =
        x === fromTop ? (paths.get(diagonal + 1) ?? null) : (paths.get(diagonal - 1) ?? null);
      paths.set(
        diagonal,
        endX === x ? previousPath : { prev: previousPath, x, y, length: endX - x },
      );
      if (endX === oldSource.length && endX - diagonal === newSource.length) {
        finalDiagonal = diagonal;
        found = true;
        break;
      }
    }
  }

  /** @type {SequenceDiff[]} */
  const diffs = [];
  let lastOld = oldSource.length;
  let lastNew = newSource.length;
  let path = paths.get(finalDiagonal) ?? null;
  while (true) {
    const equalEndOld = path === null ? 0 : path.x + path.length;
    const equalEndNew = path === null ? 0 : path.y + path.length;
    if (equalEndOld !== lastOld || equalEndNew !== lastNew) {
      diffs.push({
        oldStart: equalEndOld,
        oldEnd: lastOld,
        newStart: equalEndNew,
        newEnd: lastNew,
      });
    }
    if (path === null) {
      break;
    }
    lastOld = path.x;
    lastNew = path.y;
    path = path.prev;
  }
  diffs.reverse();
  return { diffs, status: "complete" };
}

/**
 * Convert monotonically matched positions to changed half-open ranges.
 * @param {{old: number, new: number}[]} equals
 * @param {number} oldLength
 * @param {number} newLength
 * @returns {SequenceDiff[]}
 */
function changesFromEqualPositions(equals, oldLength, newLength) {
  /** @type {SequenceDiff[]} */
  const diffs = [];
  let oldEnd = 0;
  let newEnd = 0;
  for (const equal of equals) {
    if (equal.old !== oldEnd || equal.new !== newEnd) {
      diffs.push({ oldStart: oldEnd, oldEnd: equal.old, newStart: newEnd, newEnd: equal.new });
    }
    oldEnd = equal.old + 1;
    newEnd = equal.new + 1;
  }
  if (oldEnd !== oldLength || newEnd !== newLength) {
    diffs.push({ oldStart: oldEnd, oldEnd: oldLength, newStart: newEnd, newEnd: newLength });
  }
  return diffs;
}

/**
 * Merge edits separated only by an unstable tiny match.
 * @param {SequenceDiff[]} diffs
 */
function removeShortMatches(diffs) {
  /** @type {SequenceDiff[]} */
  const result = [];
  for (const diff of diffs) {
    const previous = result.at(-1);
    if (
      previous !== undefined &&
      (diff.oldStart - previous.oldEnd <= SHORT_EQUAL_MATCH_LENGTH ||
        diff.newStart - previous.newEnd <= SHORT_EQUAL_MATCH_LENGTH)
    ) {
      previous.oldEnd = diff.oldEnd;
      previous.newEnd = diff.newEnd;
    } else {
      result.push({ ...diff });
    }
  }
  return result;
}

/**
 * Shift insertion/deletion edits toward stronger line, word, and separator boundaries.
 * @param {string} oldSource
 * @param {string} newSource
 * @param {SequenceDiff[]} diffs
 */
function shiftDiffBoundaries(oldSource, newSource, diffs) {
  return diffs.map((diff, index) => {
    if ((diff.oldStart !== diff.oldEnd && diff.newStart !== diff.newEnd) || diffs.length === 1) {
      return diff;
    }
    const previous = diffs[index - 1];
    const next = diffs[index + 1];
    let before = 0;
    let after = 0;
    while (
      before < MAX_BOUNDARY_SHIFT &&
      diff.oldStart - before > (previous?.oldEnd ?? 0) &&
      diff.newStart - before > (previous?.newEnd ?? 0) &&
      oldSource.charCodeAt(diff.oldStart - before - 1) ===
        oldSource.charCodeAt(diff.oldEnd - before - 1) &&
      newSource.charCodeAt(diff.newStart - before - 1) ===
        newSource.charCodeAt(diff.newEnd - before - 1)
    ) {
      before += 1;
    }
    while (
      after < MAX_BOUNDARY_SHIFT &&
      diff.oldEnd + after < (next?.oldStart ?? oldSource.length) &&
      diff.newEnd + after < (next?.newStart ?? newSource.length) &&
      oldSource.charCodeAt(diff.oldStart + after) === oldSource.charCodeAt(diff.oldEnd + after) &&
      newSource.charCodeAt(diff.newStart + after) === newSource.charCodeAt(diff.newEnd + after)
    ) {
      after += 1;
    }
    let bestDelta = 0;
    let bestScore = Number.NEGATIVE_INFINITY;
    for (let delta = -before; delta <= after; delta += 1) {
      const score =
        boundaryScore(oldSource, diff.oldStart + delta) +
        boundaryScore(newSource, diff.newStart + delta) +
        boundaryScore(newSource, diff.newEnd + delta);
      if (score > bestScore) {
        bestDelta = delta;
        bestScore = score;
      }
    }
    return {
      oldStart: diff.oldStart + bestDelta,
      oldEnd: diff.oldEnd + bestDelta,
      newStart: diff.newStart + bestDelta,
      newEnd: diff.newEnd + bestDelta,
    };
  });
}

/** @param {string[]} lines */
function lineStarts(lines) {
  /** @type {number[]} */
  const starts = [];
  let offset = 0;
  for (const line of lines) {
    starts.push(offset);
    offset += line.length + 1;
  }
  return starts;
}

/** @param {number[]} starts @param {number} offset */
function lineAtOffset(starts, offset) {
  let low = 0;
  let high = starts.length;
  while (low + 1 < high) {
    const middle = Math.floor((low + high) / 2);
    if (starts[middle] <= offset) {
      low = middle;
    } else {
      high = middle;
    }
  }
  return low;
}

/**
 * Invert changed ranges into equal mappings.
 * @param {SequenceDiff[]} diffs
 * @param {number} oldLength
 */
function equalMappings(diffs, oldLength) {
  /** @type {{oldStart: number, newStart: number, length: number}[]} */
  const mappings = [];
  let oldStart = 0;
  let newStart = 0;
  for (const diff of diffs) {
    const length = diff.oldStart - oldStart;
    if (length > 0) {
      mappings.push({ oldStart, newStart, length });
    }
    oldStart = diff.oldEnd;
    newStart = diff.newEnd;
  }
  if (oldStart < oldLength) {
    mappings.push({ oldStart, newStart, length: oldLength - oldStart });
  }
  return mappings;
}

/**
 * Collect same-line stable ranges and similarity evidence from global equal mappings.
 * @param {string[]} oldLines
 * @param {string[]} newLines
 * @param {SequenceDiff[]} diffs
 */
function collectLineCandidates(oldLines, newLines, diffs) {
  const oldSource = oldLines.join("\n");
  const oldStarts = lineStarts(oldLines);
  const newStarts = lineStarts(newLines);
  /** @type {Map<string, LineCandidate>} */
  const candidates = new Map();
  for (const mapping of equalMappings(diffs, oldSource.length)) {
    let consumed = 0;
    while (consumed < mapping.length) {
      const oldOffset = mapping.oldStart + consumed;
      const newOffset = mapping.newStart + consumed;
      const oldLine = lineAtOffset(oldStarts, oldOffset);
      const newLine = lineAtOffset(newStarts, newOffset);
      const oldLocal = oldOffset - oldStarts[oldLine];
      const newLocal = newOffset - newStarts[newLine];
      const oldRemaining = oldLines[oldLine].length - oldLocal;
      const newRemaining = newLines[newLine].length - newLocal;
      const length = Math.min(mapping.length - consumed, oldRemaining, newRemaining);
      if (length > 0) {
        const text = oldLines[oldLine].slice(oldLocal, oldLocal + length);
        const key = `${oldLine}:${newLine}`;
        const candidate = candidates.get(key) ?? { oldRanges: [], newRanges: [], meaningful: 0 };
        candidate.oldRanges.push({ start: oldLocal, end: oldLocal + length });
        candidate.newRanges.push({ start: newLocal, end: newLocal + length });
        candidate.meaningful += meaningfulCharacterCount(text);
        candidates.set(key, candidate);
        consumed += length;
        continue;
      }
      consumed += 1;
    }
  }
  return candidates;
}

/** @param {IntralineRange[]} ranges */
function mergeRanges(ranges) {
  /** @type {IntralineRange[]} */
  const merged = [];
  for (const range of [...ranges].sort((left, right) => left.start - right.start)) {
    const previous = merged.at(-1);
    if (previous !== undefined && range.start <= previous.end) {
      previous.end = Math.max(previous.end, range.end);
    } else {
      merged.push({ ...range });
    }
  }
  return merged;
}

/** @param {number} length @param {IntralineRange[]} stable */
function complementRanges(length, stable) {
  /** @type {IntralineRange[]} */
  const changed = [];
  let offset = 0;
  for (const range of mergeRanges(stable)) {
    if (offset < range.start) {
      changed.push({ start: offset, end: range.start });
    }
    offset = Math.max(offset, range.end);
  }
  if (offset < length) {
    changed.push({ start: offset, end: length });
  }
  return changed;
}

/** @param {string} text @param {IntralineRange} changed */
function containingWord(text, changed) {
  const word = /[A-Za-z0-9]+/gu;
  for (const match of text.matchAll(word)) {
    const start = match.index;
    const end = start + match[0].length;
    if (changed.start < end && start < changed.end) {
      return { start, end };
    }
  }
  return null;
}

/**
 * Extend mostly changed word fragments while preserving readable small suffix edits.
 * @param {string} oldText
 * @param {string} newText
 * @param {IntralineRange[]} oldSpans
 * @param {IntralineRange[]} newSpans
 */
function extendMostlyChangedWords(oldText, newText, oldSpans, newSpans) {
  if (oldSpans.length !== 1 || newSpans.length !== 1) {
    return { oldSpans, newSpans };
  }
  const oldWord = containingWord(oldText, oldSpans[0]);
  const newWord = containingWord(newText, newSpans[0]);
  if (oldWord === null || newWord === null) {
    return { oldSpans, newSpans };
  }
  const total = oldWord.end - oldWord.start + newWord.end - newWord.start;
  const changed =
    Math.min(oldSpans[0].end, oldWord.end) -
    Math.max(oldSpans[0].start, oldWord.start) +
    Math.min(newSpans[0].end, newWord.end) -
    Math.max(newSpans[0].start, newWord.start);
  if (total - changed < total * WORD_EXTENSION_EQUAL_FRACTION) {
    return { oldSpans: [oldWord], newSpans: [newWord] };
  }
  return { oldSpans, newSpans };
}

/** @param {string} text @param {IntralineRange} range */
function normalizeSurrogateRange(text, range) {
  let { start, end } = range;
  if (start > 0 && /[\uDC00-\uDFFF]/u.test(text[start])) {
    start -= 1;
  }
  if (end < text.length && /[\uDC00-\uDFFF]/u.test(text[end])) {
    end += 1;
  }
  return { start, end };
}

/**
 * Select one-to-one monotonic line pairs from already monotonic character mappings.
 * @param {string[]} oldLines
 * @param {string[]} newLines
 * @param {Map<string, LineCandidate>} candidates
 */
function selectLinePairs(oldLines, newLines, candidates) {
  /** @type {PairCandidate[]} */
  const entries = [...candidates.entries()]
    .map(([key, candidate]) => {
      const [oldIndex, newIndex] = key.split(":").map(Number);
      const maximumMeaningful = Math.max(
        meaningfulCharacterCount(oldLines[oldIndex]),
        meaningfulCharacterCount(newLines[newIndex]),
      );
      return {
        oldIndex,
        newIndex,
        candidate,
        similarity: candidate.meaningful / maximumMeaningful,
      };
    })
    .filter(
      ({ candidate, similarity }) =>
        candidate.meaningful >= MIN_MEANINGFUL_EQUAL_CHARACTERS &&
        similarity >= MIN_LINE_SIMILARITY,
    )
    .sort(
      (left, right) =>
        left.oldIndex - right.oldIndex ||
        left.newIndex - right.newIndex ||
        right.candidate.meaningful - left.candidate.meaningful,
    );
  /** @type {(PairNode | null)[]} */
  const bestByNewPrefix = Array.from({ length: newLines.length + 1 }, () => null);
  /** @param {number} exclusiveNewIndex */
  const query = (exclusiveNewIndex) => {
    /** @type {PairNode | null} */
    let best = null;
    for (let index = exclusiveNewIndex; index > 0; index -= index & -index) {
      const candidate = bestByNewPrefix[index];
      if (candidate !== null && (best === null || candidate.score > best.score)) {
        best = candidate;
      }
    }
    return best;
  };
  /** @param {number} newIndex @param {PairNode} node */
  const update = (newIndex, node) => {
    for (let index = newIndex + 1; index < bestByNewPrefix.length; index += index & -index) {
      const current = bestByNewPrefix[index];
      if (current === null || node.score > current.score) {
        bestByNewPrefix[index] = node;
      }
    }
  };
  /** @type {PairNode | null} */
  let best = null;
  for (let start = 0; start < entries.length; ) {
    let end = start + 1;
    while (end < entries.length && entries[end].oldIndex === entries[start].oldIndex) {
      end += 1;
    }
    /** @type {PairNode[]} */
    const group = [];
    for (const pair of entries.slice(start, end)) {
      const previous = query(pair.newIndex);
      const node = {
        pair,
        previous,
        score: (previous?.score ?? 0) + pair.candidate.meaningful + pair.similarity,
      };
      group.push(node);
      if (best === null || node.score > best.score) {
        best = node;
      }
    }
    for (const node of group) {
      update(node.pair.newIndex, node);
    }
    start = end;
  }
  /** @type {PairCandidate[]} */
  const selected = [];
  while (best !== null) {
    selected.push(best.pair);
    best = best.previous;
  }
  selected.reverse();
  return selected;
}

/**
 * Produce split rows and per-line changed ranges for one changed run.
 * @param {string[]} oldLines
 * @param {string[]} newLines
 * @param {IntralineBudget} [budget]
 * @returns {ChangedRunRefinement}
 */
export function refineChangedRun(oldLines, newLines, budget = {}) {
  if (oldLines.length === 0 || newLines.length === 0) {
    return plainRefinement(oldLines.length, newLines.length, "plain");
  }
  const tracker = createBudgetTracker(budget);
  if (!tracker.consume(1)) {
    return plainRefinement(
      oldLines.length,
      newLines.length,
      tracker.status === "timed_out" ? "timed_out" : "over_budget",
    );
  }
  const oldSource = oldLines.join("\n");
  const newSource = newLines.join("\n");
  const diffResult =
    oldSource.length + newSource.length < DYNAMIC_PROGRAMMING_INPUT_LENGTH
      ? dynamicProgrammingDiff(oldSource, newSource, tracker)
      : myersDiff(oldSource, newSource, tracker);
  budget.onMetrics?.({
    editDistance:
      diffResult.status === "complete"
        ? diffResult.diffs.reduce(
            (total, diff) => total + diff.oldEnd - diff.oldStart + diff.newEnd - diff.newStart,
            0,
          )
        : null,
    inputCharacters: oldSource.length + newSource.length,
    work: tracker.work,
  });
  if (diffResult.status !== "complete") {
    return plainRefinement(
      oldLines.length,
      newLines.length,
      diffResult.status === "timed_out" ? "timed_out" : "over_budget",
    );
  }
  const diffs = removeShortMatches(shiftDiffBoundaries(oldSource, newSource, diffResult.diffs));
  if (diffs.length === 0) {
    return plainRefinement(oldLines.length, newLines.length, "plain");
  }
  const candidates = collectLineCandidates(oldLines, newLines, diffs);
  const pairs = selectLinePairs(oldLines, newLines, candidates);
  if (pairs.length === 0) {
    return plainRefinement(oldLines.length, newLines.length, "plain");
  }

  const oldSpansByIndex = Array.from(
    { length: oldLines.length },
    () => /** @type {IntralineRange[]} */ ([]),
  );
  const newSpansByIndex = Array.from(
    { length: newLines.length },
    () => /** @type {IntralineRange[]} */ ([]),
  );
  /** @type {IntralineRow[]} */
  const rows = [];
  let nextOld = 0;
  let nextNew = 0;
  let refinedPairs = 0;
  for (const pair of pairs) {
    while (nextOld < pair.oldIndex || nextNew < pair.newIndex) {
      rows.push({
        oldIndex: nextOld < pair.oldIndex ? nextOld++ : null,
        newIndex: nextNew < pair.newIndex ? nextNew++ : null,
      });
    }
    const oldChanged = complementRanges(oldLines[pair.oldIndex].length, pair.candidate.oldRanges);
    const newChanged = complementRanges(newLines[pair.newIndex].length, pair.candidate.newRanges);
    const extended = extendMostlyChangedWords(
      oldLines[pair.oldIndex],
      newLines[pair.newIndex],
      oldChanged,
      newChanged,
    );
    const oldNormalized = mergeRanges(
      extended.oldSpans.map((range) => normalizeSurrogateRange(oldLines[pair.oldIndex], range)),
    );
    const newNormalized = mergeRanges(
      extended.newSpans.map((range) => normalizeSurrogateRange(newLines[pair.newIndex], range)),
    );
    const coversOld =
      oldLines[pair.oldIndex].length > 0 &&
      oldNormalized.length === 1 &&
      oldNormalized[0].start === 0 &&
      oldNormalized[0].end === oldLines[pair.oldIndex].length;
    const coversNew =
      newLines[pair.newIndex].length > 0 &&
      newNormalized.length === 1 &&
      newNormalized[0].start === 0 &&
      newNormalized[0].end === newLines[pair.newIndex].length;
    if (!coversOld && !coversNew && (oldNormalized.length > 0 || newNormalized.length > 0)) {
      oldSpansByIndex[pair.oldIndex] = oldNormalized;
      newSpansByIndex[pair.newIndex] = newNormalized;
      refinedPairs += 1;
    }
    rows.push({ oldIndex: pair.oldIndex, newIndex: pair.newIndex });
    nextOld = pair.oldIndex + 1;
    nextNew = pair.newIndex + 1;
  }
  while (nextOld < oldLines.length || nextNew < newLines.length) {
    rows.push({
      oldIndex: nextOld < oldLines.length ? nextOld++ : null,
      newIndex: nextNew < newLines.length ? nextNew++ : null,
    });
  }
  if (refinedPairs === 0) {
    return plainRefinement(oldLines.length, newLines.length, "plain");
  }
  return { newSpansByIndex, oldSpansByIndex, rows, status: "refined" };
}
