/** @typedef {{state: "pending" | "complete", totalFiles?: number, totalBytes?: number, unignoredFiles?: number, unignoredBytes?: number}} FolderTotals */
/** @typedef {{files: number, bytes: number, filesText: string, bytesText: string}} FolderTotalsMetricRow */
/** @typedef {{key: string, label: string, paletteKey: string, files: number, bytes: number, value: number, share: number}} FolderTotalsSegment */
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
  // A producer that knows its totals are provisional says so. The directory
  // totals store zero-fills the aggregates the walker has not finalized, so
  // re-deriving completeness from the numbers alone would read those
  // placeholders as a real "0 files" and state it with confidence.
  if (value.state === "pending") {
    return Object.freeze({ state: "pending" });
  }
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
 * Choose between the two sources of a folder's totals.
 *
 * They arrive from different places and neither is reliably first. The
 * directory totals store carries the walker's aggregate, applied
 * incrementally from the delta stream; the rollup carries a count of
 * everything indexed so far, fetched whole.
 *
 * While the index is still scanning, both are lower bounds that only grow,
 * and either can be the stale one — the store reports nothing for a root the
 * walker has not finalized, and the rollup lags its own refresh debounce. So
 * take whichever has seen more files, whole rather than field by field, which
 * keeps a still-pending update from replacing real numbers with a spinner.
 *
 * Once the index is settled that rule stops being safe, and this is the part
 * worth being careful about. Each source is a variable holding its last
 * value, so "larger" only means "fresher" while both keep refreshing. If one
 * stops — a store that missed a deletion in a churn burst, a rollup whose
 * debounce has gone quiet — the larger stale reading wins every subsequent
 * comparison and nothing can dislodge it. Observed in a browser: a folder
 * settled on 400,019 files and stayed there while the filesystem and the
 * server both said 400,000, surviving a reload.
 *
 * A settled rollup is authoritative, so prefer it outright. That keeps the
 * in-progress behavior the max rule exists for and removes its ability to
 * latch, because the state is a fact the server reports rather than one
 * inferred from which number is bigger.
 *
 * @param {FolderTotals | null} indexed totals from the directory totals store
 * @param {FolderTotals | null} rollup totals derived from a rollup projection
 * @param {boolean} rollupSettled whether the rollup reported a finished index
 * @returns {FolderTotals | null}
 */
export function chooseFolderTotals(indexed, rollup, rollupSettled) {
  if (!indexed || !rollup) {
    return indexed ?? rollup;
  }
  if (rollupSettled) {
    return rollup;
  }
  return (indexed.totalFiles ?? 0) >= (rollup.totalFiles ?? 0) ? indexed : rollup;
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
 * @param {boolean} includeIgnored
 * @returns {FolderTotalsComposition | null}
 */
export function buildFolderTotalsComposition(envelope, fileTypes, metric, includeIgnored) {
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
  const sortPopulation = includeIgnored ? "all" : "files";
  const groups = new Map(envelope.groups.map((group) => [group.id, group]));
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
  const orderedCandidates = fileTypes.groups.flatMap((group) =>
    candidates
      .filter((candidate) => candidate.groupId === group.id)
      .sort((left, right) => {
        const primaryDifference =
          populationValue(right.tally, selectedMetric, sortPopulation) -
          populationValue(left.tally, selectedMetric, sortPopulation);
        if (primaryDifference !== 0) {
          return primaryDifference;
        }
        const secondaryMetric = selectedMetric === "files" ? "size" : "files";
        return (
          populationValue(right.tally, secondaryMetric, sortPopulation) -
            populationValue(left.tally, secondaryMetric, sortPopulation) ||
          left.key.localeCompare(right.key)
        );
      }),
  );

  /** @param {"files" | "ignored"} population */
  const buildPopulation = (population) => {
    const value = populationValue(totals, selectedMetric, population);
    const populationFiles = populationValue(totals, "files", population);
    const populationBytes = populationValue(totals, "size", population);
    const allSegments = orderedCandidates.map((candidate) => {
      const files = populationValue(candidate.tally, "files", population);
      const bytes = populationValue(candidate.tally, "size", population);
      const segmentValue = selectedMetric === "files" ? files : bytes;
      return Object.freeze({
        key: candidate.key,
        label: candidate.label,
        paletteKey: candidate.paletteKey,
        files,
        bytes,
        value: segmentValue,
        share: value === 0 ? 0 : (segmentValue / value) * 100,
      });
    });
    const segmentFiles = allSegments.reduce((sum, segment) => sum + segment.files, 0);
    const segmentBytes = allSegments.reduce((sum, segment) => sum + segment.bytes, 0);
    if (segmentFiles !== populationFiles || segmentBytes !== populationBytes) {
      throw new TypeError(`${population} file-type segments do not conserve folder totals`);
    }
    const segments = allSegments.filter((segment) => segment.value > 0);
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
        const tooltip = `<strong>${mb.escapeHtml(segment.label)}</strong><br>${mb.formatFileCount(
          segment.files,
        )} · ${mb.formatSize(segment.bytes)}`;
        fill.addEventListener("mouseover", (event) => mb.tooltip.show(tooltip, event));
        fill.addEventListener("mousemove", (event) => mb.tooltip.move(event));
        fill.addEventListener("mouseout", () => mb.tooltip.hide());
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
    mb.tooltip.hide();
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

  function dispose() {
    mb.tooltip.hide();
    root.replaceChildren();
  }

  render();
  return Object.freeze({ dispose, update, updateComposition, updateMetric });
}
