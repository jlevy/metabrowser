/** @typedef {{state: "pending" | "complete", totalFiles?: number, totalBytes?: number, unignoredFiles?: number, unignoredBytes?: number}} FolderTotals */
/** @typedef {{files: number, bytes: number, filesText: string, bytesText: string}} FolderTotalsMetricRow */
/** @typedef {{key: string, label: string, paletteKey: string, value: number, share: number}} FolderTotalsSegment */
/** @typedef {{metric: "files" | "size", files: {value: number, segments: ReadonlyArray<FolderTotalsSegment>}, ignored: {value: number, segments: ReadonlyArray<FolderTotalsSegment>}}} FolderTotalsComposition */

/** @param {unknown} value */
const integer = (value) =>
  Number.isInteger(value) && /** @type {number} */ (value) >= 0
    ? /** @type {number} */ (value)
    : null;

/** @param {unknown} raw @returns {FolderTotals} */
export function normalizeFolderTotals(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return Object.freeze({ state: "pending" });
  }
  const value = /** @type {Record<string, unknown>} */ (raw);
  const totalFiles = integer(value.totalFiles ?? value.total_files);
  const totalBytes = integer(value.totalBytes ?? value.total_size);
  const unignoredFiles = integer(value.unignoredFiles ?? value.unignored_files);
  const unignoredBytes = integer(value.unignoredBytes ?? value.unignored_size);
  if (
    totalFiles === null ||
    totalBytes === null ||
    unignoredFiles === null ||
    unignoredBytes === null
  ) {
    return Object.freeze({ state: "pending" });
  }
  return Object.freeze({
    state: "complete",
    totalFiles,
    totalBytes,
    unignoredFiles: Math.min(totalFiles, unignoredFiles),
    unignoredBytes: Math.min(totalBytes, unignoredBytes),
  });
}

/**
 * @param {FolderTotals} totals
 * @param {{formatFileCount(value: number): string, formatSize(value: number): string}} formatters
 */
export function buildFolderTotalsModel(totals, formatters) {
  if (totals.state !== "complete") {
    return Object.freeze({ state: /** @type {const} */ ("pending") });
  }
  const totalFiles = totals.totalFiles ?? 0;
  const totalBytes = totals.totalBytes ?? 0;
  const unignoredFiles = totals.unignoredFiles ?? 0;
  const unignoredBytes = totals.unignoredBytes ?? 0;
  const ignoredFiles = Math.max(0, totalFiles - unignoredFiles);
  const ignoredBytes = Math.max(0, totalBytes - unignoredBytes);
  return Object.freeze({
    state: /** @type {const} */ ("complete"),
    files: Object.freeze({
      files: unignoredFiles,
      bytes: unignoredBytes,
      filesText: formatters.formatFileCount(unignoredFiles),
      bytesText: formatters.formatSize(unignoredBytes),
    }),
    ignored: Object.freeze({
      files: ignoredFiles,
      bytes: ignoredBytes,
      filesText: formatters.formatFileCount(ignoredFiles),
      bytesText: formatters.formatSize(ignoredBytes),
    }),
  });
}

/**
 * @param {FolderTotalsMetricRow} row
 * @param {"files" | "size"} metric
 */
export function selectFolderTotalsMetric(row, metric) {
  if (metric === "size") {
    return Object.freeze({
      value: row.bytes,
      text: row.bytesText,
    });
  }
  return Object.freeze({
    value: row.files,
    text: row.filesText,
  });
}

/** @param {{allFiles: number, allBytes: number, unignoredFiles: number, unignoredBytes: number}} tally @param {"files" | "size"} metric @param {"all" | "files" | "ignored"} population */
function populationValue(tally, metric, population) {
  const all = metric === "files" ? tally.allFiles : tally.allBytes;
  const unignored = metric === "files" ? tally.unignoredFiles : tally.unignoredBytes;
  if (population === "all") {
    return all;
  }
  return population === "files" ? unignored : Math.max(0, all - unignored);
}

/**
 * Build the two independently normalized compositions shown above File Breakdown.
 *
 * @param {ReturnType<import("./file_type_summary_model.js").normalizeRollupEnvelope> | null} envelope
 * @param {MetabrowserPublicFileTypeTaxonomyRuntime} fileTypes
 * @param {"files" | "size"} metric
 * @returns {FolderTotalsComposition | null}
 */
