// Deterministic, completion-aware Obsidian wiki-link resolution.

const MAX_AUTHORED_TARGET_LENGTH = 16_384;
// Percent identity canonicalization can expand every authored code unit from `%`
// to `%25`, and extension inference can append `.md`. Basename map keys longer
// than this cannot be named by a supported authored target, so they are skipped
// without imposing any ceiling on provider-admitted catalog identities.
const MAX_NORMALIZED_TARGET_LENGTH = MAX_AUTHORED_TARGET_LENGTH * 3 + 3;
const MAX_PARENT_SEGMENTS = Math.floor(MAX_AUTHORED_TARGET_LENGTH / 3) + 1;
const MAX_LOOKUP_FILES = 500_000;
const MAX_LOOKUP_CANDIDATES = 4096;
const MAX_RETURNED_CANDIDATES = 20;
const WIKI_RESOLUTION_IDENTITY = Symbol.for("metabrowser.wiki-resolution-identity");
const IMAGE_EXTENSIONS = new Set([
  ".avif",
  ".bmp",
  ".gif",
  ".ico",
  ".jpeg",
  ".jpg",
  ".png",
  ".svg",
  ".webp",
]);
const AUDIO_EXTENSIONS = new Set([".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"]);
const VIDEO_EXTENSIONS = new Set([".m4v", ".mov", ".mp4", ".ogv", ".webm"]);

/**
 * @typedef {object} WikiIntent
 * @property {string} sourcePath
 * @property {string} authoredTarget
 * @property {"navigate" | "embed"} action
 * @property {string=} label
 */

/**
 * @typedef {Readonly<{status: "internal", path: string, fragment?: string,
 *   mediaKind?: "markdown" | "image" | "audio" | "video" | "resource"}> |
 *   Readonly<{status: "pending" | "missing" | "unsafe" | "unsupported", reason: string}> |
 *   Readonly<{status: "ambiguous", reason: string, candidateCount: number,
 *   candidates: readonly string[]}>} WikiResolution
 */

/**
 * @typedef {Readonly<{done: boolean, pathVisits: number,
 *   result: WikiResolution | null}>} WikiResolutionStep
 */

/**
 * @typedef {Readonly<{action: "navigate" | "embed", fragment?: string,
 *   exactPath: string, miss: "fallback" | "not-found",
 *   lookup?: string, lookupKind?: "basename" | "suffix",
 *   mediaKind?: "markdown" | "image" | "audio" | "video" | "resource",
 *   resolutionIdentity: object}>} WikiLookupPlan
 */

/** @typedef {Readonly<{candidateCount: number, candidates: readonly string[], overflow: boolean}>} CandidateSummary */
/** @typedef {string | string[]} BasenameBucket */
/** @typedef {Readonly<{completePrefix: boolean, reverseSlashes: readonly number[], sourcePath: string}>} PreparedSourcePath */
/**
 * @typedef {object} SuffixQueryState
 * @property {BasenameBucket | undefined} bucket
 * @property {number} candidateCount
 * @property {string[]} candidates
 * @property {number} cursor
 * @property {boolean} done
 * @property {string} leaf
 * @property {SuffixQueryState | null} leafQuery
 * @property {string} lookup
 * @property {number} lookupDirectoryEnd
 * @property {{path: string, pathIndex: number, lookupIndex: number, phase: string} | null} match
 * @property {string} mode
 * @property {SegmentNode | null} node
 * @property {boolean} overflow
 * @property {string} phase
 * @property {number} scanIndex
 * @property {string} segment
 * @property {number} segmentEnd
 * @property {number} segmentStart
 * @property {CandidateSummary | null} summary
 */

/**
 * Resolve a parsed wiki target against one immutable known-file snapshot.
 *
 * Exact paths are usable before the inventory finishes. Basename and suffix fallback
 * remain pending until completeness proves that a currently unique match is truly
 * unique. A snapshot truncated at the inventory file cap is final but cannot prove
 * uniqueness or absence, so those results settle as `catalog-truncated`; several
 * indexed fallback candidates still settle as ambiguous.
 *
 * @param {unknown} intent
 * @param {unknown} snapshot
 */
export function resolveWikiTarget(intent, snapshot) {
  const context = createWikiResolutionContext(snapshot);
  const application = context.begin(intent);
  try {
    while (true) {
      const step = application.step(MAX_LOOKUP_FILES);
      if (step.done && step.result) {
        return step.result;
      }
    }
  } finally {
    context.dispose();
  }
}

/**
 * Cooperatively find the provider-admitted source identity's reachable parent
 * boundaries. Trusted means core already validated canonical shape and Unicode;
 * this phase still charges every inspected UTF-16 code unit. Scanning backwards
 * stops after the most parent traversals any supported authored target can name.
 *
 * @param {string} sourcePath
 */
export function createTrustedWikiSourcePathContext(sourcePath) {
  if (typeof sourcePath !== "string" || !sourcePath) {
    throw new TypeError("trusted wiki source path must be a string");
  }
  let retainedSourcePath = sourcePath;
  let cursor = sourcePath.length - 1;
  /** @type {number[]} */
  let reverseSlashes = [];
  /** @type {PreparedSourcePath | null} */
  let result = null;
  let disposed = false;

  return Object.freeze({
    dispose() {
      disposed = true;
      retainedSourcePath = "";
      reverseSlashes = [];
      result = null;
    },
    /** @param {number} maxPathVisits */
    step(maxPathVisits) {
      const limit = positiveInteger(maxPathVisits, "trusted wiki source preparation");
      if (disposed) {
        return Object.freeze({ done: true, pathVisits: 0, result: null });
      }
      if (result) {
        return Object.freeze({ done: true, pathVisits: 0, result });
      }
      let pathVisits = 0;
      while (cursor >= 0 && reverseSlashes.length < MAX_PARENT_SEGMENTS && pathVisits < limit) {
        if (retainedSourcePath.charCodeAt(cursor) === 47) {
          reverseSlashes.push(cursor);
        }
        cursor -= 1;
        pathVisits += 1;
      }
      if (cursor >= 0 && reverseSlashes.length < MAX_PARENT_SEGMENTS) {
        return Object.freeze({ done: false, pathVisits, result: null });
      }
      result = Object.freeze({
        completePrefix: cursor < 0,
        reverseSlashes: Object.freeze([...reverseSlashes]),
        sourcePath: retainedSourcePath,
      });
      return Object.freeze({ done: true, pathVisits, result });
    },
  });
}

/** @param {PreparedSourcePath} prepared */
function completedSourcePathContext(prepared) {
  return Object.freeze({
    dispose() {},
    step() {
      return Object.freeze({ done: true, pathVisits: 0, result: prepared });
    },
  });
}

