/** @param {HTMLElement} parent @param {string} className */
function element(parent, className) {
  const child = document.createElement("div");
  child.className = className;
  parent.append(child);
  return child;
}

/** @param {"files" | "bytes"} metric @param {ReadonlyArray<SummaryRow>} rows @param {Palette} palette */
export function renderDistributionBar(metric, rows, palette) {
  const figure = document.createElement("figure");
  figure.className = "file-type-distribution";
  const label = document.createElement("figcaption");
  label.textContent = metric === "files" ? "Files" : "Size";
  const track = document.createElement("div");
  track.className = "file-type-distribution-track";
  track.setAttribute(
    "aria-label",
    `${label.textContent} distribution. Exact values are in the File types table.`,
  );
  for (const row of rows) {
    if (row[metric] <= 0) {
      continue;
    }
    const segment = document.createElement("span");
    segment.className = `file-type-distribution-segment ${palette.classFor(row.key)}`;
    segment.dataset.typeKey = row.key;
    segment.style.flexGrow = String(row[metric]);
    segment.setAttribute("aria-hidden", "true");
    track.append(segment);
  }
  figure.append(label, track);
  return figure;
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
    /** @type {Map<"files" | "bytes", DistributionBarHandle>} */
    bars: new Map(),
    tableBody: /** @type {HTMLTableSectionElement | null} */ (null),
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
  updateDistributionBar(handle.bars.get("files"), "files", model.rows, handle.palette);
  updateDistributionBar(handle.bars.get("bytes"), "bytes", model.rows, handle.palette);
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
  handle.bars.clear();
  handle.tableBody = null;
  handle.status = null;
}

/** @param {DistributionHandle} handle */
function ensureDistributionBody(handle) {
  if (handle.mode === "distribution") {
    return;
  }
  resetBody(handle, "distribution");
  const bars = element(handle.body, "file-type-summary-bars");
  for (const metric of /** @type {const} */ (["files", "bytes"])) {
    const figure = renderDistributionBar(metric, [], handle.palette);
    const track = /** @type {HTMLElement} */ (
      figure.querySelector(".file-type-distribution-track")
    );
    bars.append(figure);
    handle.bars.set(metric, { figure, track, segments: new Map() });
  }
  const table = document.createElement("table");
  table.className = "file-type-summary-table";
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const label of ["Type", "Files", "Size"]) {
    const header = document.createElement("th");
    header.scope = "col";
    header.textContent = label;
    headerRow.append(header);
  }
  thead.append(headerRow);
  const tbody = document.createElement("tbody");
  table.append(thead, tbody);
  handle.body.append(table);
  handle.tableBody = tbody;
  handle.status = element(handle.body, "file-type-summary-status");
  handle.status.setAttribute("role", "status");
}

/** @param {DistributionBarHandle | undefined} bar @param {"files" | "bytes"} metric @param {ReadonlyArray<SummaryRow>} rows @param {Palette} palette */
function updateDistributionBar(bar, metric, rows, palette) {
  if (!bar) {
    return;
  }
  const liveKeys = new Set();
  for (const row of rows) {
    if (row[metric] <= 0) {
      continue;
    }
    liveKeys.add(row.key);
    let segment = bar.segments.get(row.key);
    if (!segment) {
      segment = document.createElement("span");
      segment.dataset.typeKey = row.key;
      segment.setAttribute("aria-hidden", "true");
      bar.segments.set(row.key, segment);
    }
    segment.className = `file-type-distribution-segment ${palette.classFor(row.key)}`;
    segment.style.flexGrow = String(row[metric]);
    bar.track.append(segment);
  }
  for (const [key, segment] of bar.segments) {
    if (!liveKeys.has(key)) {
      segment.remove();
      bar.segments.delete(key);
    }
  }
}

/** @param {DistributionHandle} handle @param {ReadonlyArray<SummaryRow>} rows */
function updateRows(handle, rows) {
  if (!handle.tableBody) {
    return;
  }
  const liveKeys = new Set();
  for (const row of rows) {
    liveKeys.add(row.key);
    let rowHandle = handle.rows.get(row.key);
    if (!rowHandle) {
      const tr = document.createElement("tr");
      tr.dataset.typeKey = row.key;
      const type = document.createElement("th");
      type.scope = "row";
      const mark = document.createElement("span");
      mark.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      type.append(mark, label);
      const files = document.createElement("td");
      const fileValue = document.createElement("span");
      const filePercent = document.createElement("span");
      filePercent.className = "file-type-summary-percent";
      files.append(fileValue, document.createTextNode(" "), filePercent);
      const bytes = document.createElement("td");
      const byteValue = document.createElement("span");
      byteValue.className = "size";
      const bytePercent = document.createElement("span");
      bytePercent.className = "file-type-summary-percent";
      bytes.append(byteValue, document.createTextNode(" "), bytePercent);
      tr.append(type, files, bytes);
      rowHandle = { tr, mark, label, fileValue, filePercent, byteValue, bytePercent };
      handle.rows.set(row.key, rowHandle);
    }
    rowHandle.mark.className = `file-type-summary-mark ${handle.palette.classFor(row.key)}`;
    rowHandle.label.textContent = row.label;
    rowHandle.fileValue.textContent = row.filesText;
    rowHandle.filePercent.textContent = `(${row.filePercent})`;
    rowHandle.byteValue.textContent = row.bytesText;
    rowHandle.bytePercent.textContent = `(${row.bytePercent})`;
    handle.tableBody.append(rowHandle.tr);
  }
  for (const [key, rowHandle] of handle.rows) {
    if (!liveKeys.has(key)) {
      rowHandle.tr.remove();
      handle.rows.delete(key);
    }
  }
}

/** @typedef {{key: string, label: string, files: number, bytes: number, filesText: string, bytesText: string, filePercent: string, bytePercent: string}} SummaryRow */
/** @typedef {{classFor: (key: string) => string}} Palette */
/** @typedef {{state: "pending" | "populated" | "empty" | "ignored-only" | "zero-bytes" | "truncated", rows: ReadonlyArray<SummaryRow>, filesText?: string, allFilesText?: string, bytesText?: string, hasIgnored?: boolean, showIgnored?: boolean, scanning?: boolean, indexedFiles?: number, maxFiles?: number}} SummaryModel */
/** @typedef {{figure: HTMLElement, track: HTMLElement, segments: Map<string, HTMLElement>}} DistributionBarHandle */
/** @typedef {{tr: HTMLTableRowElement, mark: HTMLElement, label: HTMLElement, fileValue: HTMLElement, filePercent: HTMLElement, byteValue: HTMLElement, bytePercent: HTMLElement}} SummaryRowHandle */
/** @typedef {{body: HTMLElement, container: HTMLElement, root: HTMLElement, meta: HTMLElement, scope: HTMLElement, total: HTMLElement, palette: Palette, rows: Map<string, SummaryRowHandle>, bars: Map<"files" | "bytes", DistributionBarHandle>, tableBody: HTMLTableSectionElement | null, status: HTMLElement | null, mode: string}} DistributionHandle */
