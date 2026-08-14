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

/** @param {"files" | "bytes"} metric */
function metricCell(metric) {
  const cell = document.createElement("td");
  cell.className = `file-type-summary-metric file-type-summary-metric-${metric}`;
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
  const files = metricCell("files");
  const bytes = metricCell("bytes");
  tr.append(heading, files.cell, bytes.cell);
  return { tr, files, bytes };
}

/** @param {HTMLElement} container @param {FolderTotals} totals @param {MetabrowserPublicSdk} mb */
export function mountFolderTotalsView(container, totals, mb) {
  const root = document.createElement("div");
  root.className = "folder-totals";
  container.append(root);
  /** @type {HTMLTableElement | null} */
  let table = null;
  /** @type {ReturnType<typeof totalsRow> | null} */
  let totalRow = null;
  /** @type {ReturnType<typeof totalsRow> | null} */
  let ignoredRow = null;

  function ensureTable() {
    if (table) {
      return;
    }
    root.replaceChildren();
    table = document.createElement("table");
    table.className = "file-type-summary-table folder-totals-table";
    const columns = document.createElement("colgroup");
    for (const className of ["file-type-summary-type-column", "", ""]) {
      const column = document.createElement("col");
      column.className = className;
      columns.append(column);
    }
    const head = document.createElement("thead");
    head.className = "sr-only";
    const headRow = document.createElement("tr");
    for (const label of ["Population", "Files", "Size"]) {
      const heading = document.createElement("th");
      heading.scope = "col";
      heading.textContent = label;
      headRow.append(heading);
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
    /** @param {"files" | "bytes"} metric @param {ReturnType<typeof metricCell>} values */
    function updateMetric(metric, values) {
      const number = metric === "files" ? row.files : row.bytes;
      values.value.className = `file-type-summary-value ${metric === "files" ? "count" : "size"} ${
        metric === "files" ? mb.countClass(number) : mb.sizeClass(number)
      }`.trim();
      values.value.textContent = metric === "files" ? row.filesText : row.bytesText;
      values.fill.style.width = `${metric === "files" ? row.fileShare : row.byteShare}%`;
      values.percent.textContent = metric === "files" ? row.filePercent : row.bytePercent;
    }
    updateMetric("files", handle.files);
    updateMetric("bytes", handle.bytes);
  }

  /** @param {FolderTotals} nextTotals */
  function update(nextTotals) {
    const model = buildFolderTotalsModel(nextTotals, mb);
    if (model.state === "pending") {
      table = null;
      totalRow = null;
      ignoredRow = null;
      root.innerHTML =
        '<div class="folder-totals-loading mb-delayed-loading" aria-hidden="true"></div>' +
        '<span class="sr-only">Loading file totals…</span>';
      return;
    }
    ensureTable();
    if (!totalRow || !ignoredRow) {
      throw new TypeError("folder totals table failed to initialize");
    }
    updateRow(model.total, totalRow);
    updateRow(model.ignored, ignoredRow);
  }

  update(totals);
  return Object.freeze({ update });
}

/** @param {unknown} raw */
function totalsFromFolderEnvelope(raw) {
  const envelope =
    raw && typeof raw === "object" ? /** @type {Record<string, unknown>} */ (raw) : {};
  return normalizeFolderTotals(envelope.dir);
}

/** @param {MetabrowserPublicSdk} mb */
export function createFileTotalsPanel(mb) {
  return Object.freeze({
    label: "File Totals",
    placement: /** @type {const} */ ("summary"),
    presentation: /** @type {const} */ ("surface"),
    collapsible: false,
    required: true,
    printable: false,
    /** @param {{path?: string, raw?: unknown}} context */
    resolve(context) {
      return Object.freeze({
        key: context.path || "",
        data: totalsFromFolderEnvelope(context.raw),
      });
    },
    /** @param {HTMLElement} container @param {{path?: string}} context @param {FolderTotals} data @param {{signal?: AbortSignal}} options */
    mount(container, context, data, options) {
      const view = mountFolderTotalsView(container, data, mb);
      const unsubscribe = mb.directoryTotals.subscribe(context.path || "", (next) => {
        const normalized = normalizeFolderTotals(next);
        if (normalized.state === "complete") {
          view.update(normalized);
        }
      });
      let disposed = false;
      const dispose = () => {
        if (disposed) {
          return;
        }
        disposed = true;
        unsubscribe();
        options.signal?.removeEventListener("abort", dispose);
      };
      options.signal?.addEventListener("abort", dispose, { once: true });
      return Object.freeze({
        dispose,
        /** @param {{path?: string, raw?: unknown}} nextContext */
        update(nextContext) {
          view.update(totalsFromFolderEnvelope(nextContext.raw));
        },
      });
    },
  });
}