/**
 * Create snapshot-scoped resolver state. Consumers resolving more than one target
 * should share this context: exact membership is memoized and the basename index is
 * built once, cooperatively, then published only after its final catalog entry.
 *
 * The context deliberately trusts the core catalog's canonical, immutable,
 * code-unit-sorted projection. Length and normalization policy applies to authored
 * targets, not to already-admitted catalog identities.
 *
 * @param {unknown} snapshot
 */
export function createWikiResolutionContext(snapshot) {
  /** @type {{complete: boolean, files: ReadonlyArray<unknown>, truncated: boolean} | null} */
  let validatedCatalog = validateSnapshot(snapshot);
  const catalogComplete = validatedCatalog.complete;
  const catalogTruncated = validatedCatalog.truncated;
  /** @type {ReadonlyArray<unknown>} */
  let catalogFiles = validatedCatalog.files;
  validatedCatalog = null;
  snapshot = null;
  /** @type {Map<string, boolean> | null} */
  let membership = new Map();
  /** @type {Map<string, Readonly<{step: (maxPathVisits: number) => Readonly<{done: boolean, found: boolean, pathVisits: number}>}>> | null} */
  let membershipApplications = new Map();
  /** @type {WeakMap<object, Map<string, boolean>> | null} */
  let sourceMembership = new WeakMap();
  /** @type {WeakMap<object, Map<string, Readonly<{step: (maxPathVisits: number) => Readonly<{done: boolean, found: boolean, pathVisits: number}>}>>> | null} */
  let sourceMembershipApplications = new WeakMap();
  /** @type {Map<string, BasenameBucket> | null} */
  let basenameIndex = null;
  /** @type {Map<string, BasenameBucket> | null} */
  let stagedBasenameIndex = null;
  let indexCursor = 0;
  /** @type {Readonly<{basename: string, path: string}> | null} */
  let indexFile = null;
  let indexBasenameCursor = 0;
  /** @type {Map<string, CandidateSummary> | null} */
  let basenameSummaries = new Map();
  /** @type {Map<string, ReturnType<typeof suffixQueryState>> | null} */
  let suffixQueries = new Map();
  /** @type {Map<string, CandidateSummary> | null} */
  let suffixSummaries = new Map();
  /** @type {Map<string, Set<string>> | null} */
  let qualifiedLookups = new Map();
  /** @type {Map<string, ReturnType<typeof segmentIndexState>> | null} */
  let segmentIndexes = new Map();
  let disposed = false;

  /** @param {unknown} intent */
  function begin(intent) {
    const value = validateIntentShape(intent);
    return beginPrepared(value, completedSourcePathContext(prepareSourcePath(value.sourcePath)));
  }

  /**
   * Resolve an intent whose source identity came from the core catalog. Core owns
   * canonical validation at this boundary, so reconciliation does not rescan one
   * arbitrarily long provider string for every renderer or graph phase.
   *
   * @param {unknown} intent
   * @param {ReturnType<typeof createTrustedWikiSourcePathContext>=} sourceContext
   */
  function beginTrusted(intent, sourceContext) {
    const value = validateIntentShape(intent);
    // A supplied context is an opaque capability owned by the document scope.
    // Comparing it back to a primitive string can itself scan an unbounded
    // provider identity. The context's prepared source is authoritative for all
    // source-relative and fragment-only results.
    return beginPrepared(
      value,
      sourceContext || createTrustedWikiSourcePathContext(value.sourcePath),
    );
  }

  /** @param {Readonly<WikiIntent>} value @param {ReturnType<typeof createTrustedWikiSourcePathContext>} sourceContext */
  function beginPrepared(value, sourceContext) {
    const exactResolutionIdentity = Object.freeze({
      authoredTarget: value.authoredTarget,
      kind: "exact",
      sourceContext,
    });
    /** @type {WikiResolution | WikiLookupPlan | null} */
    let prepared = null;
    /** @type {PreparedSourcePath | null} */
    let preparedSource = null;
    /** @type {ReturnType<typeof beginMembership> | null} */
    let exactLookup = null;
    /** @type {WikiResolution | null} */
    let terminal = null;

    return Object.freeze({
      /** @param {number} maxPathVisits @returns {WikiResolutionStep} */
      step(maxPathVisits) {
        const limit = positiveInteger(maxPathVisits, "wiki resolution");
        if (terminal) {
          return resolutionStep(true, 0, terminal);
        }
        if (disposed) {
          return resolutionStep(true, 0, unsupported("resolver-disposed"));
        }
        let pathVisits = 0;
        if (!preparedSource) {
          const sourceStep = sourceContext.step(limit);
          pathVisits += sourceStep.pathVisits;
          if (!sourceStep.done || !sourceStep.result) {
            return resolutionStep(false, pathVisits, null);
          }
          preparedSource = sourceStep.result;
          if (pathVisits >= limit) {
            return resolutionStep(false, pathVisits, null);
          }
        }
        prepared ||= prepareWikiTarget(
          value,
          {
            complete: catalogComplete,
            files: catalogFiles,
          },
          preparedSource,
          exactResolutionIdentity,
        );
        if (!("exactPath" in prepared)) {
          terminal = prepared;
          return resolutionStep(true, pathVisits, terminal);
        }

        exactLookup ||= beginMembership(prepared.exactPath, sourceContext, value.authoredTarget);
        const exactStep = exactLookup.step(limit - pathVisits);
        pathVisits += exactStep.pathVisits;
        if (!exactStep.done) {
          return resolutionStep(false, pathVisits, null);
        }
        if (exactStep.found) {
          terminal = internalResult(
            prepared.exactPath,
            prepared.action,
            prepared.fragment,
            prepared.mediaKind,
            prepared.resolutionIdentity,
          );
          return resolutionStep(true, pathVisits, terminal);
        }
        if (!catalogComplete && !catalogTruncated) {
          terminal = pending("catalog-incomplete");
          return resolutionStep(true, pathVisits, terminal);
        }
        if (prepared.miss === "not-found") {
          // A capped index may not hold the exact file, so it cannot report a miss.
          terminal = catalogTruncated ? unsupported("catalog-truncated") : missing("not-found");
          return resolutionStep(true, pathVisits, terminal);
        }
        if (pathVisits >= limit) {
          return resolutionStep(false, pathVisits, null);
        }

        const fallbackStep = stepFallback(prepared, limit - pathVisits);
        pathVisits += fallbackStep.pathVisits;
        if (!fallbackStep.done || !fallbackStep.summary) {
          return resolutionStep(false, pathVisits, null);
        }
        const summary = fallbackStep.summary;
        // Files past a cap can only add fallback candidates. Several indexed
        // candidates therefore already prove ambiguity, but none or one proves
        // neither absence nor uniqueness.
        terminal =
          catalogTruncated && !summary.overflow && summary.candidateCount < 2
            ? unsupported("catalog-truncated")
            : resolutionFromSummary(
                summary,
                prepared.action,
                prepared.fragment,
                prepared.mediaKind,
              );
        return resolutionStep(true, pathVisits, terminal);
      },
    });
  }

  /**
   * Memoize bounded exact identities directly. A source-relative result can carry
   * an arbitrarily long provider prefix, so its memo is instead namespaced by the
   * opaque source context and keyed by the bounded authored target.
   *
   * @param {string} target
   * @param {object} sourceContext
   * @param {string} authoredTarget
   */
  function beginMembership(target, sourceContext, authoredTarget) {
    const directKey = target.length <= MAX_NORMALIZED_TARGET_LENGTH;
    const key = directKey ? target : authoredTarget;
    let terminalCache = membership;
    let applicationCache = membershipApplications;
    if (!directKey) {
      terminalCache = sourceMembership?.get(sourceContext) || null;
      if (!terminalCache && sourceMembership) {
        terminalCache = new Map();
        sourceMembership.set(sourceContext, terminalCache);
      }
      applicationCache = sourceMembershipApplications?.get(sourceContext) || null;
      if (!applicationCache && sourceMembershipApplications) {
        applicationCache = new Map();
        sourceMembershipApplications.set(sourceContext, applicationCache);
      }
    }
    const inFlight = applicationCache?.get(key);
    if (inFlight) {
      return inFlight;
    }
    let low = 0;
    let high = catalogFiles.length;
    let checkIndex = -1;
    let terminal = terminalCache?.get(key);
    /** @type {{candidate: string, index: number, leftIndex: number, result: number | null} | null} */
    let comparison = null;

    const application = Object.freeze({
      /** @param {number} maxPathVisits */
      step(maxPathVisits) {
        const limit = positiveInteger(maxPathVisits, "wiki membership");
        if (terminal !== undefined) {
          return Object.freeze({ done: true, found: terminal, pathVisits: 0 });
        }
        let pathVisits = 0;
        while (low < high && pathVisits < limit) {
          if (!comparison) {
            const middle = low + Math.floor((high - low) / 2);
            comparison = {
              candidate: catalogPathAt(catalogFiles, middle),
              index: middle,
              leftIndex: 0,
              result: null,
            };
            pathVisits += 1;
            if (pathVisits >= limit) {
              break;
            }
          }
          pathVisits += stepCatalogComparison(comparison, target, limit - pathVisits);
          if (comparison.result === null) {
            break;
          }
          if (comparison.result < 0) {
            low = comparison.index + 1;
          } else {
            high = comparison.index;
          }
          comparison = null;
        }
        if (low < high) {
          return Object.freeze({ done: false, found: false, pathVisits });
        }
        if (checkIndex === -1) {
          checkIndex = low;
        }
        if (checkIndex < catalogFiles.length) {
          if (!comparison) {
            if (pathVisits >= limit) {
              return Object.freeze({ done: false, found: false, pathVisits });
            }
            comparison = {
              candidate: catalogPathAt(catalogFiles, checkIndex),
              index: checkIndex,
              leftIndex: 0,
              result: null,
            };
            pathVisits += 1;
          }
          if (pathVisits < limit) {
            pathVisits += stepCatalogComparison(comparison, target, limit - pathVisits);
          }
          if (comparison.result === null) {
            return Object.freeze({ done: false, found: false, pathVisits });
          }
          terminal = comparison.result === 0;
          comparison = null;
        } else {
          terminal = false;
        }
        terminalCache?.set(key, terminal);
        applicationCache?.delete(key);
        return Object.freeze({ done: true, found: terminal, pathVisits });
      },
    });
    if (terminal === undefined) {
      applicationCache?.set(key, application);
    }
    return application;
  }

  /** @param {number} maxPathVisits */
  function stepIndex(maxPathVisits) {
    const limit = positiveInteger(maxPathVisits, "wiki basename index");
    if (disposed) {
      return Object.freeze({ done: true, pathVisits: 0 });
    }
    if (basenameIndex) {
      return Object.freeze({ done: true, pathVisits: 0 });
    }
    stagedBasenameIndex ||= new Map();
    let pathVisits = 0;
    while ((indexFile || indexCursor < catalogFiles.length) && pathVisits < limit) {
      if (!indexFile) {
        indexFile = catalogFileAt(catalogFiles, indexCursor);
        indexCursor += 1;
        indexBasenameCursor = 0;
        pathVisits += 1;
        if (indexFile.basename.length > MAX_NORMALIZED_TARGET_LENGTH) {
          // No supported authored target can name this basename. Avoid hashing or
          // retaining its unbounded provider identity while preserving the file in
          // the canonical catalog for exact membership.
          indexFile = null;
          continue;
        }
      }
      while (indexBasenameCursor < indexFile.basename.length && pathVisits < limit) {
        indexFile.basename.charCodeAt(indexBasenameCursor);
        indexBasenameCursor += 1;
        pathVisits += 1;
      }
      if (indexBasenameCursor < indexFile.basename.length || pathVisits >= limit) {
        continue;
      }
      // The only native hash operation is now bounded by the existing authored
      // target policy; every code unit that can contribute was charged above.
      const existing = stagedBasenameIndex.get(indexFile.basename);
      if (existing === undefined) {
        stagedBasenameIndex.set(indexFile.basename, indexFile.path);
      } else if (typeof existing === "string") {
        stagedBasenameIndex.set(indexFile.basename, [existing, indexFile.path]);
      } else {
        existing.push(indexFile.path);
      }
      indexFile = null;
      pathVisits += 1;
    }
    if (indexFile || indexCursor < catalogFiles.length) {
      return Object.freeze({ done: false, pathVisits });
    }
    // Publication is the linearization point. Queries never observe the staged
    // prefix, and a disposed context cannot retain or publish it.
    basenameIndex = stagedBasenameIndex;
    stagedBasenameIndex = null;
    return Object.freeze({ done: true, pathVisits });
  }

  /** @param {WikiLookupPlan} plan @param {number} maxPathVisits */
  function stepFallback(plan, maxPathVisits) {
    const indexStep = stepIndex(maxPathVisits);
    if (!indexStep.done) {
      return Object.freeze({ done: false, pathVisits: indexStep.pathVisits, summary: null });
    }
    let pathVisits = indexStep.pathVisits;
    if (!plan.lookup || !plan.lookupKind || !basenameIndex) {
      return Object.freeze({
        done: true,
        pathVisits,
        summary: emptyCandidateSummary(),
      });
    }
    const leaf = basename(plan.lookup);
    const bucket = basenameIndex.get(leaf);
    if (plan.lookupKind === "basename") {
      let summary = basenameSummaries?.get(leaf);
      if (!summary) {
        summary = summaryForBucket(bucket);
        basenameSummaries?.set(leaf, summary);
      }
      return Object.freeze({ done: true, pathVisits, summary });
    }

    const key = plan.lookup;
    const cachedSummary = suffixSummaries?.get(key);
    if (cachedSummary) {
      return Object.freeze({ done: true, pathVisits, summary: cachedSummary });
    }
    let query = suffixQueries?.get(key);
    if (query) {
      const remaining = maxPathVisits - pathVisits;
      if (remaining < 1 && !query.done) {
        return Object.freeze({ done: false, pathVisits, summary: null });
      }
      const queryStep = stepSuffixQuery(query, Math.max(remaining, 1));
      pathVisits += queryStep.pathVisits;
      if (queryStep.done && queryStep.summary) {
        suffixQueries?.delete(key);
        suffixSummaries?.set(key, queryStep.summary);
      }
      return Object.freeze({
        done: queryStep.done,
        pathVisits,
        summary: queryStep.summary,
      });
    }

    let lookups = qualifiedLookups?.get(leaf);
    if (!lookups) {
      lookups = new Set();
      qualifiedLookups?.set(leaf, lookups);
    }
    // A cold linear scan is cheaper than constructing an index for a one-off
    // qualified target. At the second distinct target, the build breaks even with
    // a second full scan and prevents distinct-target × bucket work thereafter.
    const promote = Array.isArray(bucket) && bucket.length > 1 && lookups.size > 0;
    lookups.add(key);
    let segmentIndex = null;
    if (promote) {
      segmentIndex = segmentIndexes?.get(leaf) || null;
      if (!segmentIndex) {
        segmentIndex = segmentIndexState(bucket, leaf);
        segmentIndexes?.set(leaf, segmentIndex);
      }
      const remaining = maxPathVisits - pathVisits;
      if (remaining < 1 && !segmentIndex.done) {
        return Object.freeze({ done: false, pathVisits, summary: null });
      }
      const indexStep = stepSegmentIndex(segmentIndex, Math.max(remaining, 1));
      pathVisits += indexStep.pathVisits;
      if (!indexStep.done) {
        return Object.freeze({ done: false, pathVisits, summary: null });
      }
    }
    query = suffixQueryState(key, bucket, segmentIndex?.root || null, leaf);
    suffixQueries?.set(key, query);
    const remaining = maxPathVisits - pathVisits;
    if (remaining < 1 && !query.done) {
      return Object.freeze({ done: false, pathVisits, summary: null });
    }
    const queryStep = stepSuffixQuery(query, Math.max(remaining, 1));
    pathVisits += queryStep.pathVisits;
    if (queryStep.done && queryStep.summary) {
      suffixQueries?.delete(key);
      suffixSummaries?.set(key, queryStep.summary);
    }
    return Object.freeze({
      done: queryStep.done,
      pathVisits,
      summary: queryStep.summary,
    });
  }

  return Object.freeze({
    begin,
    beginTrusted,
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      // Applications retain this context closure while a newer coordinator
      // generation reaches them cooperatively. Sever the large immutable snapshot
      // immediately rather than retaining it until every old job is revisited.
      catalogFiles = Object.freeze([]);
      membership?.clear();
      membership = null;
      membershipApplications?.clear();
      membershipApplications = null;
      sourceMembership = null;
      sourceMembershipApplications = null;
      basenameIndex?.clear();
      basenameIndex = null;
      stagedBasenameIndex?.clear();
      stagedBasenameIndex = null;
      indexFile = null;
      basenameSummaries?.clear();
      basenameSummaries = null;
      suffixQueries?.clear();
      suffixQueries = null;
      suffixSummaries?.clear();
      suffixSummaries = null;
      qualifiedLookups?.clear();
      qualifiedLookups = null;
      segmentIndexes?.clear();
      segmentIndexes = null;
    },
    stepIndex,
  });
}

