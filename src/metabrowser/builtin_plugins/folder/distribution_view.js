/** @param {HTMLElement} parent @param {string} className */
function element(parent, className) {
  const child = document.createElement("div");
  child.className = className;
  parent.append(child);
  return child;
}

/** @param {"files" | "bytes"} metric */
function createMetricCell(metric) {
  const cell = document.createElement("td");
  cell.className = `file-type-summary-metric file-type-summary-metric-${metric}`;
  const contents = document.createElement("div");
  contents.className = "file-type-summary-metric-content";
  const value = document.createElement("span");
  value.className = "file-type-summary-value";
  const track = document.createElement("div");
  track.className = "file-type-summary-track";
  track.setAttribute("aria-hidden", "true");
  const fill = document.createElement("span");
  fill.className = "file-type-summary-fill";
  track.append(fill);
  const percent = document.createElement("span");
  percent.className = "file-type-summary-percent";
  contents.append(value, track, percent);
  cell.append(contents);
  return { cell, fill, percent, value };
}

/** @param {HTMLElement} container @param {SummaryModel} model @param {Palette} palette */
export function mountDistributionView(container, model, palette) {
  const root = document.createElement("div");
  root.className = "file-type-summary";
  const meta = element(root, "file-type-summary-meta");
  const scope = document.createElement("span");
  scope.className = "file-type-summary-scope";
  const total = document.createElement("span");
  total.className = "file-type-summary-total";
  meta.append(scope, total);
  const body = element(root, "file-type-summary-body");
  const handle = {
    container,
    root,
    meta,
    scope,
    total,
    body,
    palette,
    /** @type {Map<string, SummaryRowHandle>} */
    rows: new Map(),
    /** @type {Map<FileTypeCategory, SummaryGroupHandle>} */
    groups: new Map(),
    table: /** @type {HTMLTableElement | null} */ (null),
    status: /** @type {HTMLElement | null} */ (null),
    mode: "",
  };
  container.append(root);
  updateDistributionView(handle, model);
  return handle;
}

/** @param {DistributionHandle} handle @param {SummaryModel} model */
export function updateDistributionView(handle, model) {
  handle.total.textContent = `${"filesText" in model ? model.filesText : "0 files"} · ${"bytesText" in model ? model.bytesText : "0 B"}`;
  handle.scope.textContent =
    "hasIgnored" in model && model.hasIgnored
      ? model.showIgnored
        ? "Including ignored"
        : "Ignored excluded"
      : "";
  if (model.state === "pending") {
    resetBody(handle, "pending");
    const skeleton = element(handle.body, "file-type-summary-skeleton");
    skeleton.append(document.createElement("span"), document.createElement("span"));
    const loading = document.createElement("span");
    loading.className = "sr-only";
    loading.textContent = "Loading file types…";
    skeleton.append(loading);
    return;
  }
  if (model.state === "empty") {
    resetBody(handle, "empty");
    const empty = element(handle.body, "file-type-summary-empty");
    empty.textContent = "No files to summarize.";
    return;
  }
  if (model.state === "ignored-only") {
    resetBody(handle, "ignored-only");
    const empty = element(handle.body, "file-type-summary-empty");
    empty.textContent = `No included files. Show ignored to include ${model.allFilesText || "these files"}.`;
    return;
  }

  ensureDistributionBody(handle);
  updateRows(handle, model.rows);
  if (!handle.status) {
    return;
  }
  handle.status.hidden = false;
  handle.status.textContent = "";
  if (model.state === "truncated") {
    handle.status.textContent = `Summary is partial: ${(model.indexedFiles ?? 0).toLocaleString()} files indexed at the ${(model.maxFiles ?? 0).toLocaleString()}-file cap.`;
  } else if (model.scanning) {
    handle.status.textContent = "Scanning… percentages cover files indexed so far.";
  } else if (model.state === "zero-bytes") {
    handle.status.textContent = "All included files are zero bytes.";
  } else {
    handle.status.hidden = true;
  }
}

/** @param {DistributionHandle} handle @param {string} mode */
function resetBody(handle, mode) {
  handle.mode = mode;
  handle.body.replaceChildren();
  handle.rows.clear();
  handle.groups.clear();
  handle.table = null;
  handle.status = null;
}

/** @param {DistributionHandle} handle */
function ensureDistributionBody(handle) {
  if (handle.mode === "distribution") {
    return;
  }
  resetBody(handle, "distribution");
  const table = document.createElement("table");
  table.className = "file-type-summary-table";
  const columns = document.createElement("colgroup");
  for (const className of ["file-type-summary-type-column", "", ""]) {
    const column = document.createElement("col");
    column.className = className;
    columns.append(column);
  }
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const label of ["Type", "Files", "Size"]) {
    const header = document.createElement("th");
    header.scope = "col";
    header.textContent = label;
    headerRow.append(header);
  }
  thead.append(headerRow);
  table.append(columns, thead);
  handle.body.append(table);
  handle.table = table;
  handle.status = element(handle.body, "file-type-summary-status");
  handle.status.setAttribute("role", "status");
}