export function buildFolderTotalsComposition(envelope, fileTypes, metric) {
  if (!envelope?.registry || !envelope.totals || !fileTypes) {
    return null;
  }
  const totals = envelope.totals;
  if (
    envelope.registry.revision !== fileTypes.revision ||
    envelope.registry.fingerprint !== fileTypes.fingerprint
  ) {
    throw new TypeError("folder totals registry does not match the browser registry");
  }
  const selectedMetric = metric === "size" ? "size" : "files";
  const groups = new Map(envelope.groups.map((group) => [group.id, group]));
  const groupOrder = new Map(fileTypes.groups.map((group, index) => [group.id, index]));
  const families = new Map(fileTypes.families.map((family) => [family.id, family]));
  /** @type {Array<{key: string, label: string, paletteKey: string, groupId: string, tally: {allFiles: number, allBytes: number, unignoredFiles: number, unignoredBytes: number}}>} */
  const candidates = [];
  for (const group of fileTypes.groups) {
    const rawGroup = groups.get(group.id);
    if (!rawGroup) {
      continue;
    }
    for (const tally of rawGroup.families) {
      const family = families.get(tally.id);
      if (!family || (family.groupId ?? family.category) !== group.id) {
        throw new TypeError(`unknown file-type family in folder totals: ${tally.id}`);
      }
      candidates.push({
        key: `family:${tally.id}`,
        label: family.label,
        paletteKey: `family:${tally.id}`,
        groupId: group.id,
        tally,
      });
    }
  }
  if (envelope.specialTypes?.noExtension) {
    candidates.push({
      key: "(none)",
      label: "No extension",
      paletteKey: "",
      groupId: "other",
      tally: envelope.specialTypes.noExtension,
    });
  }
  if (envelope.specialTypes?.remainingTypes) {
    candidates.push({
      key: "",
      label: "Other types",
      paletteKey: "",
      groupId: "other",
      tally: envelope.specialTypes.remainingTypes,
    });
  }
  candidates.sort((left, right) => {
    const groupDifference =
      (groupOrder.get(left.groupId) ?? Number.MAX_SAFE_INTEGER) -
      (groupOrder.get(right.groupId) ?? Number.MAX_SAFE_INTEGER);
    if (groupDifference !== 0) {
      return groupDifference;
    }
    const primaryDifference =
      populationValue(right.tally, selectedMetric, "all") -
      populationValue(left.tally, selectedMetric, "all");
    if (primaryDifference !== 0) {
      return primaryDifference;
    }
    const secondaryMetric = selectedMetric === "files" ? "size" : "files";
    return (
      populationValue(right.tally, secondaryMetric, "all") -
        populationValue(left.tally, secondaryMetric, "all") || left.key.localeCompare(right.key)
    );
  });

  /** @param {"files" | "ignored"} population */
  const buildPopulation = (population) => {
    const value = populationValue(totals, selectedMetric, population);
    const segments = candidates
      .map((candidate) => {
        const segmentValue = populationValue(candidate.tally, selectedMetric, population);
        return Object.freeze({
          key: candidate.key,
          label: candidate.label,
          paletteKey: candidate.paletteKey,
          value: segmentValue,
          share: value === 0 ? 0 : (segmentValue / value) * 100,
        });
      })
      .filter((segment) => segment.value > 0);
    const segmentTotal = segments.reduce((sum, segment) => sum + segment.value, 0);
    if (segmentTotal !== value) {
      throw new TypeError(`${population} file-type segments do not conserve folder totals`);
    }
    return Object.freeze({ value, segments: Object.freeze(segments) });
  };

  return Object.freeze({
    metric: selectedMetric,
    files: buildPopulation("files"),
    ignored: buildPopulation("ignored"),
  });
}

function metricCell() {
  const cell = document.createElement("td");
  const contents = document.createElement("div");
  contents.className = "file-type-summary-metric-content";
  const value = document.createElement("span");
  const track = document.createElement("div");
  track.className = "file-type-summary-track";
  track.setAttribute("aria-hidden", "true");
  contents.append(value, track);
  cell.append(contents);
  return { cell, track, value };
}

/** @param {string} label */
function totalsRow(label) {
  const tr = document.createElement("tr");
  tr.className = `file-type-summary-${label.toLowerCase()}-row`;
  const heading = document.createElement("th");
  heading.scope = "row";
  heading.textContent = label;
  const metric = metricCell();
  tr.append(heading, metric.cell);
  return { tr, metric };
}