/**
 * Advance one raw UTF-16 comparison without hiding an arbitrarily long common
 * prefix inside a nominal catalog visit.
 *
 * @param {{candidate: string, leftIndex: number, result: number | null}} state
 * @param {string} target
 * @param {number} maxPathVisits
 */
function stepCatalogComparison(state, target, maxPathVisits) {
  let pathVisits = 0;
  while (
    state.result === null &&
    state.leftIndex < state.candidate.length &&
    state.leftIndex < target.length &&
    pathVisits < maxPathVisits
  ) {
    const left = state.candidate.charCodeAt(state.leftIndex);
    const right = target.charCodeAt(state.leftIndex);
    state.leftIndex += 1;
    pathVisits += 1;
    if (left !== right) {
      state.result = left < right ? -1 : 1;
    }
  }
  if (state.result === null && pathVisits < maxPathVisits) {
    state.result =
      state.candidate.length === target.length
        ? 0
        : state.candidate.length < target.length
          ? -1
          : 1;
    pathVisits += 1;
  }
  return pathVisits;
}

/**
 * @param {Readonly<WikiIntent>} value
 * @param {{complete: boolean, files: ReadonlyArray<unknown>}} catalog
 * @param {PreparedSourcePath} source
 * @param {object} exactResolutionIdentity
 * @returns {WikiResolution | WikiLookupPlan}
 */