/** @param {DistributionHandle} handle @param {FileTypeCategory} category */
function ensureGroup(handle, category) {
  let group = handle.groups.get(category);
  if (group || !handle.table) {
    return group;
  }
  const body = document.createElement("tbody");
  body.className = "file-type-summary-group";
  body.dataset.category = category;
  const headingRow = document.createElement("tr");
  headingRow.className = "file-type-summary-group-row";
  const heading = document.createElement("th");
  heading.scope = "rowgroup";
  heading.colSpan = 3;
  heading.textContent = category === "code" ? "Code" : category === "data" ? "Data" : "Other";
  headingRow.append(heading);
  body.append(headingRow);
  group = { body };
  handle.groups.set(category, group);
  handle.table.append(body);
  return group;
}

/** @param {DistributionHandle} handle @param {ReadonlyArray<SummaryRow>} rows */
function updateRows(handle, rows) {
  if (!handle.table) {
    return;
  }
  const liveKeys = new Set();
  const liveCategories = new Set();
  for (const category of /** @type {const} */ (["code", "data", "other"])) {
    const categoryRows = rows.filter((row) => row.category === category);
    if (categoryRows.length === 0) {
      continue;
    }
    liveCategories.add(category);
    const group = ensureGroup(handle, category);
    if (!group) {
      continue;
    }
    handle.table.append(group.body);
    for (const row of categoryRows) {
      liveKeys.add(row.key);
      let rowHandle = handle.rows.get(row.key);
      if (!rowHandle) {
        const tr = document.createElement("tr");
        tr.dataset.typeKey = row.key;
        const type = document.createElement("th");
        type.scope = "row";
        type.className = "file-type-summary-type";
        const label = document.createElement("span");
        type.append(label);
        const files = createMetricCell("files");
        const bytes = createMetricCell("bytes");
        bytes.value.className += " size";
        tr.append(type, files.cell, bytes.cell);
        rowHandle = {
          tr,
          label,
          fileValue: files.value,
          fileFill: files.fill,
          filePercent: files.percent,
          byteValue: bytes.value,
          byteFill: bytes.fill,
          bytePercent: bytes.percent,
        };
        handle.rows.set(row.key, rowHandle);
      }
      const colorClass = handle.palette.classFor(row.key);
      rowHandle.label.textContent = row.label;
      rowHandle.fileValue.textContent = row.filesText;
      rowHandle.fileFill.className = `file-type-summary-fill ${colorClass}`;
      rowHandle.fileFill.style.width = `${row.fileShare}%`;
      rowHandle.filePercent.textContent = row.filePercent;
      rowHandle.byteValue.textContent = row.bytesText;
      rowHandle.byteFill.className = `file-type-summary-fill ${colorClass}`;
      rowHandle.byteFill.style.width = `${row.byteShare}%`;
      rowHandle.bytePercent.textContent = row.bytePercent;
      group.body.append(rowHandle.tr);
    }
  }
  for (const [key, rowHandle] of handle.rows) {
    if (!liveKeys.has(key)) {
      rowHandle.tr.remove();
      handle.rows.delete(key);
    }
  }
  for (const [category, group] of handle.groups) {
    if (!liveCategories.has(category)) {
      group.body.remove();
      handle.groups.delete(category);
    }
  }
}

/** @typedef {"code" | "data" | "other"} FileTypeCategory */
/** @typedef {{key: string, label: string, category: FileTypeCategory, files: number, bytes: number, filesText: string, bytesText: string, filePercent: string, bytePercent: string, fileShare: number, byteShare: number}} SummaryRow */
/** @typedef {{classFor: (key: string) => string}} Palette */
/** @typedef {{state: "pending" | "populated" | "empty" | "ignored-only" | "zero-bytes" | "truncated", rows: ReadonlyArray<SummaryRow>, filesText?: string, allFilesText?: string, bytesText?: string, hasIgnored?: boolean, showIgnored?: boolean, scanning?: boolean, indexedFiles?: number, maxFiles?: number}} SummaryModel */
/** @typedef {{body: HTMLTableSectionElement}} SummaryGroupHandle */
/** @typedef {{tr: HTMLTableRowElement, label: HTMLElement, fileValue: HTMLElement, fileFill: HTMLElement, filePercent: HTMLElement, byteValue: HTMLElement, byteFill: HTMLElement, bytePercent: HTMLElement}} SummaryRowHandle */
/** @typedef {{body: HTMLElement, container: HTMLElement, root: HTMLElement, meta: HTMLElement, scope: HTMLElement, total: HTMLElement, palette: Palette, rows: Map<string, SummaryRowHandle>, groups: Map<FileTypeCategory, SummaryGroupHandle>, table: HTMLTableElement | null, status: HTMLElement | null, mode: string}} DistributionHandle */
