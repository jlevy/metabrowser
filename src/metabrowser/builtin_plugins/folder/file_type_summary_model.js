export const NO_EXTENSION_KEY = "(none)";
export const OTHER_KEY = "";

/** @param {unknown} raw @param {string} label */
function normalizePopulationMetrics(raw, label) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new TypeError(`${label} metrics must be an object`);
  }
  const value = /** @type {Record<string, unknown>} */ (raw);
  /** @param {unknown} candidate @param {string} population */
  const measure = (candidate, population) => {
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
      throw new TypeError(`${label} ${population} measure must be an object`);
    }
    const item = /** @type {Record<string, unknown>} */ (candidate);
    if (
      !Number.isInteger(item.files) ||
      /** @type {number} */ (item.files) < 0 ||
      !Number.isInteger(item.bytes) ||
      /** @type {number} */ (item.bytes) < 0
    ) {
      throw new TypeError(`${label} ${population} measure must contain nonnegative integers`);
    }
    return {
      files: /** @type {number} */ (item.files),
      bytes: /** @type {number} */ (item.bytes),
    };
  };
  const all = measure(value.all, "all");
  const unignored = measure(value.unignored, "unignored");
  if (unignored.files > all.files || unignored.bytes > all.bytes) {
    throw new TypeError(`${label} unignored metrics cannot exceed all metrics`);
  }
  return Object.freeze({
    allFiles: all.files,
    allBytes: all.bytes,
    unignoredFiles: unignored.files,
    unignoredBytes: unignored.bytes,
  });
}

/** @param {unknown} raw */
function normalizeBreakdown(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new TypeError("file-type breakdown must be an object");
  }
  const value = /** @type {Record<string, unknown>} */ (raw);
  if (value.schema !== "file-type-breakdown-v1") {
    throw new TypeError("unsupported file-type breakdown schema");
  }
  const registry =
    value.registry && typeof value.registry === "object" && !Array.isArray(value.registry)
      ? /** @type {Record<string, unknown>} */ (value.registry)
      : null;
  if (
    registry?.schema_version !== 1 ||
    !Number.isInteger(registry.revision) ||
    typeof registry.fingerprint !== "string"
  ) {
    throw new TypeError("file-type breakdown has invalid registry identity");
  }
  if (!Array.isArray(value.groups)) {
    throw new TypeError("file-type breakdown groups must be an array");
  }
  const groups = value.groups.map((rawGroup) => {
    const group = /** @type {Record<string, unknown>} */ (rawGroup);
    if (!group || typeof group.id !== "string" || !Array.isArray(group.families)) {
      throw new TypeError("file-type breakdown group is invalid");
    }
    return Object.freeze({
      id: group.id,
      families: Object.freeze(
        group.families.map((rawFamily) => {
          const family = /** @type {Record<string, unknown>} */ (rawFamily);
          if (!family || typeof family.id !== "string" || !Array.isArray(family.extensions)) {
            throw new TypeError("file-type breakdown family is invalid");
          }
          return Object.freeze({
            id: family.id,
            ...normalizePopulationMetrics(family.metrics, `family ${family.id}`),
            extensions: Object.freeze(
              family.extensions.map((rawExtension) => {
                const extension = /** @type {Record<string, unknown>} */ (rawExtension);
                if (!extension || typeof extension.extension !== "string") {
                  throw new TypeError("file-type breakdown extension is invalid");
                }
                return Object.freeze({
                  key: extension.extension,
                  label: extension.extension,
                  ...normalizePopulationMetrics(
                    extension.metrics,
                    `extension ${extension.extension}`,
                  ),
                });
              }),
            ),
          });
        }),
      ),
    });
  });

  /** @param {unknown} rawOthers @param {string} label */
  const normalizeOthers = (rawOthers, label) => {
    if (rawOthers === null) {
      return null;
    }
    if (!rawOthers || typeof rawOthers !== "object" || Array.isArray(rawOthers)) {
      throw new TypeError(`${label} Others row is invalid`);
    }
    const others = /** @type {Record<string, unknown>} */ (rawOthers);
    if (
      !Number.isInteger(others.omitted_distinct_values) ||
      /** @type {number} */ (others.omitted_distinct_values) < 1
    ) {
      throw new TypeError(`${label} Others row requires an omitted-value count`);
    }
    return Object.freeze({
      key: `${label}:others`,
      label: "Others",
      omittedDistinctValues: /** @type {number} */ (others.omitted_distinct_values),
      ...normalizePopulationMetrics(others.metrics, `${label} Others`),
    });
  };

  const noExtension = /** @type {Record<string, unknown>} */ (value.no_extension);
  const remainingTypes = /** @type {Record<string, unknown>} */ (value.remaining_types);
  if (!noExtension || !Array.isArray(noExtension.filenames)) {
    throw new TypeError("No extension breakdown is invalid");
  }
  if (!remainingTypes || !Array.isArray(remainingTypes.extensions)) {
    throw new TypeError("Remaining types breakdown is invalid");
  }
  return Object.freeze({
    registry: Object.freeze({
      schemaVersion: 1,
      revision: /** @type {number} */ (registry.revision),
      fingerprint: registry.fingerprint,
    }),
    totals: normalizePopulationMetrics(value.metrics, "breakdown root"),
    groups: Object.freeze(groups),
    noExtension: Object.freeze({
      ...normalizePopulationMetrics(noExtension.metrics, "No extension"),
      filenames: Object.freeze(
        noExtension.filenames.map((rawFilename) => {
          const filename = /** @type {Record<string, unknown>} */ (rawFilename);
          if (!filename || typeof filename.basename !== "string" || !filename.basename) {
            throw new TypeError("No extension filename is invalid");
          }
          return Object.freeze({
            key: filename.basename,
            label: filename.basename,
            ...normalizePopulationMetrics(filename.metrics, `filename ${filename.basename}`),
          });
        }),
      ),
      others: normalizeOthers(noExtension.others, "no-extension"),
    }),
    remainingTypes: Object.freeze({
      ...normalizePopulationMetrics(remainingTypes.metrics, "Remaining types"),
      extensions: Object.freeze(
        remainingTypes.extensions.map((rawExtension) => {
          const extension = /** @type {Record<string, unknown>} */ (rawExtension);
          if (!extension || typeof extension.extension !== "string") {
            throw new TypeError("Remaining types extension is invalid");
          }
          return Object.freeze({
            key: extension.extension,
            label: extension.extension,
            ...normalizePopulationMetrics(
              extension.metrics,
              `remaining extension ${extension.extension}`,
            ),
          });
        }),
      ),
      others: normalizeOthers(remainingTypes.others, "remaining-types"),
    }),
  });
}

