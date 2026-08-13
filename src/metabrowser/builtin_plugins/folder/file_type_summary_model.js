export const NO_EXTENSION_KEY = "(none)";
export const OTHER_KEY = "";

/**
 * Build a pure extension classifier from the shell's broad filter presets.
 * Compound logical extensions inherit the category of their final known
 * suffix, so `.d.ts` and `.min.js` stay with Code without duplicating the
 * catalog in the folder plugin.
 *
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
      const category = preset.id;
      const categorySuffixes = suffixes.get(category);
      for (const value of preset.values) {
        if (typeof value === "string" && value.startsWith(".")) {
          categorySuffixes?.push(value.toLowerCase());
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
    tallies: Array.isArray(value.ext_tallies) ? value.ext_tallies.map(normalizeTallyRow) : [],
  });
}

/** @param {ReturnType<typeof normalizeRollupEnvelope>} envelope @param {boolean} showIgnored */
export function selectPopulation(envelope, showIgnored) {
  if (!envelope.totals) {
    return null;
  }
  return Object.freeze({
    files: showIgnored ? envelope.totals.allFiles : envelope.totals.unignoredFiles,
    bytes: showIgnored ? envelope.totals.allBytes : envelope.totals.unignoredBytes,
    allFiles: envelope.totals.allFiles,
    hasIgnored: envelope.totals.allFiles !== envelope.totals.unignoredFiles,
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

/**
 * @param {ReturnType<typeof normalizeRollupEnvelope> | null} envelope
 * @param {boolean} showIgnored
 * @param {{formatSize(value: number): string, formatInteger(value: number): string, formatFileCount(value: number): string}} formatters
 * @param {(key: string) => "docs" | "code" | "data" | "other"} [classifyCategory]
 */
export function buildFileTypeSummaryModel(
  envelope,
  showIgnored,
  formatters,
  classifyCategory = () => "other",
) {
  if (!envelope?.totals) {
    return Object.freeze({ state: /** @type {const} */ ("pending"), rows: [], files: 0, bytes: 0 });
  }
  const population = selectPopulation(envelope, showIgnored);
  if (!population) {
    throw new TypeError("rollup population is unavailable");
  }
  const percentFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
  const rows = envelope.tallies
    .map((tally) => {
      const files = showIgnored ? tally.allFiles : tally.unignoredFiles;
      const bytes = showIgnored ? tally.allBytes : tally.unignoredBytes;
      return Object.freeze({
        key: tally.key,
        label: tally.label,
        category: classifyCategory(tally.key),
        files,
        bytes,
        filesText: formatters.formatFileCount(files),
        bytesText: formatters.formatSize(bytes),
        filePercent: formatPercent(files, population.files, percentFormatter),
        bytePercent: formatPercent(bytes, population.bytes, percentFormatter),
        fileShare: percentShare(files, population.files),
        byteShare: percentShare(bytes, population.bytes),
      });
    })
    .filter((row) => row.files !== 0 || row.bytes !== 0)
    .sort((left, right) => (left.key === OTHER_KEY ? 1 : right.key === OTHER_KEY ? -1 : 0));

  const base = {
    rows,
    files: population.files,
    bytes: population.bytes,
    filesText: formatters.formatFileCount(population.files),
    allFilesText: formatters.formatFileCount(population.allFiles),
    bytesText: formatters.formatSize(population.bytes),
    hasIgnored: population.hasIgnored,
    showIgnored,
    scanning: envelope.indexStatus !== "done" && envelope.indexStatus !== "complete",
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