function prepareWikiTarget(value, catalog, source, exactResolutionIdentity) {
  if (value.authoredTarget.length > MAX_AUTHORED_TARGET_LENGTH) {
    return unsupported("target-too-long");
  }
  if (catalog.files.length > MAX_LOOKUP_FILES) {
    return unsupported("catalog-too-large");
  }
  if (value.authoredTarget.includes("\\")) {
    return unsafe("backslash-path");
  }
  if (value.authoredTarget.includes("\0")) {
    return unsafe("nul-byte");
  }

  const parsed = parseWikiTarget(value.authoredTarget);
  if ("status" in parsed) {
    return parsed;
  }
  const fragment = locationFragment(parsed.location);
  if (typeof fragment !== "string" && fragment !== undefined) {
    return fragment;
  }
  if (!parsed.note) {
    return internalResult(
      source.sourcePath,
      value.action,
      fragment,
      value.action === "embed" ? "markdown" : undefined,
      exactResolutionIdentity,
    );
  }

  const notePath = appendMarkdownExtension(parsed.note.replaceAll("%", "%25"));
  const mediaKind = value.action === "embed" ? mediaKindForAuthoredPath(notePath) : undefined;
  const explicitRelative = notePath.startsWith("./") || notePath.startsWith("../");
  const explicitRoot = notePath.startsWith("/");
  const qualified = notePath.includes("/");
  if (explicitRelative || explicitRoot) {
    const exactPath = normalizeWikiPath(
      explicitRelative ? source : null,
      explicitRoot ? notePath.slice(1) : notePath,
    );
    return typeof exactPath === "string"
      ? Object.freeze({
          action: value.action,
          exactPath,
          fragment,
          mediaKind,
          miss: /** @type {const} */ ("not-found"),
          resolutionIdentity: exactResolutionIdentity,
        })
      : exactPath;
  }

  if (qualified) {
    const exactPath = normalizeWikiPath(null, notePath);
    const lookupKind =
      typeof exactPath === "string" && exactPath.includes("/")
        ? /** @type {const} */ ("suffix")
        : /** @type {const} */ ("basename");
    return typeof exactPath === "string"
      ? Object.freeze({
          action: value.action,
          exactPath,
          fragment,
          lookup: exactPath,
          // Dot-segment normalization can remove the last directory component
          // (`x/../Leaf`). Choose fallback semantics from the normalized
          // identity so that case remains an ordinary basename lookup.
          lookupKind,
          mediaKind,
          miss: /** @type {const} */ ("fallback"),
          resolutionIdentity: exactResolutionIdentity,
        })
      : exactPath;
  }

  const sourceDirectoryPath = normalizeWikiPath(source, notePath);
  return typeof sourceDirectoryPath === "string"
    ? Object.freeze({
        action: value.action,
        exactPath: sourceDirectoryPath,
        fragment,
        lookup: notePath,
        lookupKind: /** @type {const} */ ("basename"),
        mediaKind,
        miss: /** @type {const} */ ("fallback"),
        resolutionIdentity: exactResolutionIdentity,
      })
    : sourceDirectoryPath;
}