/** @param {unknown} raw */
export function normalizeRollupEnvelope(raw) {
  if (!raw || typeof raw !== "object") {
    throw new TypeError("rollup envelope must be an object");
  }
  const value = /** @type {Record<string, unknown>} */ (raw);
  /** @param {unknown} candidate */
  const integer = (candidate) =>
    Number.isInteger(candidate) && /** @type {number} */ (candidate) >= 0
      ? /** @type {number} */ (candidate)
      : 0;
  const breakdown = value.file_type_breakdown
    ? normalizeBreakdown(value.file_type_breakdown)
    : null;
  return Object.freeze({
    path: typeof value.path === "string" ? value.path : "",
    indexStatus: typeof value.index_status === "string" ? value.index_status : "pending",
    indexedFiles: integer(value.indexed_files),
    maxFiles: integer(value.max_files),
    truncated: value.truncated === true,
    breakdown,
    registry: breakdown?.registry ?? null,
    groups: breakdown?.groups ?? Object.freeze([]),
    specialTypes: breakdown
      ? Object.freeze({
          noExtension: breakdown.noExtension,
          remainingTypes: breakdown.remainingTypes,
        })
      : null,
    totals: breakdown?.totals ?? null,
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

const VISIBLE_ROWS_PER_SUBSECTION = 10;

/** @param {ReadonlyArray<any>} rows @param {"files" | "size"} metric */
function sortRows(rows, metric) {
  const primary = metric === "files" ? "files" : "bytes";
  const secondary = metric === "files" ? "bytes" : "files";
  return [...rows].sort(
    (left, right) =>
      right[primary] - left[primary] ||
      right[secondary] - left[secondary] ||
      left.key.localeCompare(right.key),
  );
}

/**
 * @param {ReadonlyArray<any>} rows
 * @param {"files" | "size"} metric
 * @param {{key: string, category: string, child: boolean}} identity
 * @param {ReturnType<typeof selectPopulation>} population
 * @param {{formatSize(value: number): string, formatFileCount(value: number): string, formatInteger(value: number): string}} formatters
 * @param {Intl.NumberFormat} percentFormatter
 */
function boundedRows(rows, metric, identity, population, formatters, percentFormatter) {
  const sorted = sortRows(rows, metric);
  if (sorted.length <= VISIBLE_ROWS_PER_SUBSECTION || !population) {
    return Object.freeze(sorted);
  }
  const visible = sorted.slice(0, VISIBLE_ROWS_PER_SUBSECTION);
  const remainder = sorted.slice(VISIBLE_ROWS_PER_SUBSECTION);
  const files = remainder.reduce((total, row) => total + row.files, 0);
  const bytes = remainder.reduce((total, row) => total + row.bytes, 0);
  const tail = Object.freeze({
    key: identity.key,
    rawKey: null,
    extension: null,
    iconPath: null,
    label: `${formatters.formatInteger ? formatters.formatInteger(remainder.length) : remainder.length} more`,
    category: identity.category,
    kind: "tail",
    child: identity.child,
    paletteKey: "",
    files,
    bytes,
    filesText: formatters.formatFileCount(files),
    bytesText: formatters.formatSize(bytes),
    filePercent: formatPercent(files, population.files, percentFormatter),
    bytePercent: formatPercent(bytes, population.bytes, percentFormatter),
    fileShare: percentShare(files, population.files),
    byteShare: percentShare(bytes, population.bytes),
    score: dualScore(files, bytes, population.files, population.bytes),
    children: Object.freeze(remainder),
    disclosable: true,
  });
  return Object.freeze([...visible, tail]);
}

/**
 * @param {{allFiles: number, allBytes: number, unignoredFiles: number, unignoredBytes: number}} tally
 * @param {boolean} showIgnored
 * @param {ReturnType<typeof selectPopulation>} population
 * @param {{formatSize(value: number): string, formatFileCount(value: number): string}} formatters
 * @param {Intl.NumberFormat} percentFormatter
 * @param {{key: string, rawKey: string | null, extension: string | null, iconPath: string | null, label: string, category: string, kind: string, child: boolean, paletteKey: string}} identity
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

/**
 * @param {ReturnType<typeof normalizeRollupEnvelope>} envelope
 * @param {boolean} showIgnored
 * @param {ReturnType<typeof selectPopulation>} population
 * @param {{formatSize(value: number): string, formatInteger(value: number): string, formatFileCount(value: number): string}} formatters
 * @param {Intl.NumberFormat} percentFormatter
 * @param {MetabrowserPublicFileTypeTaxonomyRuntime} runtime
 * @param {"files" | "size"} metric
 */
function buildRegistryRows(
  envelope,
  showIgnored,
  population,
  formatters,
  percentFormatter,
  runtime,
  metric,
) {
  if (!population || !envelope.breakdown || !envelope.registry) {
    return [];
  }
  if (
    runtime.revision !== envelope.registry.revision ||
    runtime.fingerprint !== envelope.registry.fingerprint
  ) {
    throw new TypeError("file-type breakdown registry does not match the browser registry");
  }
  const rawGroups = new Map(envelope.groups.map((group) => [group.id, group]));
  const familyDescriptors = new Map(runtime.families.map((family) => [family.id, family]));
  const rows = [];
  for (const group of runtime.groups) {
    const rawGroup = rawGroups.get(group.id);
    if (!rawGroup) {
      continue;
    }
    for (const tally of rawGroup.families) {
      const descriptor = familyDescriptors.get(tally.id);
      if (!descriptor || (descriptor.groupId ?? descriptor.category) !== group.id) {
        throw new TypeError(`unknown file-type family in breakdown: ${tally.id}`);
      }
      const paletteKey = `family:${tally.id}`;
      const rawChildren = tally.extensions
        .map((child) =>
          buildRow(child, showIgnored, population, formatters, percentFormatter, {
            key: `${paletteKey}/${child.key}`,
            rawKey: child.key,
            extension: child.key,
            iconPath: `x${child.key}`,
            label: child.label,
            category: group.id,
            kind: "extension",
            child: true,
            paletteKey,
          }),
        )
        .filter((row) => row.files !== 0 || row.bytes !== 0);
      const children = boundedRows(
        rawChildren,
        metric,
        {
          key: `${paletteKey}/tail`,
          category: group.id,
          child: true,
        },
        population,
        formatters,
        percentFormatter,
      );
      rows.push(
        Object.freeze({
          ...buildRow(tally, showIgnored, population, formatters, percentFormatter, {
            key: paletteKey,
            rawKey: null,
            extension: null,
            iconPath: null,
            label: descriptor.label,
            category: group.id,
            kind: "family",
            child: false,
            paletteKey,
          }),
          children: Object.freeze(children),
          disclosable: children.length >= 1,
        }),
      );
    }
  }

  /**
   * @param {"no-extension" | "remaining-types"} id
   * @param {string} key
   * @param {string} label
   * @param {any} tally
   * @param {ReadonlyArray<any>} rawChildren
   * @param {"filename" | "extension"} childKind
   */
  const specialRow = (id, key, label, tally, rawChildren, childKind) => {
    const populatedChildren = rawChildren
      .map((child) => {
        const others = child.omittedDistinctValues > 0;
        const childLabel = others
          ? `${formatters.formatInteger(child.omittedDistinctValues)} more`
          : child.label;
        return buildRow(child, showIgnored, population, formatters, percentFormatter, {
          key: `${id}/${child.key}`,
          rawKey: child.key,
          extension: !others && childKind === "extension" ? child.key : null,
          iconPath:
            !others && childKind === "filename"
              ? child.key
              : !others && childKind === "extension"
                ? `x${child.key}`
                : "file",
          label: childLabel,
          category: "other",
          kind: others ? "others" : childKind,
          child: true,
          paletteKey: others ? "" : childKind === "extension" ? child.key : "",
        });
      })
      .filter((row) => row.files !== 0 || row.bytes !== 0);
    const children = boundedRows(
      populatedChildren,
      metric,
      { key: `${id}/tail`, category: "other", child: true },
      population,
      formatters,
      percentFormatter,
    );
    return Object.freeze({
      ...buildRow(tally, showIgnored, population, formatters, percentFormatter, {
        key,
        rawKey: key,
        extension: null,
        iconPath: null,
        label,
        category: "other",
        kind: "special",
        child: false,
        paletteKey: "",
      }),
      children: Object.freeze(children),
      disclosable: children.length >= 1,
    });
  };
  const noExtension = envelope.specialTypes?.noExtension;
  const remainingTypes = envelope.specialTypes?.remainingTypes;
  if (noExtension) {
    rows.push(
      specialRow(
        "no-extension",
        NO_EXTENSION_KEY,
        "No extension",
        noExtension,
        [...noExtension.filenames, ...(noExtension.others ? [noExtension.others] : [])],
        "filename",
      ),
    );
  }
  if (remainingTypes) {
    rows.push(
      specialRow(
        "remaining-types",
        OTHER_KEY,
        "Other types",
        remainingTypes,
        [...remainingTypes.extensions, ...(remainingTypes.others ? [remainingTypes.others] : [])],
        "extension",
      ),
    );
  }
  const populatedRows = rows.filter((row) => row.files !== 0 || row.bytes !== 0);
  const bounded = [];
  for (const group of runtime.groups) {
    bounded.push(
      ...boundedRows(
        populatedRows.filter((row) => row.category === group.id),
        metric,
        { key: `group:${group.id}/tail`, category: group.id, child: false },
        population,
        formatters,
        percentFormatter,
      ),
    );
  }
  return bounded;
}

/**
 * @param {ReturnType<typeof normalizeRollupEnvelope> | null} envelope
 * @param {boolean} showIgnored
 * @param {{formatSize(value: number): string, formatInteger(value: number): string, formatFileCount(value: number): string}} formatters
 * @param {MetabrowserPublicFileTypeTaxonomyRuntime} [fileTypes]
 * @param {"files" | "size"} [metric]
 */
export function buildFileTypeSummaryModel(
  envelope,
  showIgnored,
  formatters,
  fileTypes,
  metric = "size",
) {
  /** @type {"files" | "size"} */
  const selectedMetric = metric === "files" ? "files" : "size";
  if (envelope?.indexStatus === "scanning") {
    return Object.freeze({
      state: /** @type {const} */ ("pending"),
      metric: selectedMetric,
      rows: [],
      files: 0,
      bytes: 0,
      scanning: true,
      indexFailed: false,
    });
  }
  if (!envelope?.totals) {
    const failed = envelope?.indexStatus === "failed";
    const unavailable = envelope?.indexStatus === "done" || envelope?.indexStatus === "truncated";
    return Object.freeze({
      state: /** @type {"pending" | "failed" | "unavailable"} */ (
        failed ? "failed" : unavailable ? "unavailable" : "pending"
      ),
      metric: selectedMetric,
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
  if (!envelope.breakdown || !runtime) {
    throw new TypeError("file-type summary requires File Rollup Format data");
  }
  const rows = buildRegistryRows(
    envelope,
    showIgnored,
    population,
    formatters,
    percentFormatter,
    runtime,
    selectedMetric,
  );
  const groupDescriptors = Object.freeze(
    runtime.groups.map((group) => Object.freeze({ id: group.id, label: group.label })),
  );

  const base = {
    metric: selectedMetric,
    rows,
    groups: groupDescriptors,
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
