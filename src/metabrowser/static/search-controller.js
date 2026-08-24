// DOM-independent search orchestration and the browser-local filename provider.

(() => {
  const LOCAL_FILE_PROVIDER_ID = "local-known-files";
  const PROVIDER_ACTIVATION_FALLBACK = "fallback";
  const PROVIDER_ACTIVATION_IMMEDIATE = "immediate";
  /** Default bounds for local result retention and cooperative scanning. */
  const LOCAL_SEARCH_DEFAULTS = Object.freeze({
    chunkSize: 250,
    maxResults: 100,
    syncThreshold: 500,
  });
  /** Providers with no explicit priority sort after focused built-in providers. */
  const DEFAULT_PROVIDER_PRIORITY = 100;
  /** Built-in local navigation results lead later fallback providers. */
  const LOCAL_FILE_PROVIDER_PRIORITY = 10;
  /** Keep a small overflow before pruning so insertion does not sort every match. */
  const RETAINED_RESULT_MULTIPLIER = 2;

  /**
   * @typedef {object} MetabrowserKnownFile
   * @property {string} basename
   * @property {string | null} logicalExtension
   * @property {string} path
   */

  /**
   * @typedef {object} MetabrowserKnownFileCatalogApi
   * @property {() => Readonly<{
   *   complete: boolean,
   *   files: readonly MetabrowserKnownFile[],
   *   observedCount: number,
   *   revision: number,
   * }>} snapshot
   */

  /**
   * @typedef {object} MetabrowserFuzzyRank
   * @property {number} matchClass
   * @property {number} boundaryHits
   * @property {number} contiguousChars
   * @property {number} runCount
   * @property {number} gapChars
   * @property {number} startOffset
   * @property {number} candidateLength
   * @property {number} directoryDepth
   * @property {string} normalizedPath
   * @property {string} originalPath
   */

  /**
   * @typedef {object} MetabrowserFuzzyMatch
   * @property {readonly Readonly<{start: number, end: number}>[]} matchRanges
   * @property {string} path
   * @property {Readonly<MetabrowserFuzzyRank>} rank
   */

  /**
   * @typedef {object} MetabrowserFileFuzzyMatchRuntime
   * @property {(left: MetabrowserFuzzyMatch, right: MetabrowserFuzzyMatch) => number} compareMatches
   * @property {(query: string, path: string) => MetabrowserFuzzyMatch | null} matchPath
   */

  /**
   * @typedef {object} MetabrowserSearchRequest
   * @property {"fuzzy"} match
   * @property {string} query
   * @property {"file"} target
   */

  /**
   * @typedef {object} MetabrowserSearchFileResult
   * @property {string} description
   * @property {string} id
   * @property {"file"} kind
   * @property {string} label
   * @property {string | null} [logicalExtension]
   * @property {readonly Readonly<{start: number, end: number}>[]} matchRanges
   * @property {string} path
   * @property {string} providerId
   * @property {Readonly<MetabrowserFuzzyRank>} [rank]
   * @property {number} score
   */

  /**
   * @typedef {object} MetabrowserSearchBatch
   * @property {number} [candidateCount]
   * @property {boolean} complete
   * @property {string} providerId
   * @property {readonly MetabrowserSearchFileResult[]} results
   * @property {number} [revision]
   * @property {string} [statusMessage]
   * @property {boolean} truncated
   */

  /** @typedef {Readonly<{requestId: number}>} MetabrowserSearchContext */

  /**
   * @typedef {object} MetabrowserSearchProvider
   * @property {"fallback" | "immediate"} [activation]
   * @property {string} id
   * @property {number} [priority]
   * @property {(request: MetabrowserSearchRequest, context: MetabrowserSearchContext,
   *   signal: AbortSignal) => MetabrowserSearchBatch | Promise<MetabrowserSearchBatch>} search
   * @property {(request: MetabrowserSearchRequest) => boolean} [supports]
   */

  /** @typedef {Readonly<{includeFallback?: boolean}>} MetabrowserSearchOptions */

  /**
   * @typedef {object} MetabrowserSearchState
   * @property {readonly Readonly<{
   *   candidateCount?: number,
   *   complete: boolean,
   *   providerId: string,
   *   resultCount: number,
   *   revision?: number,
   *   statusMessage?: string,
   *   truncated: boolean,
   * }>[] } batches
   * @property {boolean} complete
   * @property {readonly string[]} errors
   * @property {"idle" | "searching" | "complete"} phase
   * @property {Readonly<MetabrowserSearchRequest> | null} request
   * @property {number} requestId
   * @property {readonly MetabrowserSearchFileResult[]} results
   * @property {string} statusMessage
   * @property {boolean} truncated
   */

  /** @param {string} left @param {string} right */
  function codeUnitCompare(left, right) {
    if (left < right) {
      return -1;
    }
    if (left > right) {
      return 1;
    }
    return 0;
  }

  function abortError() {
    const error = new Error("Search aborted");
    error.name = "AbortError";
    return error;
  }

  /** @param {AbortSignal} signal */
  function throwIfAborted(signal) {
    if (signal.aborted) {
      throw abortError();
    }
  }

  /** @param {AbortSignal} signal */
  function defaultYieldControl(signal) {
    if (signal.aborted) {
      return Promise.reject(abortError());
    }
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        signal.removeEventListener("abort", onAbort);
        resolve(undefined);
      }, 0);
      function onAbort() {
        clearTimeout(timer);
        reject(abortError());
      }
      signal.addEventListener("abort", onAbort, { once: true });
    });
  }

  /** @param {number | undefined} value @param {number} fallback */
  function positiveInteger(value, fallback) {
    return typeof value === "number" && Number.isFinite(value) && value > 0
      ? Math.floor(value)
      : fallback;
  }

  /** @param {number} count @param {string} [modifier] */
  function fileCount(count, modifier = "") {
    const noun = count === 1 ? "file" : "files";
    return `${count.toLocaleString()}${modifier ? ` ${modifier}` : ""} ${noun}`;
  }

  /** @param {number} count */
  function formattedMatchCount(count) {
    return `${count.toLocaleString()} ${count === 1 ? "match" : "matches"}`;
  }

  /**
   * Create the browser-local provider. It searches one immutable catalog snapshot and
   * never reaches the network.
   * @param {{
   *   catalog: MetabrowserKnownFileCatalogApi,
   *   matcher: MetabrowserFileFuzzyMatchRuntime,
   *   maxResults?: number,
   *   syncThreshold?: number,
   *   chunkSize?: number,
   *   yieldControl?: (signal: AbortSignal) => Promise<void>,
   * }} options
   * @returns {MetabrowserSearchProvider}
   */
  function createLocalFileProvider(options) {
    if (!options?.catalog || !options.matcher) {
      throw new TypeError("Local file search requires a catalog and matcher");
    }
    const { catalog, matcher } = options;
    const maxResults = positiveInteger(options.maxResults, LOCAL_SEARCH_DEFAULTS.maxResults);
    const syncThreshold = positiveInteger(
      options.syncThreshold,
      LOCAL_SEARCH_DEFAULTS.syncThreshold,
    );
    const chunkSize = positiveInteger(options.chunkSize, LOCAL_SEARCH_DEFAULTS.chunkSize);
    const yieldControl = options.yieldControl || defaultYieldControl;

    /** @param {MetabrowserSearchRequest} request */
    function supports(request) {
      return request.target === "file" && request.match === "fuzzy";
    }

    /**
     * @param {MetabrowserSearchRequest} request
     * @param {MetabrowserSearchContext} _context
     * @param {AbortSignal} signal
     * @returns {Promise<MetabrowserSearchBatch>}
     */
    async function search(request, _context, signal) {
      throwIfAborted(signal);
      const snapshot = catalog.snapshot();
      const query = request.query.trim();
      /** @type {Array<{file: MetabrowserKnownFile, match: MetabrowserFuzzyMatch}>} */
      let retained = [];
      let matchCount = 0;

      if (query) {
        const scanChunkSize =
          snapshot.files.length <= syncThreshold ? snapshot.files.length || 1 : chunkSize;
        for (let chunkStart = 0; chunkStart < snapshot.files.length; chunkStart += scanChunkSize) {
          const chunkEnd = Math.min(snapshot.files.length, chunkStart + scanChunkSize);
          for (let index = chunkStart; index < chunkEnd; index += 1) {
            throwIfAborted(signal);
            const file = snapshot.files[index];
            const match = matcher.matchPath(query, file.path);
            if (!match) {
              continue;
            }
            matchCount += 1;
            retained.push({ file, match });
            if (retained.length >= maxResults * RETAINED_RESULT_MULTIPLIER) {
              retained.sort((left, right) => matcher.compareMatches(left.match, right.match));
              retained = retained.slice(0, maxResults);
            }
          }
          if (chunkEnd < snapshot.files.length) {
            await yieldControl(signal);
            throwIfAborted(signal);
          }
        }
      }

      retained.sort((left, right) => matcher.compareMatches(left.match, right.match));
      const ordered = retained.slice(0, maxResults);
      const results = ordered.map(({ file, match }, index) => {
        const separator = file.path.lastIndexOf("/");
        return Object.freeze({
          description: separator >= 0 ? file.path.slice(0, separator) : "",
          id: `file:${file.path}`,
          kind: /** @type {const} */ ("file"),
          label: file.basename,
          logicalExtension: file.logicalExtension,
          matchRanges: match.matchRanges,
          path: file.path,
          providerId: LOCAL_FILE_PROVIDER_ID,
          rank: match.rank,
          score: ordered.length - index,
        });
      });
      const searchScope = fileCount(snapshot.observedCount, snapshot.complete ? "" : "indexed");
      const statusMessage =
        results.length === 0
          ? `No matches in ${searchScope}.${snapshot.complete ? "" : " Scanning continues."}`
          : snapshot.complete
            ? `${formattedMatchCount(matchCount)}.`
            : `${formattedMatchCount(matchCount)} in ${searchScope}. Scanning continues.`;
      return Object.freeze({
        candidateCount: snapshot.observedCount,
        complete: snapshot.complete,
        providerId: LOCAL_FILE_PROVIDER_ID,
        results: Object.freeze(results),
        revision: snapshot.revision,
        statusMessage,
        truncated: matchCount > maxResults,
      });
    }

    return Object.freeze({
      activation: PROVIDER_ACTIVATION_IMMEDIATE,
      id: LOCAL_FILE_PROVIDER_ID,
      priority: LOCAL_FILE_PROVIDER_PRIORITY,
      search,
      supports,
    });
  }

  /** @param {MetabrowserSearchFileResult} result @param {string} providerId */
  function freezeResult(result, providerId) {
    const ranges = Array.isArray(result.matchRanges)
      ? result.matchRanges.map((range) => Object.freeze({ end: range.end, start: range.start }))
      : [];
    const rank = result.rank ? Object.freeze({ ...result.rank }) : undefined;
    return Object.freeze({
      ...result,
      matchRanges: Object.freeze(ranges),
      providerId,
      ...(rank ? { rank } : {}),
      score: Number.isFinite(result.score) ? result.score : 0,
    });
  }

  /**
   * @param {Map<string, MetabrowserSearchBatch>} batches
   * @param {Map<string, {
   *   activation: "fallback" | "immediate",
   *   provider: MetabrowserSearchProvider,
   *   priority: number,
   * }>} registrations
   * @param {number} maxResults
   */
  function composeResults(batches, registrations, maxResults) {
    /** @type {Map<string, MetabrowserSearchFileResult>} */
    const byPath = new Map();
    for (const [providerId, batch] of batches) {
      const priority = registrations.get(providerId)?.priority ?? Number.MAX_SAFE_INTEGER;
      for (const rawResult of batch.results) {
        if (rawResult?.kind !== "file" || typeof rawResult.path !== "string") {
          continue;
        }
        const result = freezeResult(rawResult, providerId);
        const previous = byPath.get(result.path);
        if (!previous) {
          byPath.set(result.path, result);
          continue;
        }
        const previousPriority =
          registrations.get(previous.providerId)?.priority ?? Number.MAX_SAFE_INTEGER;
        if (
          result.score > previous.score ||
          (result.score === previous.score && priority < previousPriority) ||
          (result.score === previous.score &&
            priority === previousPriority &&
            codeUnitCompare(result.providerId, previous.providerId) < 0)
        ) {
          byPath.set(result.path, result);
        }
      }
    }
    const allResults = Array.from(byPath.values()).sort((left, right) => {
      const leftPriority = registrations.get(left.providerId)?.priority ?? Number.MAX_SAFE_INTEGER;
      const rightPriority =
        registrations.get(right.providerId)?.priority ?? Number.MAX_SAFE_INTEGER;
      return (
        right.score - left.score ||
        leftPriority - rightPriority ||
        codeUnitCompare(left.path, right.path) ||
        codeUnitCompare(left.providerId, right.providerId)
      );
    });
    return {
      resultLimitTruncated: allResults.length > maxResults,
      results: Object.freeze(allResults.slice(0, maxResults)),
    };
  }

  /** @param {{maxResults?: number}} [options] */
  function createController(options = {}) {
    const maxResults = positiveInteger(options.maxResults, LOCAL_SEARCH_DEFAULTS.maxResults);
    /** @type {Map<string, {
     *   activation: "fallback" | "immediate",
     *   provider: MetabrowserSearchProvider,
     *   priority: number,
     * }>} */
    const registrations = new Map();
    /** @type {Set<(state: MetabrowserSearchState) => void>} */
    const listeners = new Set();
    let requestSerial = 0;
    let disposed = false;
    /** @type {{controller: AbortController, requestId: number} | null} */
    let active = null;
    /** @type {MetabrowserSearchState} */
    let currentState = Object.freeze({
      batches: Object.freeze([]),
      complete: false,
      errors: Object.freeze([]),
      phase: /** @type {const} */ ("idle"),
      request: null,
      requestId: 0,
      results: Object.freeze([]),
      statusMessage: "",
      truncated: false,
    });

    /** @param {MetabrowserSearchState} state */
    function publish(state) {
      currentState = state;
      for (const listener of listeners) {
        listener(state);
      }
    }

    /** @param {MetabrowserSearchProvider} provider */
    function registerProvider(provider) {
      if (disposed) {
        throw new Error("Search controller is disposed");
      }
      if (!provider?.id || typeof provider.search !== "function") {
        throw new TypeError("A search provider needs a stable id and search function");
      }
      if (registrations.has(provider.id)) {
        throw new Error(`Search provider already registered: ${provider.id}`);
      }
      if (
        provider.activation !== undefined &&
        provider.activation !== PROVIDER_ACTIVATION_IMMEDIATE &&
        provider.activation !== PROVIDER_ACTIVATION_FALLBACK
      ) {
        throw new TypeError(`Unknown search provider activation: ${provider.activation}`);
      }
      registrations.set(provider.id, {
        activation:
          provider.activation === PROVIDER_ACTIVATION_FALLBACK
            ? PROVIDER_ACTIVATION_FALLBACK
            : PROVIDER_ACTIVATION_IMMEDIATE,
        priority:
          typeof provider.priority === "number" && Number.isFinite(provider.priority)
            ? provider.priority
            : DEFAULT_PROVIDER_PRIORITY,
        provider,
      });
      return () => {
        registrations.delete(provider.id);
      };
    }

    /** @param {(state: MetabrowserSearchState) => void} listener */
    function subscribe(listener) {
      if (disposed) {
        throw new Error("Search controller is disposed");
      }
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    }

    /**
     * @param {MetabrowserSearchRequest} rawRequest
     * @param {MetabrowserSearchOptions} [searchOptions]
     * @returns {Promise<MetabrowserSearchState | null>}
     */
    async function search(rawRequest, searchOptions = {}) {
      if (disposed) {
        throw new Error("Search controller is disposed");
      }
      active?.controller.abort();
      requestSerial += 1;
      const requestId = requestSerial;
      const controller = new AbortController();
      active = { controller, requestId };
      const request = Object.freeze({
        match: rawRequest.match,
        query: rawRequest.query,
        target: rawRequest.target,
      });
      const supported = Array.from(registrations.values())
        .filter(({ provider }) => !provider.supports || provider.supports(request))
        .sort(
          (left, right) =>
            left.priority - right.priority || codeUnitCompare(left.provider.id, right.provider.id),
        );
      const immediate = supported.filter(
        ({ activation }) => activation === PROVIDER_ACTIVATION_IMMEDIATE,
      );
      const fallback = supported.filter(
        ({ activation }) => activation === PROVIDER_ACTIVATION_FALLBACK,
      );
      /** @type {typeof supported} */
      const started = [];
      /** @type {Map<string, MetabrowserSearchBatch>} */
      const batches = new Map();
      /** @type {Map<string, string>} */
      const errors = new Map();

      /** @param {"searching" | "complete"} phase */
      function publishComposition(phase) {
        const composition = composeResults(batches, registrations, maxResults);
        const batchMetadata = started.flatMap(({ provider }) => {
          const batch = batches.get(provider.id);
          return batch
            ? [
                Object.freeze({
                  candidateCount: batch.candidateCount,
                  complete: batch.complete,
                  providerId: batch.providerId,
                  resultCount: batch.results.length,
                  revision: batch.revision,
                  statusMessage: batch.statusMessage,
                  truncated: batch.truncated,
                }),
              ]
            : [];
        });
        const orderedErrors = started.flatMap(({ provider }) => {
          const error = errors.get(provider.id);
          return error ? [error] : [];
        });
        const statusMessages = batchMetadata
          .map((batch) => batch.statusMessage)
          .filter((message) => typeof message === "string" && message);
        publish(
          Object.freeze({
            batches: Object.freeze(batchMetadata),
            complete:
              phase === "complete" &&
              orderedErrors.length === 0 &&
              batchMetadata.length === started.length &&
              batchMetadata.every((batch) => batch.complete),
            errors: Object.freeze(orderedErrors),
            phase,
            request,
            requestId,
            results: composition.results,
            statusMessage:
              orderedErrors.length > 0 ? orderedErrors.join(" ") : statusMessages.join(" "),
            truncated:
              composition.resultLimitTruncated || batchMetadata.some((batch) => batch.truncated),
          }),
        );
      }

      /** @param {typeof supported} providers */
      async function runProviders(providers) {
        if (providers.length === 0) {
          return;
        }
        started.push(...providers);
        publishComposition("searching");
        await Promise.all(
          providers.map(async ({ provider }) => {
            try {
              const batch = await provider.search(
                request,
                Object.freeze({ requestId }),
                controller.signal,
              );
              if (controller.signal.aborted || active?.requestId !== requestId) {
                return;
              }
              batches.set(
                provider.id,
                Object.freeze({
                  ...batch,
                  complete: batch.complete === true,
                  providerId: provider.id,
                  results: Array.isArray(batch.results) ? batch.results : [],
                  truncated: batch.truncated === true,
                }),
              );
            } catch (error) {
              if (controller.signal.aborted || active?.requestId !== requestId) {
                return;
              }
              const detail = error instanceof Error ? error.message : String(error);
              errors.set(provider.id, `${provider.id}: ${detail}`);
            } finally {
              if (!controller.signal.aborted && active?.requestId === requestId) {
                publishComposition("searching");
              }
            }
          }),
        );
      }

      if (supported.length === 0) {
        publishComposition("complete");
        active = null;
        return currentState;
      }

      await runProviders(immediate);

      if (controller.signal.aborted || active?.requestId !== requestId) {
        return null;
      }
      const immediateComposition = composeResults(batches, registrations, maxResults);
      const immediateCoverageIncomplete =
        immediate.length === 0 ||
        errors.size > 0 ||
        immediate.some(({ provider }) => batches.get(provider.id)?.complete !== true);
      const shouldRunFallback =
        searchOptions.includeFallback === true ||
        (immediateComposition.results.length === 0 && immediateCoverageIncomplete);
      if (shouldRunFallback) {
        await runProviders(fallback);
      }

      if (controller.signal.aborted || active?.requestId !== requestId) {
        return null;
      }
      publishComposition("complete");
      active = null;
      return currentState;
    }

    function cancel() {
      if (active) {
        active.controller.abort();
        active = null;
      }
    }

    function state() {
      return currentState;
    }

    function dispose() {
      cancel();
      registrations.clear();
      listeners.clear();
      disposed = true;
    }

    return Object.freeze({ cancel, dispose, registerProvider, search, state, subscribe });
  }

  window.MetabrowserSearch = Object.freeze({ createController, createLocalFileProvider });
})();