/** @param {BasenameBucket | undefined} bucket @returns {CandidateSummary} */
function summaryForBucket(bucket) {
  if (bucket === undefined) {
    return emptyCandidateSummary();
  }
  if (typeof bucket === "string") {
    return Object.freeze({
      candidateCount: 1,
      candidates: Object.freeze([bucket]),
      overflow: false,
    });
  }
  return Object.freeze({
    candidateCount: bucket.length,
    candidates: Object.freeze(bucket.slice(0, MAX_RETURNED_CANDIDATES)),
    overflow: bucket.length > MAX_LOOKUP_CANDIDATES,
  });
}

function emptyCandidateSummary() {
  return Object.freeze({
    candidateCount: 0,
    candidates: Object.freeze([]),
    overflow: false,
  });
}

/** @typedef {{candidateCount: number, candidates: string[], children: Map<string, string | SegmentNode>, overflow: boolean, suffixLength: number, terminalPath: string | null}} SegmentNode */

/** @param {number} suffixLength @param {string[]} candidates @returns {SegmentNode} */
function segmentNode(suffixLength, candidates) {
  return {
    candidateCount: candidates.length,
    candidates: candidates.slice(0, MAX_RETURNED_CANDIDATES),
    children: new Map(),
    overflow: candidates.length > MAX_LOOKUP_CANDIDATES,
    suffixLength,
    terminalPath: null,
  };
}

/** @param {SegmentNode} node @param {string} path */
function addSegmentCandidate(node, path) {
  node.candidateCount += 1;
  if (node.candidates.length < MAX_RETURNED_CANDIDATES) {
    // The catalog is canonical and code-unit sorted, and the staged index consumes
    // it in that order. Appending therefore preserves the exact candidate preview
    // without an extra comparison sort in each query.
    node.candidates.push(path);
  }
  node.overflow = node.candidateCount > MAX_LOOKUP_CANDIDATES;
}

/** @param {string} path @param {SegmentNode} node @param {number} end */
function segmentInsertion(path, node, end) {
  return {
    end,
    /** @type {string | SegmentNode | undefined} */
    entry: undefined,
    node,
    path,
    phase: "start",
    scanIndex: end - 1,
    segment: "",
    segmentStart: 0,
  };
}

/**
 * A basename-local reverse-segment trie is promoted on the second distinct query.
 * Unique branches remain direct path references. Nodes only appear where paths
 * actually collide, and their summaries are built in catalog order. This avoids
 * both N×query scans and the former O(N log N × suffix length) reverse comparator.
 *
 * @param {string[]} bucket
 * @param {string} leaf
 */
function segmentIndexState(bucket, leaf) {
  return {
    bucket,
    cursor: 0,
    /** @type {ReturnType<typeof segmentInsertion> | null} */
    current: null,
    done: false,
    leaf,
    /** @type {ReturnType<typeof segmentInsertion>[]} */
    pending: [],
    /** @type {SegmentNode | null} */
    root: null,
    /** @type {SegmentNode | null} */
    stagedRoot: segmentNode(leaf.length, []),
  };
}

/**
 * Build and atomically publish a reverse-segment trie. Every catalog candidate,
 * code unit inspected while finding a segment, map operation, node promotion, and
 * summary update consumes one visit. A long shared suffix can therefore suspend in
 * the middle of a path instead of hiding an unbounded string comparator in a slice.
 *
 * @param {ReturnType<typeof segmentIndexState>} state
 * @param {number} maxPathVisits
 */
