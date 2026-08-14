export const NO_EXTENSION_KEY = "(none)";
export const OTHER_KEY = "";

/**
 * Compatibility classifier for consumers that still have only broad presets.
 * New code should pass the shared `mb.fileTypes` runtime to the model builder.
 * @param {unknown} rawPresets
 */
export function createFileTypeCategoryClassifier(rawPresets) {
  /** @type {Map<"docs" | "code" | "data", Array<string>>} */
  const suffixes = new Map([
    ["docs", []],
    ["code", []],
    ["data", []],
  ]);
  if (Array.isArray(rawPresets)) {
    for (const rawPreset of rawPresets) {
      if (!rawPreset || typeof rawPreset !== "object") {
        continue;
      }
      const preset = /** @type {{id?: unknown, values?: unknown}} */ (rawPreset);
      if (preset.id !== "docs" && preset.id !== "code" && preset.id !== "data") {
        continue;
      }
      if (!Array.isArray(preset.values)) {
        continue;
      }
      for (const value of preset.values) {
        if (typeof value === "string" && value.startsWith(".")) {
          suffixes.get(preset.id)?.push(value.toLowerCase());
        }
      }
    }
  }
  return /** @param {string} key */ (key) => {
    const normalized = key.toLowerCase();
    for (const category of /** @type {const} */ (["docs", "code", "data"])) {
      if (suffixes.get(category)?.some((suffix) => normalized.endsWith(suffix))) {
        return category;
      }
    }
    return /** @type {const} */ ("other");
  };
}

/** @param {unknown} raw */
export function normalizeTallyRow(raw) {
  if (!Array.isArray(raw) || raw.length !== 5 || typeof raw[0] !== "string") {
    throw new TypeError("file-type tally must have five cells");
  }
  const values = raw.slice(1);
  if (values.some((value) => !Number.isInteger(value) || /** @type {number} */ (value) < 0)) {
    throw new TypeError("file-type tally values must be nonnegative integers");
  }
  const key = raw[0];
  return Object.freeze({
    key,
    label: key === OTHER_KEY ? "Remaining types" : key === NO_EXTENSION_KEY ? "No extension" : key,
    allFiles: /** @type {number} */ (raw[1]),
    allBytes: /** @type {number} */ (raw[2]),
    unignoredFiles: /** @type {number} */ (raw[3]),
    unignoredBytes: /** @type {number} */ (raw[4]),
  });
}

/** @param {unknown} raw */
function normalizeFamilyTally(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new TypeError("file-type family tally must be an object");
  }
  const value = /** @type {Record<string, unknown>} */ (raw);
  if (typeof value.id !== "string" || !value.id) {
    throw new TypeError("file-type family tally must have an id");
  }
  const metrics = [value.all_files, value.all_bytes, value.unignored_files, value.unignored_bytes];
  if (metrics.some((metric) => !Number.isInteger(metric) || /** @type {number} */ (metric) < 0)) {
    throw new TypeError("file-type family tally values must be nonnegative integers");
  }
  if (!Array.isArray(value.extensions)) {
    throw new TypeError("file-type family tally extensions must be an array");
  }
  return Object.freeze({
    id: value.id,
    allFiles: /** @type {number} */ (value.all_files),
    allBytes: /** @type {number} */ (value.all_bytes),
    unignoredFiles: /** @type {number} */ (value.unignored_files),
    unignoredBytes: /** @type {number} */ (value.unignored_bytes),
    extensions: Object.freeze(value.extensions.map(normalizeTallyRow)),
  });
}

/** @param {unknown} raw */
export function normalizeRollupEnvelope(raw) {
  if (!raw || typeof raw !== "object") {
    throw new TypeError("rollup envelope must be an object");
  }
  const value = /** @type {Record<string, unknown>} */ (raw);
  const node =
    value.node && typeof value.node === "object"
      ? /** @type {Record<string, unknown>} */ (value.node)
      : null;
  /** @param {unknown} candidate */
  const integer = (candidate) =>
    Number.isInteger(candidate) && /** @type {number} */ (candidate) >= 0
      ? /** @type {number} */ (candidate)
      : 0;
  const semantic =
    value.type_tallies && typeof value.type_tallies === "object"
      ? /** @type {Record<string, unknown>} */ (value.type_tallies)
      : null;
  const legacyTallies = Array.isArray(value.ext_tallies)
    ? value.ext_tallies.map(normalizeTallyRow)
    : [];
  return Object.freeze({
    path: typeof value.path === "string" ? value.path : "",
    indexStatus: typeof value.index_status === "string" ? value.index_status : "pending",
    indexedFiles: integer(value.indexed_files),
    maxFiles: integer(value.max_files),
    truncated: value.truncated === true,
    totals: node
      ? Object.freeze({
          allFiles: integer(node.total_files),
          allBytes: integer(node.total_size),
          unignoredFiles: integer(node.unignored_files),
          unignoredBytes: integer(node.unignored_size),
        })
      : null,
    families: Object.freeze(
      semantic && Array.isArray(semantic.families)
        ? semantic.families.map(normalizeFamilyTally)
        : [],
    ),
    tallies: Object.freeze(
      semantic && Array.isArray(semantic.extensions)
        ? semantic.extensions.map(normalizeTallyRow)
        : legacyTallies,
    ),
  });
}

