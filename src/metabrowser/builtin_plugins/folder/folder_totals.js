/** @typedef {{state: "pending" | "complete", totalFiles?: number, totalBytes?: number, unignoredFiles?: number, unignoredBytes?: number}} FolderTotals */
/** @typedef {{files: number, bytes: number, filesText: string, bytesText: string, fileShare: number, byteShare: number, filePercent: string, bytePercent: string}} FolderTotalsMetricRow */

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

/** @param {number} numerator @param {number} denominator */
function share(numerator, denominator) {
  return denominator === 0 ? 0 : (numerator / denominator) * 100;
}

/** @param {number} value */
function percentText(value) {
  if (value === 0) {
    return "0%";
  }
  return value < 0.1
    ? "<0.1%"
    : `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value)}%`;
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
  const ignoredFiles = Math.max(0, totalFiles - (totals.unignoredFiles ?? 0));
  const ignoredBytes = Math.max(0, totalBytes - (totals.unignoredBytes ?? 0));
  const ignoredFileShare = share(ignoredFiles, totalFiles);
  const ignoredByteShare = share(ignoredBytes, totalBytes);
  return Object.freeze({
    state: /** @type {const} */ ("complete"),
    total: Object.freeze({
      files: totalFiles,
      bytes: totalBytes,
      filesText: formatters.formatFileCount(totalFiles),
      bytesText: formatters.formatSize(totalBytes),
      fileShare: totalFiles > 0 ? 100 : 0,
      byteShare: totalBytes > 0 ? 100 : 0,
      filePercent: totalFiles > 0 ? "100%" : "0%",
      bytePercent: totalBytes > 0 ? "100%" : "0%",
    }),
    ignored: Object.freeze({
      files: ignoredFiles,
      bytes: ignoredBytes,
      filesText: formatters.formatFileCount(ignoredFiles),
      bytesText: formatters.formatSize(ignoredBytes),
      fileShare: ignoredFileShare,
      byteShare: ignoredByteShare,
      filePercent: percentText(ignoredFileShare),
      bytePercent: percentText(ignoredByteShare),
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
      share: row.byteShare,
      percent: row.bytePercent,
    });
  }
  return Object.freeze({
    value: row.files,
    text: row.filesText,
    share: row.fileShare,
    percent: row.filePercent,
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
  const fill = document.createElement("span");
  fill.className = "file-type-summary-fill mb-distribution-other";
  track.append(fill);
  const percent = document.createElement("span");
  percent.className = "file-type-summary-percent";
  contents.append(value, track, percent);
  cell.append(contents);
  return { cell, fill, percent, value };
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
  let totalRow = null;
  /** @type {ReturnType<typeof totalsRow> | null} */
  let ignoredRow = null;
  /** @type {HTMLTableCellElement | null} */
  let metricHeader = null;
  /** @type {FolderTotals} */
  let currentTotals = totals;
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
    totalRow = totalsRow("Total");
    ignoredRow = totalsRow("Ignored");
    body.append(totalRow.tr, ignoredRow.tr);
    table.append(columns, head, body);
    root.append(table);
  }

  /** @param {FolderTotalsMetricRow} row @param {ReturnType<typeof totalsRow>} handle */
  function updateRow(row, handle) {
    const selected = selectFolderTotalsMetric(row, currentMetric);
    const displayKind = currentMetric === "files" ? "count" : "size";
    handle.metric.cell.className = `file-type-summary-metric file-type-summary-metric-${currentMetric}`;
    handle.metric.value.className = `file-type-summary-value ${displayKind} ${
      currentMetric === "files" ? mb.countClass(selected.value) : mb.sizeClass(selected.value)
    }`.trim();
    handle.metric.value.textContent = selected.text;
    handle.metric.fill.style.width = `${selected.share}%`;
    handle.metric.percent.textContent = selected.percent;
  }

  function render() {
    const model = buildFolderTotalsModel(currentTotals, mb);
    if (model.state === "pending") {
      table = null;
      totalRow = null;
      ignoredRow = null;
      metricHeader = null;
      root.innerHTML =
        '<div class="folder-totals-loading mb-delayed-loading" aria-hidden="true"></div>' +
        '<span class="sr-only">Loading file totals…</span>';
      return;
    }
    ensureTable();
    if (!totalRow || !ignoredRow) {
      throw new TypeError("folder totals table failed to initialize");
    }
    if (metricHeader) {
      metricHeader.textContent = currentMetric === "size" ? "Bytes" : "Files";
    }
    updateRow(model.total, totalRow);
    updateRow(model.ignored, ignoredRow);
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

  render();
  return Object.freeze({ update, updateMetric });
}