function stepSegmentIndex(state, maxPathVisits) {
  if (state.done) {
    return Object.freeze({ done: true, pathVisits: 0 });
  }
  let pathVisits = 0;
  while (pathVisits < maxPathVisits && !state.done) {
    const root = state.stagedRoot;
    if (!root) {
      throw new Error("wiki segment index lost its staged root");
    }
    if (!state.current) {
      state.current = state.pending.pop() || null;
      if (!state.current && state.cursor < state.bucket.length) {
        const path = state.bucket[state.cursor];
        state.cursor += 1;
        pathVisits += 1;
        state.current = segmentInsertion(
          path,
          root,
          Math.max(path.length - state.leaf.length - 1, 0),
        );
      }
      if (!state.current) {
        state.root = root;
        state.stagedRoot = null;
        state.done = true;
        continue;
      }
    }

    const insertion = state.current;
    if (insertion.phase === "start") {
      if (insertion.end <= 0) {
        insertion.node.terminalPath = insertion.path;
        state.current = null;
        pathVisits += 1;
        continue;
      }
      insertion.scanIndex = insertion.end - 1;
      insertion.phase = "scan";
      continue;
    }
    if (insertion.phase === "scan") {
      if (insertion.scanIndex < 0) {
        insertion.segmentStart = 0;
        insertion.phase = "lookup";
        continue;
      }
      const unit = insertion.path.charCodeAt(insertion.scanIndex);
      pathVisits += 1;
      if (unit === 47) {
        insertion.segmentStart = insertion.scanIndex + 1;
        insertion.phase = "lookup";
      } else {
        insertion.scanIndex -= 1;
      }
      continue;
    }
    if (insertion.phase === "lookup") {
      if (insertion.end - insertion.segmentStart > MAX_NORMALIZED_TARGET_LENGTH) {
        // No supported authored target can name this whole segment. Provider
        // paths still contribute to an already-built ancestor summary, but there
        // is no reachable deeper key to retain or allocate.
        state.current = null;
        pathVisits += 1;
        continue;
      }
      // The preceding scan charged every code unit copied into this key.
      insertion.segment = insertion.path.slice(insertion.segmentStart, insertion.end);
      insertion.entry = insertion.node.children.get(insertion.segment);
      insertion.phase = "apply";
      pathVisits += 1;
      continue;
    }

    const nextEnd = insertion.segmentStart > 0 ? insertion.segmentStart - 1 : 0;
    if (insertion.entry === undefined) {
      insertion.node.children.set(insertion.segment, insertion.path);
      state.current = null;
      pathVisits += 1;
      continue;
    }
    if (typeof insertion.entry === "string") {
      const childSuffixLength = insertion.path.length - insertion.segmentStart;
      if (childSuffixLength > MAX_NORMALIZED_TARGET_LENGTH) {
        // The parent already retains the exact summary for both candidates.
        // No supported target can reach a child whose cumulative suffix is
        // longer than the normalized authored-target envelope, so stop before
        // allocating or descending through the provider-only prefix.
        state.current = null;
        pathVisits += 1;
        continue;
      }
      if (maxPathVisits - pathVisits < 2) {
        break;
      }
      const child = segmentNode(childSuffixLength, [insertion.entry, insertion.path]);
      insertion.node.children.set(insertion.segment, child);
      const existingEnd = Math.max(insertion.entry.length - child.suffixLength - 1, 0);
      // LIFO order is deliberate: process the older catalog path first so every
      // deeper node also receives candidates in canonical order.
      state.pending.push(segmentInsertion(insertion.path, child, nextEnd));
      state.pending.push(segmentInsertion(insertion.entry, child, existingEnd));
      state.current = null;
      pathVisits += 2;
      continue;
    }
    addSegmentCandidate(insertion.entry, insertion.path);
    insertion.node = insertion.entry;
    insertion.end = nextEnd;
    insertion.phase = "start";
    insertion.entry = undefined;
    insertion.segment = "";
    pathVisits += 1;
  }
  return Object.freeze({ done: state.done, pathVisits });
}

/**
 * @param {string} lookup
 * @param {BasenameBucket | undefined} bucket
 * @param {SegmentNode | null} root
 * @param {string} leaf
 * @returns {SuffixQueryState}
 */
function suffixQueryState(lookup, bucket, root, leaf) {
  return {
    bucket,
    candidateCount: 0,
    candidates: /** @type {string[]} */ ([]),
    cursor: 0,
    done: bucket === undefined,
    leaf,
    /** @type {SuffixQueryState | null} */
    leafQuery: null,
    lookup,
    lookupDirectoryEnd: Math.max(lookup.length - leaf.length - 1, 0),
    /** @type {{path: string, pathIndex: number, lookupIndex: number, phase: string} | null} */
    match: null,
    mode: root ? "trie" : "scan",
    /** @type {SegmentNode | null} */
    node: root,
    overflow: false,
    phase: "start",
    scanIndex: Math.max(lookup.length - leaf.length - 2, -1),
    segment: "",
    segmentEnd: Math.max(lookup.length - leaf.length - 1, 0),
    segmentStart: 0,
    /** @type {CandidateSummary | null} */
    summary: bucket === undefined ? emptyCandidateSummary() : null,
  };
}

/** @param {ReturnType<typeof suffixQueryState>} state */
function finishSuffixQuery(state) {
  state.done = true;
  state.summary ||= Object.freeze({
    candidateCount: state.candidateCount,
    candidates: Object.freeze([...state.candidates]),
    overflow: state.overflow,
  });
}

/** @param {ReturnType<typeof suffixQueryState>} state @param {string} path */
function recordSuffixCandidate(state, path) {
  state.candidateCount += 1;
  if (state.candidates.length < MAX_RETURNED_CANDIDATES) {
    state.candidates.push(path);
  }
  if (state.candidateCount > MAX_LOOKUP_CANDIDATES) {
    state.overflow = true;
    finishSuffixQuery(state);
  }
}

/**
 * Advance a cold query one candidate/code unit at a time. The basename has already
 * matched by construction, so comparisons only inspect the qualified directory
 * suffix and its slash boundary.
 *
 * @param {ReturnType<typeof suffixQueryState>} state
 * @param {number} maxPathVisits
 */
function stepLinearSuffixQuery(state, maxPathVisits) {
  let pathVisits = 0;
  const length = Array.isArray(state.bucket) ? state.bucket.length : state.bucket ? 1 : 0;
  while (!state.done && pathVisits < maxPathVisits) {
    if (!state.match) {
      if (state.cursor >= length) {
        finishSuffixQuery(state);
        break;
      }
      const path = typeof state.bucket === "string" ? state.bucket : state.bucket?.[state.cursor];
      state.cursor += 1;
      pathVisits += 1;
      if (!path) {
        continue;
      }
      state.match = {
        lookupIndex: state.lookupDirectoryEnd - 1,
        path,
        pathIndex: path.length - state.leaf.length - 2,
        phase: "compare",
      };
      continue;
    }
    const match = state.match;
    if (match.phase === "compare" && match.lookupIndex >= 0) {
      const equal =
        match.pathIndex >= 0 &&
        match.path.charCodeAt(match.pathIndex) === state.lookup.charCodeAt(match.lookupIndex);
      match.pathIndex -= 1;
      match.lookupIndex -= 1;
      pathVisits += 1;
      if (!equal) {
        state.match = null;
      } else if (match.lookupIndex < 0) {
        match.phase = "boundary";
      }
      continue;
    }
    if (match.phase === "boundary") {
      const matches = match.pathIndex < 0 || match.path.charCodeAt(match.pathIndex) === 47;
      match.phase = matches ? "record" : "done";
      pathVisits += 1;
      continue;
    }
    if (match.phase === "record") {
      recordSuffixCandidate(state, match.path);
      pathVisits += 1;
    }
    state.match = null;
  }
  return pathVisits;
}

/** @param {SegmentNode} node @returns {CandidateSummary} */
function summaryForSegmentNode(node) {
  return Object.freeze({
    candidateCount: node.candidateCount,
    candidates: Object.freeze([...node.candidates]),
    overflow: node.overflow,
  });
}