/** @param {ReturnType<typeof normalizeRollupEnvelope>} envelope @param {boolean} showIgnored */
export function selectPopulation(envelope, showIgnored) {
  if (!envelope.totals) {
    return null;
  }
  const ignoredFiles = Math.max(0, envelope.totals.allFiles - envelope.totals.unignoredFiles);
  const ignoredBytes = Math.max(0, envelope.totals.allBytes - envelope.totals.unignoredBytes);
  return Object.freeze({
    files: showIgnored ? envelope.totals.allFiles : envelope.totals.unignoredFiles,
    bytes: showIgnored ? envelope.totals.allBytes : envelope.totals.unignoredBytes,
    allFiles: envelope.totals.allFiles,
    allBytes: envelope.totals.allBytes,
    ignoredFiles,
    ignoredBytes,
  });
}

/** @param {number} numerator @param {number} denominator @param {Intl.NumberFormat} formatter */
export function formatPercent(numerator, denominator, formatter) {
  if (numerator === 0 || denominator === 0) {
    return "0%";
  }
  const percent = (numerator / denominator) * 100;
  return percent < 0.1 ? "<0.1%" : `${formatter.format(percent)}%`;
}

/** @param {number} numerator @param {number} denominator */
function percentShare(numerator, denominator) {
  return denominator === 0 ? 0 : (numerator / denominator) * 100;
}

/** @param {number} files @param {number} bytes @param {number} totalFiles @param {number} totalBytes */
function dualScore(files, bytes, totalFiles, totalBytes) {
  const fileShare = percentShare(files, totalFiles);
  const byteShare = percentShare(bytes, totalBytes);
  return [Math.max(fileShare, byteShare), byteShare, fileShare];
}

/**
 * @param {{allFiles: number, allBytes: number, unignoredFiles: number, unignoredBytes: number}} tally
 * @param {boolean} showIgnored
 * @param {ReturnType<typeof selectPopulation>} population
 * @param {{formatSize(value: number): string, formatFileCount(value: number): string}} formatters
 * @param {Intl.NumberFormat} percentFormatter
 * @param {Record<string, unknown>} identity
 */
function buildRow(tally, showIgnored, population, formatters, percentFormatter, identity) {
  if (!population) {
    throw new TypeError("rollup population is unavailable");
  }
  const files = showIgnored ? tally.allFiles : tally.unignoredFiles;
  const bytes = showIgnored ? tally.allBytes : tally.unignoredBytes;
  return Object.freeze({
    ...identity,
    files,
    bytes,
    filesText: formatters.formatFileCount(files),
    bytesText: formatters.formatSize(bytes),
    filePercent: formatPercent(files, population.files, percentFormatter),
    bytePercent: formatPercent(bytes, population.bytes, percentFormatter),
    fileShare: percentShare(files, population.files),
    byteShare: percentShare(bytes, population.bytes),
    score: dualScore(files, bytes, population.files, population.bytes),
  });
}

/** @param {ReadonlyArray<any>} rows */
function sortRows(rows) {
  return rows.slice().sort((left, right) => {
    if (left.rawKey === OTHER_KEY || right.rawKey === OTHER_KEY) {
      return Number(left.rawKey === OTHER_KEY) - Number(right.rawKey === OTHER_KEY);
    }
    for (let index = 0; index < 3; index += 1) {
      if (left.score[index] !== right.score[index]) {
        return right.score[index] - left.score[index];
      }
    }
    return left.key.localeCompare(right.key);
  });
}

/**
 * @param {ReturnType<typeof normalizeRollupEnvelope> | null} envelope
 * @param {boolean} showIgnored
 * @param {{formatSize(value: number): string, formatInteger(value: number): string, formatFileCount(value: number): string}} formatters
 * @param {MetabrowserPublicFileTypeTaxonomyRuntime | ((key: string) => "docs" | "code" | "data" | "other")} [fileTypes]
 */