/** @param {HTMLElement} container @param {FolderTotals} totals @param {MetabrowserPublicSdk} mb @param {"files" | "size"} [initialMetric] */
export function mountFolderTotalsView(container, totals, mb, initialMetric = "files") {
  const root = document.createElement("div");
  root.className = "folder-totals";
  container.append(root);
  /** @type {HTMLTableElement | null} */
  let table = null;
  /** @type {ReturnType<typeof totalsRow> | null} */
  let filesRow = null;
  /** @type {ReturnType<typeof totalsRow> | null} */
  let ignoredRow = null;
  /** @type {HTMLTableCellElement | null} */
  let metricHeader = null;
  /** @type {FolderTotals} */
  let currentTotals = totals;
  /** @type {FolderTotalsComposition | null} */
  let currentComposition = null;
  /** @type {{classFor(key: string): string} | null} */
  let currentPalette = null;
  /** @type {"files" | "size"} */
  let currentMetric = initialMetric === "size" ? "size" : "files";

  function ensureTable() {
    if (table) {
      return;
    }
    root.replaceChildren();
    table = document.createElement("table");
    table.className = "file-type-summary-table folder-totals-table";
    const columns = document.createElement("colgroup");
    for (const className of ["file-type-summary-type-column", ""]) {
      const column = document.createElement("col");
      column.className = className;
      columns.append(column);
    }
    const head = document.createElement("thead");
    head.className = "sr-only";
    const headRow = document.createElement("tr");
    for (const label of ["Population", currentMetric === "size" ? "Bytes" : "Files"]) {
      const heading = document.createElement("th");
      heading.scope = "col";
      heading.textContent = label;
      headRow.append(heading);
      if (label !== "Population") {
        metricHeader = heading;
      }
    }
    head.append(headRow);
    const body = document.createElement("tbody");
    body.className = "file-type-summary-group file-type-summary-totals";
    filesRow = totalsRow("Files");
    ignoredRow = totalsRow("Ignored");
    body.append(filesRow.tr, ignoredRow.tr);
    table.append(columns, head, body);
    root.append(table);
  }

  /** @param {ReturnType<typeof totalsRow>} handle @param {"files" | "ignored"} population @param {number} value */
  function updateTrack(handle, population, value) {
    const projected =
      currentComposition?.metric === currentMetric ? currentComposition[population] : null;
    const segments = projected?.value === value ? projected.segments : null;
    if (value === 0) {
      handle.metric.track.replaceChildren();
      return;
    }
    if (!segments || !currentPalette) {
      const fill = document.createElement("span");
      fill.className = "file-type-summary-fill mb-distribution-other";
      fill.style.width = "100%";
      handle.metric.track.replaceChildren(fill);
      return;
    }
    const palette = currentPalette;
    handle.metric.track.replaceChildren(
      ...segments.map((segment) => {
        const fill = document.createElement("span");
        fill.className = `file-type-summary-fill ${palette.classFor(segment.paletteKey)}`;
        fill.dataset.segmentKey = segment.key;
        fill.style.width = `${segment.share}%`;
        return fill;
      }),
    );
  }

  /** @param {FolderTotalsMetricRow} row @param {ReturnType<typeof totalsRow>} handle @param {"files" | "ignored"} population */
  function updateRow(row, handle, population) {
    const selected = selectFolderTotalsMetric(row, currentMetric);
    const displayKind = currentMetric === "files" ? "count" : "size";
    handle.metric.cell.className = `file-type-summary-metric file-type-summary-metric-${currentMetric}`;
    handle.metric.value.className = `file-type-summary-value ${displayKind} ${
      currentMetric === "files" ? mb.countClass(selected.value) : mb.sizeClass(selected.value)
    }`.trim();
    handle.metric.value.textContent = selected.text;
    updateTrack(handle, population, selected.value);
  }

  function render() {
    const model = buildFolderTotalsModel(currentTotals, mb);
    if (model.state === "pending") {
      table = null;
      filesRow = null;
      ignoredRow = null;
      metricHeader = null;
      root.innerHTML =
        '<div class="folder-totals-loading mb-delayed-loading" aria-hidden="true"></div>' +
        '<span class="sr-only">Loading file totals…</span>';
      return;
    }
    ensureTable();
    if (!filesRow || !ignoredRow) {
      throw new TypeError("folder totals table failed to initialize");
    }
    if (metricHeader) {
      metricHeader.textContent = currentMetric === "size" ? "Bytes" : "Files";
    }
    updateRow(model.files, filesRow, "files");
    updateRow(model.ignored, ignoredRow, "ignored");
  }

  /** @param {FolderTotals} nextTotals */
  function update(nextTotals) {
    currentTotals = nextTotals;
    render();
  }

  /** @param {"files" | "size"} nextMetric */
  function updateMetric(nextMetric) {
    const normalized = nextMetric === "size" ? "size" : "files";
    if (normalized === currentMetric) {
      return;
    }
    currentMetric = normalized;
    render();
  }

  /** @param {FolderTotalsComposition | null} composition @param {{classFor(key: string): string} | null} palette */
  function updateComposition(composition, palette) {
    currentComposition = composition;
    currentPalette = palette;
    render();
  }

  render();
  return Object.freeze({ update, updateComposition, updateMetric });
}