/**
 * @param {ReturnType<typeof suffixQueryState>} state
 * @param {number} maxPathVisits
 */
function stepTrieSuffixQuery(state, maxPathVisits) {
  let pathVisits = 0;
  while (!state.done && pathVisits < maxPathVisits) {
    if (state.leafQuery) {
      const step = stepSuffixQuery(state.leafQuery, maxPathVisits - pathVisits);
      pathVisits += step.pathVisits;
      if (step.done && step.summary) {
        state.done = true;
        state.summary = step.summary;
      }
      break;
    }
    const node = state.node;
    if (!node) {
      state.done = true;
      state.summary = emptyCandidateSummary();
      break;
    }
    if (state.phase === "start") {
      if (state.segmentEnd <= 0) {
        state.done = true;
        state.summary = summaryForSegmentNode(node);
        continue;
      }
      state.scanIndex = state.segmentEnd - 1;
      state.phase = "scan";
      continue;
    }
    if (state.phase === "scan") {
      if (state.scanIndex < 0) {
        state.segmentStart = 0;
        state.phase = "lookup";
        continue;
      }
      const unit = state.lookup.charCodeAt(state.scanIndex);
      pathVisits += 1;
      if (unit === 47) {
        state.segmentStart = state.scanIndex + 1;
        state.phase = "lookup";
      } else {
        state.scanIndex -= 1;
      }
      continue;
    }
    state.segment = state.lookup.slice(state.segmentStart, state.segmentEnd);
    const entry = node.children.get(state.segment);
    pathVisits += 1;
    if (entry === undefined) {
      state.done = true;
      state.summary = emptyCandidateSummary();
      continue;
    }
    if (typeof entry === "string") {
      state.leafQuery = suffixQueryState(state.lookup, entry, null, state.leaf);
      continue;
    }
    const nextEnd = state.segmentStart > 0 ? state.segmentStart - 1 : 0;
    if (nextEnd <= 0) {
      state.done = true;
      state.summary = summaryForSegmentNode(entry);
      continue;
    }
    state.node = entry;
    state.segmentEnd = nextEnd;
    state.phase = "start";
    state.segment = "";
  }
  return pathVisits;
}

/** @param {ReturnType<typeof suffixQueryState>} state @param {number} maxPathVisits */
function stepSuffixQuery(state, maxPathVisits) {
  if (state.done && state.summary) {
    return Object.freeze({ done: true, pathVisits: 0, summary: state.summary });
  }
  const pathVisits =
    state.mode === "trie"
      ? stepTrieSuffixQuery(state, maxPathVisits)
      : stepLinearSuffixQuery(state, maxPathVisits);
  return Object.freeze({ done: state.done, pathVisits, summary: state.summary });
}

/** @param {CandidateSummary} summary @param {"navigate" | "embed"} action @param {string | undefined} fragment @param {"markdown" | "image" | "audio" | "video" | "resource" | undefined} mediaKind */
function resolutionFromSummary(summary, action, fragment, mediaKind) {
  if (summary.overflow) {
    return unsupported("too-many-candidates");
  }
  if (summary.candidateCount === 0) {
    return missing("not-found");
  }
  if (summary.candidateCount > 1) {
    return Object.freeze({
      status: /** @type {const} */ ("ambiguous"),
      reason: "ambiguous-target",
      candidateCount: summary.candidateCount,
      candidates: summary.candidates,
    });
  }
  return internalResult(summary.candidates[0], action, fragment, mediaKind);
}

/** @param {boolean} done @param {number} pathVisits @param {WikiResolution | null} result */
function resolutionStep(done, pathVisits, result) {
  return Object.freeze({ done, pathVisits, result });
}

/** @param {unknown} intent @returns {Readonly<WikiIntent>} */
function validateIntentShape(intent) {
  if (!intent || typeof intent !== "object") {
    throw new TypeError("wiki resolver requires a WikiIntent");
  }
  const value = /** @type {Record<string, unknown>} */ (intent);
  if (value.action !== "navigate" && value.action !== "embed") {
    throw new TypeError("wiki link action must be navigate or embed");
  }
  if (typeof value.sourcePath !== "string" || typeof value.authoredTarget !== "string") {
    throw new TypeError("wiki link paths must be strings");
  }
  if (value.label !== undefined && typeof value.label !== "string") {
    throw new TypeError("wiki link label must be a string");
  }
  return /** @type {Readonly<WikiIntent>} */ (value);
}

/**
 * Strict direct-call boundary. Production reconciliation uses the cooperative
 * trusted source context because the core catalog has already established these
 * invariants.
 *
 * @param {string} sourcePath
 * @returns {PreparedSourcePath}
 */
function prepareSourcePath(sourcePath) {
  if (!sourcePath || sourcePath.startsWith("/") || sourcePath.endsWith("/")) {
    throw new TypeError("wiki link source path is invalid");
  }
  let segmentStart = 0;
  for (let index = 0; index < sourcePath.length; index += 1) {
    const unit = sourcePath.charCodeAt(index);
    if (unit === 0 || unit === 92) {
      throw new TypeError("wiki link source path must identify a normalized logical file");
    }
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const following = sourcePath.charCodeAt(index + 1);
      if (following < 0xdc00 || following > 0xdfff) {
        throw new TypeError("wiki link source path must identify a normalized logical file");
      }
      index += 1;
      continue;
    }
    if (unit >= 0xdc00 && unit <= 0xdfff) {
      throw new TypeError("wiki link source path must identify a normalized logical file");
    }
    if (unit !== 47) {
      continue;
    }
    if (invalidSourceSegment(sourcePath, segmentStart, index)) {
      throw new TypeError("wiki link source path must identify a normalized logical file");
    }
    segmentStart = index + 1;
  }
  if (invalidSourceSegment(sourcePath, segmentStart, sourcePath.length)) {
    throw new TypeError("wiki link source path must identify a normalized logical file");
  }

  const reverseSlashes = [];
  let cursor = sourcePath.length - 1;
  while (cursor >= 0 && reverseSlashes.length < MAX_PARENT_SEGMENTS) {
    if (sourcePath.charCodeAt(cursor) === 47) {
      reverseSlashes.push(cursor);
    }
    cursor -= 1;
  }
  return Object.freeze({
    completePrefix: cursor < 0,
    reverseSlashes: Object.freeze(reverseSlashes),
    sourcePath,
  });
}

/** @param {string} sourcePath @param {number} start @param {number} end */
function invalidSourceSegment(sourcePath, start, end) {
  const length = end - start;
  return (
    length === 0 ||
    (length === 1 && sourcePath.charCodeAt(start) === 46) ||
    (length === 2 && sourcePath.charCodeAt(start) === 46 && sourcePath.charCodeAt(start + 1) === 46)
  );
}