export function buildFileTypeSummaryModel(envelope, showIgnored, formatters, fileTypes) {
  if (!envelope?.totals) {
    const failed = envelope?.indexStatus === "failed";
    const unavailable = envelope?.indexStatus === "done" || envelope?.indexStatus === "truncated";
    return Object.freeze({
      state: /** @type {"pending" | "failed" | "unavailable"} */ (
        failed ? "failed" : unavailable ? "unavailable" : "pending"
      ),
      rows: [],
      files: 0,
      bytes: 0,
      scanning: envelope?.indexStatus === "scanning",
      indexFailed: failed,
    });
  }
  const population = selectPopulation(envelope, showIgnored);
  if (!population) {
    throw new TypeError("rollup population is unavailable");
  }
  const percentFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
  const runtime = typeof fileTypes === "object" && fileTypes ? fileTypes : null;
  const legacyClassifier = typeof fileTypes === "function" ? fileTypes : () => "other";
  const familyDescriptors = new Map(runtime?.families.map((family) => [family.id, family]) ?? []);

  const familyRows = envelope.families.map((tally) => {
    const descriptor = familyDescriptors.get(tally.id);
    const category = descriptor?.category ?? "other";
    const paletteKey = `family:${tally.id}`;
    const children = sortRows(
      tally.extensions
        .map((child) =>
          buildRow(child, showIgnored, population, formatters, percentFormatter, {
            key: `${paletteKey}/${child.key}`,
            rawKey: child.key,
            extension: child.key,
            label: child.label,
            category,
            kind: "extension",
            child: true,
            paletteKey,
          }),
        )
        .filter((row) => row.files !== 0 || row.bytes !== 0),
    );
    return Object.freeze({
      ...buildRow(tally, showIgnored, population, formatters, percentFormatter, {
        key: paletteKey,
        rawKey: null,
        extension: null,
        label: descriptor?.label ?? tally.id,
        category,
        kind: "family",
        child: false,
        paletteKey,
      }),
      children,
      disclosable: children.length >= 2,
    });
  });
  const rawRows = envelope.tallies.map((tally) => {
    const category = runtime ? runtime.categoryForFile("", tally.key) : legacyClassifier(tally.key);
    return buildRow(tally, showIgnored, population, formatters, percentFormatter, {
      key: tally.key,
      rawKey: tally.key,
      extension: tally.key.startsWith(".") ? tally.key : null,
      label: tally.label,
      category,
      kind: "extension",
      child: false,
      paletteKey: tally.key,
    });
  });
  const rows = sortRows([...familyRows, ...rawRows]).filter(
    (row) => row.files !== 0 || row.bytes !== 0,
  );

  const base = {
    rows,
    files: population.files,
    bytes: population.bytes,
    filesText: formatters.formatFileCount(population.files),
    allFilesText: formatters.formatFileCount(population.allFiles),
    bytesText: formatters.formatSize(population.bytes),
    ignoredFiles: population.ignoredFiles,
    ignoredBytes: population.ignoredBytes,
    ignoredFilesText: formatters.formatFileCount(population.ignoredFiles),
    ignoredBytesText: formatters.formatSize(population.ignoredBytes),
    ignoredFilePercent: formatPercent(
      population.ignoredFiles,
      population.allFiles,
      percentFormatter,
    ),
    ignoredBytePercent: formatPercent(
      population.ignoredBytes,
      population.allBytes,
      percentFormatter,
    ),
    ignoredFileShare: percentShare(population.ignoredFiles, population.allFiles),
    ignoredByteShare: percentShare(population.ignoredBytes, population.allBytes),
    showIgnored,
    scanning: envelope.indexStatus === "scanning",
    indexFailed: envelope.indexStatus === "failed",
    indexedFiles: envelope.indexedFiles,
    maxFiles: envelope.maxFiles,
  };
  if (population.files === 0) {
    if (!showIgnored && population.allFiles > 0) {
      return Object.freeze({ ...base, state: /** @type {const} */ ("ignored-only") });
    }
    return Object.freeze({ ...base, state: /** @type {const} */ ("empty") });
  }
  if (envelope.truncated) {
    return Object.freeze({ ...base, state: /** @type {const} */ ("truncated") });
  }
  if (population.bytes === 0) {
    return Object.freeze({ ...base, state: /** @type {const} */ ("zero-bytes") });
  }
  return Object.freeze({ ...base, state: /** @type {const} */ ("populated") });
}
