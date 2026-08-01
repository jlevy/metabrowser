// Deterministic fuzzy matching for served-root-relative file paths.

(() => {
  const BOUNDARY_SEPARATOR = /[/\-_.\s]/u;

  /** @param {string} value */
  function isLowercaseLetter(value) {
    return value === value.toLowerCase() && value !== value.toUpperCase();
  }

  /** @param {string} value */
  function isUppercaseLetter(value) {
    return value === value.toUpperCase() && value !== value.toLowerCase();
  }

  /**
   * Normalize one original string while retaining UTF-16 offsets for highlights.
   * @param {string} original
   */
  function normalizedView(original) {
    const normalizedUnits = Array.from(original.toLowerCase());
    /** @type {string[]} */
    const units = [];
    /** @type {number[]} */
    const starts = [];
    /** @type {number[]} */
    const ends = [];
    /** @type {boolean[]} */
    const boundaries = [];
    let offset = 0;
    let normalizedOffset = 0;
    let previous = "";
    for (const character of original) {
      const normalizedCharacterLength = Array.from(character.toLowerCase()).length;
      const boundary =
        offset === 0 ||
        BOUNDARY_SEPARATOR.test(previous) ||
        (isLowercaseLetter(previous) && isUppercaseLetter(character));
      for (let index = 0; index < normalizedCharacterLength; index += 1) {
        units.push(normalizedUnits[normalizedOffset]);
        starts.push(offset);
        ends.push(offset + character.length);
        boundaries.push(index === 0 && boundary);
        normalizedOffset += 1;
      }
      offset += character.length;
      previous = character;
    }

    const slashPrefix = [0];
    for (const unit of units) {
      slashPrefix.push(slashPrefix[slashPrefix.length - 1] + (unit === "/" ? 1 : 0));
    }
    return { boundaries, ends, slashPrefix, starts, units };
  }

  /**
   * @typedef {object} Alignment
   * @property {number} boundaryHits
   * @property {number} currentRun
   * @property {number} gapChars
   * @property {number} longestRun
   * @property {number[]} positions
   * @property {number} runCount
   * @property {boolean} skippedSlash
   * @property {number} startOffset
   */

  /** @param {Alignment} left @param {Alignment} right */
  function comparePositionOrder(left, right) {
    for (let index = 0; index < left.positions.length; index += 1) {
      if (left.positions[index] !== right.positions[index]) {
        return left.positions[index] - right.positions[index];
      }
    }
    return 0;
  }

  /**
   * Compare states that end at the same candidate position with the same current run
   * and path-segment state. Future transitions affect both states identically.
   * @param {Alignment} left
   * @param {Alignment} right
   */
  function comparePartialAlignment(left, right) {
    return (
      right.boundaryHits - left.boundaryHits ||
      right.longestRun - left.longestRun ||
      left.runCount - right.runCount ||
      left.gapChars - right.gapChars ||
      left.startOffset - right.startOffset ||
      comparePositionOrder(left, right)
    );
  }

  /** @param {Alignment} left @param {Alignment} right @param {boolean} pathAware */
  function compareFinalAlignment(left, right, pathAware) {
    return (
      (pathAware ? Number(left.skippedSlash) - Number(right.skippedSlash) : 0) ||
      comparePartialAlignment(left, right)
    );
  }

  /**
   * Find the best ordered subsequence under the documented rank components.
   * Dynamic states retain current-run and skipped-segment distinctions because those
   * can affect a later comparison.
   * @param {string[]} queryUnits
   * @param {ReturnType<typeof normalizedView>} candidate
   * @param {boolean} pathAware
   * @returns {Alignment | null}
   */
  function bestSubsequence(queryUnits, candidate, pathAware) {
    if (queryUnits.length === 0 || queryUnits.length > candidate.units.length) {
      return null;
    }

    /** @type {Map<number, Map<string, Alignment>>} */
    let layer = new Map();
    for (let position = 0; position < candidate.units.length; position += 1) {
      if (candidate.units[position] !== queryUnits[0]) {
        continue;
      }
      layer.set(
        position,
        new Map([
          [
            "1|0",
            {
              boundaryHits: candidate.boundaries[position] ? 1 : 0,
              currentRun: 1,
              gapChars: 0,
              longestRun: 1,
              positions: [position],
              runCount: 1,
              skippedSlash: false,
              startOffset: candidate.starts[position],
            },
          ],
        ]),
      );
    }

    for (let queryIndex = 1; queryIndex < queryUnits.length; queryIndex += 1) {
      /** @type {Map<number, Map<string, Alignment>>} */
      const nextLayer = new Map();
      for (let position = 0; position < candidate.units.length; position += 1) {
        if (candidate.units[position] !== queryUnits[queryIndex]) {
          continue;
        }
        /** @type {Map<string, Alignment>} */
        const statesAtPosition = new Map();
        for (const [previousPosition, previousStates] of layer) {
          if (previousPosition >= position) {
            continue;
          }
          const gap = position - previousPosition - 1;
          const skippedSlashBetween =
            candidate.slashPrefix[position] - candidate.slashPrefix[previousPosition + 1] > 0;
          for (const previous of previousStates.values()) {
            const contiguous = gap === 0;
            const currentRun = contiguous ? previous.currentRun + 1 : 1;
            const skippedSlash = previous.skippedSlash || skippedSlashBetween;
            /** @type {Alignment} */
            const next = {
              boundaryHits: previous.boundaryHits + (candidate.boundaries[position] ? 1 : 0),
              currentRun,
              gapChars: previous.gapChars + gap,
              longestRun: Math.max(previous.longestRun, currentRun),
              positions: [...previous.positions, position],
              runCount: previous.runCount + (contiguous ? 0 : 1),
              skippedSlash,
              startOffset: previous.startOffset,
            };
            const stateKey = `${currentRun}|${Number(skippedSlash)}`;
            const current = statesAtPosition.get(stateKey);
            if (!current || comparePartialAlignment(next, current) < 0) {
              statesAtPosition.set(stateKey, next);
            }
          }
        }
        if (statesAtPosition.size > 0) {
          nextLayer.set(position, statesAtPosition);
        }
      }
      layer = nextLayer;
      if (layer.size === 0) {
        return null;
      }
    }

    /** @type {Alignment | null} */
    let best = null;
    for (const states of layer.values()) {
      for (const state of states.values()) {
        if (!best || compareFinalAlignment(state, best, pathAware) < 0) {
          best = state;
        }
      }
    }
    return best;
  }

  /**
   * @param {string[]} queryUnits
   * @param {ReturnType<typeof normalizedView>} candidate
   * @returns {Alignment | null}
   */
  function bestContiguous(queryUnits, candidate) {
    /** @type {Alignment | null} */
    let best = null;
    const lastStart = candidate.units.length - queryUnits.length;
    for (let start = 0; start <= lastStart; start += 1) {
      let matches = true;
      for (let queryIndex = 0; queryIndex < queryUnits.length; queryIndex += 1) {
        if (candidate.units[start + queryIndex] !== queryUnits[queryIndex]) {
          matches = false;
          break;
        }
      }
      if (!matches) {
        continue;
      }
      const positions = queryUnits.map((_, index) => start + index);
      const candidateAlignment = {
        boundaryHits: positions.reduce(
          (count, position) => count + (candidate.boundaries[position] ? 1 : 0),
          0,
        ),
        currentRun: queryUnits.length,
        gapChars: 0,
        longestRun: queryUnits.length,
        positions,
        runCount: 1,
        skippedSlash: false,
        startOffset: candidate.starts[start],
      };
      if (!best || comparePartialAlignment(candidateAlignment, best) < 0) {
        best = candidateAlignment;
      }
    }
    return best;
  }

  /** @param {string[]} left @param {string[]} right */
  function equalUnits(left, right) {
    return left.length === right.length && left.every((unit, index) => unit === right[index]);
  }

  /** @param {string[]} candidate @param {string[]} prefix */
  function startsWithUnits(candidate, prefix) {
    return (
      candidate.length >= prefix.length && prefix.every((unit, index) => candidate[index] === unit)
    );
  }

  /**
   * @param {Alignment} alignment
   * @param {ReturnType<typeof normalizedView>} candidate
   * @param {number} pathOffset
   */
  function matchRanges(alignment, candidate, pathOffset) {
    /** @type {Array<{start: number, end: number}>} */
    const ranges = [];
    for (const position of alignment.positions) {
      const start = pathOffset + candidate.starts[position];
      const end = pathOffset + candidate.ends[position];
      const previous = ranges[ranges.length - 1];
      if (previous && start <= previous.end) {
        previous.end = Math.max(previous.end, end);
      } else {
        ranges.push({ start, end });
      }
    }
    return Object.freeze(ranges.map((range) => Object.freeze(range)));
  }

  /**
   * Score one served-root-relative path, or return null when it is ineligible.
   * @param {string} query
   * @param {string} path
   */
  function matchPath(query, path) {
    if (typeof query !== "string" || typeof path !== "string") {
      return null;
    }
    const trimmedQuery = query.trim();
    if (!trimmedQuery || !path) {
      return null;
    }

    const queryUnits = Array.from(trimmedQuery.toLowerCase());
    const basenameOffset = path.lastIndexOf("/") + 1;
    const basename = path.slice(basenameOffset);
    const basenameView = normalizedView(basename);
    const queryIsPathAware = trimmedQuery.includes("/");
    let matchedValue = basename;
    let matchedView = basenameView;
    let pathOffset = basenameOffset;
    let matchClass = 3;
    /** @type {Alignment | null} */
    let alignment = null;

    if (!queryIsPathAware) {
      if (equalUnits(basenameView.units, queryUnits)) {
        alignment = bestContiguous(queryUnits, basenameView);
        matchClass = 0;
      } else if (startsWithUnits(basenameView.units, queryUnits)) {
        alignment = bestContiguous(queryUnits, basenameView);
        matchClass = 1;
      } else {
        alignment = bestContiguous(queryUnits, basenameView);
        if (alignment) {
          matchClass = 2;
        } else {
          alignment = bestSubsequence(queryUnits, basenameView, false);
          matchClass = 3;
        }
      }
    }

    if (queryIsPathAware || !alignment) {
      matchedValue = path;
      matchedView = normalizedView(path);
      pathOffset = 0;
      alignment = bestSubsequence(queryUnits, matchedView, true);
      if (!alignment) {
        return null;
      }
      matchClass = alignment.skippedSlash ? 5 : 4;
    }

    if (!alignment) {
      return null;
    }
    const rank = Object.freeze({
      matchClass,
      boundaryHits: alignment.boundaryHits,
      contiguousChars: alignment.longestRun,
      runCount: alignment.runCount,
      gapChars: alignment.gapChars,
      startOffset: alignment.startOffset,
      candidateLength: matchedValue.length,
      directoryDepth: Array.from(path).filter((character) => character === "/").length,
      normalizedPath: path.toLowerCase(),
      originalPath: path,
    });
    return Object.freeze({
      matchRanges: matchRanges(alignment, matchedView, pathOffset),
      path,
      rank,
    });
  }

  /**
   * @param {NonNullable<ReturnType<typeof matchPath>>} left
   * @param {NonNullable<ReturnType<typeof matchPath>>} right
   */
  function compareMatches(left, right) {
    const leftRank = left.rank;
    const rightRank = right.rank;
    return (
      leftRank.matchClass - rightRank.matchClass ||
      rightRank.boundaryHits - leftRank.boundaryHits ||
      rightRank.contiguousChars - leftRank.contiguousChars ||
      leftRank.runCount - rightRank.runCount ||
      leftRank.gapChars - rightRank.gapChars ||
      leftRank.startOffset - rightRank.startOffset ||
      leftRank.candidateLength - rightRank.candidateLength ||
      leftRank.directoryDepth - rightRank.directoryDepth ||
      (leftRank.normalizedPath < rightRank.normalizedPath
        ? -1
        : leftRank.normalizedPath > rightRank.normalizedPath
          ? 1
          : 0) ||
      (leftRank.originalPath < rightRank.originalPath
        ? -1
        : leftRank.originalPath > rightRank.originalPath
          ? 1
          : 0)
    );
  }

  /** @param {string} query @param {string[]} paths @param {number} [limit] */
  function rankPaths(query, paths, limit = Number.POSITIVE_INFINITY) {
    const results = paths
      .map((path) => matchPath(query, path))
      .filter((result) => result !== null)
      .sort(compareMatches);
    const boundedLimit = Number.isFinite(limit) ? Math.max(0, Math.floor(limit)) : results.length;
    return Object.freeze(results.slice(0, boundedLimit));
  }

  window.MetabrowserFileFuzzyMatch = Object.freeze({ compareMatches, matchPath, rankPaths });
})();