/** @param {unknown} snapshot */
function validateSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    throw new TypeError("wiki resolver requires a catalog snapshot");
  }
  const value = /** @type {Record<string, unknown>} */ (snapshot);
  if (typeof value.complete !== "boolean" || !Array.isArray(value.files)) {
    throw new TypeError("wiki resolver requires snapshot completeness and files");
  }
  const truncated = snapshotTruncation(value);
  return Object.freeze({ complete: value.complete, files: value.files, truncated });
}

/**
 * Read the terminal truncated state. It cannot accompany complete coverage.
 *
 * @param {Record<string, unknown>} value
 */
function snapshotTruncation(value) {
  if (value.truncated !== undefined && typeof value.truncated !== "boolean") {
    throw new TypeError("wiki resolver requires a boolean snapshot truncation state");
  }
  if (value.complete && value.truncated) {
    throw new TypeError("wiki resolver snapshot cannot be both complete and truncated");
  }
  return value.truncated === true;
}

/** @param {string} authoredTarget */
function parseWikiTarget(authoredTarget) {
  const separator = authoredTarget.indexOf("#");
  const note = (separator === -1 ? authoredTarget : authoredTarget.slice(0, separator)).trim();
  const location = separator === -1 ? undefined : authoredTarget.slice(separator + 1).trim();
  if (!note && !location) {
    return unsupported("empty-target");
  }
  return Object.freeze({ location: location || undefined, note });
}

/** @param {string | undefined} location */
function locationFragment(location) {
  if (!location) {
    return undefined;
  }
  if (location.startsWith("^")) {
    const block = location.slice(1);
    if (!/^[A-Za-z0-9-]+$/.test(block)) {
      return unsupported("invalid-block-id");
    }
    return `obsidian-block-${block}`;
  }
  try {
    encodeURIComponent(location);
    return `obsidian-heading-${location}`;
  } catch (_error) {
    return unsafe("invalid-unicode");
  }
}

/** @param {string} path */
function appendMarkdownExtension(path) {
  const leaf = basename(path);
  return leaf.includes(".") ? path : `${path}.md`;
}

/** @param {PreparedSourcePath | null} source @param {string} authoredPath */
function normalizeWikiPath(source, authoredPath) {
  if (!authoredPath || authoredPath.endsWith("/")) {
    return unsafe("non-file-path");
  }
  const segments = [];
  let parentPops = 0;
  for (const segment of authoredPath.split("/")) {
    if (!segment) {
      return unsafe("non-canonical-path");
    }
    if (segment === ".") {
      continue;
    }
    if (segment === "..") {
      if (segments.length) {
        segments.pop();
        continue;
      }
      if (!source) {
        return unsafe("path-escapes-served-root");
      }
      parentPops += 1;
      continue;
    }
    if (segment.includes("\\") || segment.includes("\0")) {
      return unsafe(segment.includes("\\") ? "backslash-path" : "nul-byte");
    }
    segments.push(segment);
  }
  const authored = segments.join("/");
  let base = "";
  if (source) {
    if (parentPops < source.reverseSlashes.length) {
      base = source.sourcePath.slice(0, source.reverseSlashes[parentPops]);
    } else if (source.completePrefix) {
      if (parentPops > source.reverseSlashes.length) {
        return unsafe("path-escapes-served-root");
      }
    } else {
      // MAX_PARENT_SEGMENTS is derived from the authored-target limit, so a
      // supported target cannot exhaust an incomplete retained window.
      throw new Error("wiki source parent window was unexpectedly exhausted");
    }
  }
  return base && authored ? `${base}/${authored}` : base || authored;
}

/** @param {number} value @param {string} label */
function positiveInteger(value, label) {
  if (!Number.isFinite(value) || value < 1) {
    throw new TypeError(`${label} requires a positive path-visit bound`);
  }
  return Math.floor(value);
}

/**
 * The core catalog owns validation and canonical ordering. Reading the projection is
 * intentionally position-independent: consumers must not reject a legitimate long
 * identity only when a binary search or fallback happens to visit it.
 *
 * @param {ReadonlyArray<unknown>} files
 * @param {number} index
 */
function catalogFileAt(files, index) {
  return /** @type {Readonly<{basename: string, path: string}>} */ (files[index]);
}

/** @param {ReadonlyArray<unknown>} files @param {number} index */
function catalogPathAt(files, index) {
  return catalogFileAt(files, index).path;
}

/** @param {string} path */
function basename(path) {
  const separator = path.lastIndexOf("/");
  return separator === -1 ? path : path.slice(separator + 1);
}

/** @param {string} path @param {"navigate" | "embed"} action @param {string | undefined} fragment @param {"markdown" | "image" | "audio" | "video" | "resource" | undefined=} mediaKind @param {object=} resolutionIdentity */
function internalResult(path, action, fragment, mediaKind, resolutionIdentity) {
  /** @type {{status: "internal", path: string, fragment?: string, mediaKind?: "markdown" | "image" | "audio" | "video" | "resource"}} */
  const result = { status: "internal", path };
  if (fragment) {
    result.fragment = fragment;
  }
  if (action === "embed") {
    result.mediaKind = mediaKind || "resource";
  }
  Object.defineProperty(result, WIKI_RESOLUTION_IDENTITY, {
    value: resolutionIdentity || Object.freeze({ kind: "fallback" }),
  });
  return Object.freeze(result);
}

/** @param {string} path */
function mediaKindForAuthoredPath(path) {
  const leaf = basename(path).toLowerCase();
  const dot = leaf.lastIndexOf(".");
  const extension = dot === -1 ? "" : leaf.slice(dot);
  if (extension === ".md") {
    return /** @type {const} */ ("markdown");
  }
  if (IMAGE_EXTENSIONS.has(extension)) {
    return /** @type {const} */ ("image");
  }
  if (AUDIO_EXTENSIONS.has(extension)) {
    return /** @type {const} */ ("audio");
  }
  if (VIDEO_EXTENSIONS.has(extension)) {
    return /** @type {const} */ ("video");
  }
  return /** @type {const} */ ("resource");
}

/** @param {string} reason */
function pending(reason) {
  return Object.freeze({ status: /** @type {const} */ ("pending"), reason });
}

/** @param {string} reason */
function missing(reason) {
  return Object.freeze({ status: /** @type {const} */ ("missing"), reason });
}

/** @param {string} reason */
function unsafe(reason) {
  return Object.freeze({ status: /** @type {const} */ ("unsafe"), reason });
}

/** @param {string} reason */
function unsupported(reason) {
  return Object.freeze({ status: /** @type {const} */ ("unsupported"), reason });
}
