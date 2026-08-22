/** @param {HTMLElement} parent @param {string} className */
function element(parent, className) {
  const child = document.createElement("div");
  child.className = className;
  parent.append(child);
  return child;
}

let distributionViewSequence = 0;

/** @param {DistributionHandle} handle @param {string} key */
function controlledRowId(handle, key) {
  return `${handle.idPrefix}-${encodeURIComponent(key).replace(/%/g, "_")}`;
}

function createMetricCell() {
  const cell = document.createElement("td");
  const contents = document.createElement("div");
  contents.className = "file-type-summary-metric-content";
  const value = document.createElement("span");
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

/** @param {string} className @param {string} label */
function createGroupBody(className, label) {
  const body = document.createElement("tbody");
  body.className = className;
  const headingRow = document.createElement("tr");
  headingRow.className = "file-type-summary-group-row";
  const heading = document.createElement("th");
  heading.scope = "rowgroup";
  heading.colSpan = 2;
  heading.textContent = label;
  headingRow.append(heading);
  body.append(headingRow);
  return body;
}

/**
 * @param {HTMLElement} container
 * @param {SummaryModel} model
 * @param {Palette} palette
 * @param {MetricClasses} metricClasses
 * @param {FileTypeIconResolver} fileTypeIcon
 */
export function mountDistributionView(container, model, palette, metricClasses, fileTypeIcon) {
  const root = document.createElement("div");
  root.className = "file-type-summary";
  const body = element(root, "file-type-summary-body");
  const handle = {
    container,
    root,
    body,
    palette,
    metricClasses,
    fileTypeIcon,
    idPrefix: `file-type-summary-${++distributionViewSequence}`,
    /** @type {Map<string, SummaryRowHandle>} */
    rows: new Map(),
    /** @type {Map<string, SummaryGroupHandle>} */
    groups: new Map(),
    /** @type {Set<string>} */
    expandedFamilies: new Set(),
    /** @type {ReadonlyArray<SummaryRow>} */
    lastRows: [],
    /** @type {ReadonlyArray<SummaryGroup>} */
    lastGroupOrder: [],
    table: /** @type {HTMLTableElement | null} */ (null),
    metricHeader: /** @type {HTMLTableCellElement | null} */ (null),
    metric: /** @type {"files" | "size"} */ ("files"),
    status: /** @type {HTMLElement | null} */ (null),
    mode: "",
  };
  container.append(root);
  updateDistributionView(handle, model);
  return handle;
}

/** @param {DistributionHandle} handle @param {SummaryModel} model */
export function updateDistributionView(handle, model) {
  if (model.state === "pending") {
    resetBody(handle, "pending");
    const skeleton = element(handle.body, "file-type-summary-skeleton mb-delayed-loading");
    skeleton.append(document.createElement("span"), document.createElement("span"));
    const loading = document.createElement("span");
    loading.className = "sr-only";
    loading.textContent = "Loading file types…";
    skeleton.append(loading);
    return;
  }
  if (model.state === "failed") {
    resetBody(handle, "failed");
    const failure = element(handle.body, "file-type-summary-status");
    failure.setAttribute("role", "status");
    failure.textContent = "Indexing failed; no file summary is available.";
    return;
  }
  if (model.state === "unavailable") {
    resetBody(handle, "unavailable");
    const unavailable = element(handle.body, "file-type-summary-empty");
    unavailable.textContent = "This folder is not in the current file index.";
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
  handle.metric = model.metric === "size" ? "size" : "files";
  if (handle.metricHeader) {
    handle.metricHeader.textContent = handle.metric === "size" ? "Bytes" : "Files";
  }
  updateRows(handle, model.rows, model.groups || [], handle.metric);
  if (!handle.status) {
    return;
  }
  handle.status.hidden = false;
  handle.status.replaceChildren();
  handle.status.classList?.remove("file-type-summary-status-progress");
  if (model.state === "truncated") {
    handle.status.textContent = `Summary is partial: ${(model.indexedFiles ?? 0).toLocaleString()} files indexed at the ${(model.maxFiles ?? 0).toLocaleString()}-file cap.`;
  } else if (model.indexFailed) {
    handle.status.textContent =
      "Indexing failed; percentages cover files indexed before the failure.";
  } else if (model.scanning) {
    renderScanningProgress(handle.status, model.indexedFiles);
  } else if (model.state === "zero-bytes") {
    handle.status.textContent = "All included files are zero bytes.";
  } else {
    handle.status.hidden = true;
  }
}

/**
 * Show the crawl the way the nav panel already shows it, rather than as a
 * sentence about what the percentages mean. Progress is a spinner and a
 * count; a reader watching a bar fill does not need to be told the number
 * beside it is provisional.
 *
 * The classes are the nav's own `#index-progress` internals, so this is
 * that component and cannot drift from it. The count rule is the nav's
 * too: a literal "~0 files scanned" reads as a stuck scan, so a count
 * that has not arrived yet falls back to the bare label.
 *
 * @param {HTMLElement} status
 * @param {number | undefined} indexedFiles
 */
function renderScanningProgress(status, indexedFiles) {
  status.classList?.add("file-type-summary-status-progress");
  const spinner = document.createElement("span");
  spinner.className = "index-progress-spinner";
  spinner.setAttribute("aria-hidden", "true");
  const text = document.createElement("span");
  text.className = "index-progress-text";
  const files = typeof indexedFiles === "number" && indexedFiles > 0 ? indexedFiles : null;
  text.textContent = files === null ? "Scanning…" : `~${files.toLocaleString()} files scanned`;
  status.append(spinner, text);
}

/** @param {DistributionHandle} handle @param {string} mode */
function resetBody(handle, mode) {
  handle.mode = mode;
  handle.body.replaceChildren();
  handle.rows.clear();
  handle.groups.clear();
  handle.table = null;
  handle.metricHeader = null;
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
  for (const className of ["file-type-summary-type-column", ""]) {
    const column = document.createElement("col");
    column.className = className;
    columns.append(column);
  }
  const thead = document.createElement("thead");
  thead.className = "sr-only";
  const headerRow = document.createElement("tr");
  for (const label of ["Type", "Files"]) {
    const header = document.createElement("th");
    header.scope = "col";
    header.textContent = label;
    headerRow.append(header);
    if (label !== "Type") {
      handle.metricHeader = header;
    }
  }
  thead.append(headerRow);
  table.append(columns, thead);
  handle.body.append(table);
  handle.table = table;
  handle.status = element(handle.body, "file-type-summary-status");
  handle.status.setAttribute("role", "status");
}

/**
 * @param {HTMLElement} element
 * @param {"files" | "size"} metric
 * @param {number} value
 * @param {string} text
 * @param {MetricClasses} metricClasses
 */
function updateMetricValue(element, metric, value, text, metricClasses) {
  const baseClass = metric === "files" ? "count" : "size";
  const emphasisClass =
    metric === "files" ? metricClasses.countClass(value) : metricClasses.sizeClass(value);
  element.className = `file-type-summary-value ${baseClass} ${emphasisClass}`.trim();
  element.textContent = text;
}

/** @param {DistributionHandle} handle @param {string} groupId @param {string} label */
function ensureGroup(handle, groupId, label) {
  let group = handle.groups.get(groupId);
  if (group || !handle.table) {
    return group;
  }
  const body = createGroupBody("file-type-summary-group", label);
  body.dataset.category = groupId;
  group = { body };
  handle.groups.set(groupId, group);
  handle.table.append(body);
  return group;
}

/** @param {DistributionHandle} handle @param {ReadonlyArray<SummaryRow>} rows @param {ReadonlyArray<SummaryGroup>} groupOrder */
function updateRows(handle, rows, groupOrder, metric = "files") {
  if (!handle.table) {
    return;
  }
  handle.lastRows = rows;
  handle.lastGroupOrder = groupOrder;
  const liveKeys = new Set();
  const liveCategories = new Set();
  /** @type {Array<SummaryRow>} */
  const allRows = [];
  /** @param {ReadonlyArray<SummaryRow>} items */
  const collectRows = (items) => {
    for (const row of items) {
      allRows.push(row);
      collectRows(row.children || []);
    }
  };
  collectRows(rows);
  const liveFamilyKeys = new Set(allRows.filter((row) => row.disclosable).map((row) => row.key));
  for (const familyKey of handle.expandedFamilies) {
    if (!liveFamilyKeys.has(familyKey)) {
      handle.expandedFamilies.delete(familyKey);
    }
  }
  const orderedGroups = [
    ...groupOrder,
    ...rows
      .map((row) => row.category)
      .filter(
        (id, index, ids) =>
          !groupOrder.some((group) => group.id === id) && ids.indexOf(id) === index,
      )
      .map((id) => ({ id, label: id })),
  ];
  for (const descriptor of orderedGroups) {
    const category = descriptor.id;
    /** @param {ReadonlyArray<SummaryRow>} items @returns {Array<SummaryRow>} */
    const visibleRows = (items) =>
      items.flatMap((row) => [
        row,
        ...(row.disclosable && handle.expandedFamilies.has(row.key)
          ? visibleRows(row.children || [])
          : []),
      ]);
    const categoryRows = visibleRows(rows.filter((row) => row.category === category));
    if (categoryRows.length === 0) {
      continue;
    }
    liveCategories.add(category);
    const group = ensureGroup(handle, category, descriptor.label);
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
        const typeContent = document.createElement("span");
        typeContent.className = "file-type-summary-type-content";
        const icon = document.createElement("span");
        icon.setAttribute("aria-hidden", "true");
        const label = document.createElement("span");
        const disclosure = document.createElement("button");
        disclosure.type = "button";
        disclosure.className = "file-type-summary-disclosure section-disclosure-trigger";
        const disclosureLabel = document.createElement("span");
        disclosure.append(disclosureLabel);
        disclosure.addEventListener("click", () => {
          const key = disclosure.dataset.rowKey;
          if (key === undefined) {
            return;
          }
          if (handle.expandedFamilies.has(key)) {
            handle.expandedFamilies.delete(key);
          } else {
            handle.expandedFamilies.add(key);
          }
          updateRows(handle, handle.lastRows, handle.lastGroupOrder, handle.metric);
        });
        typeContent.append(icon, label, disclosure);
        type.append(typeContent);
        const metricCell = createMetricCell();
        tr.append(type, metricCell.cell);
        rowHandle = {
          tr,
          icon,
          label,
          disclosure,
          disclosureLabel,
          metricCell: metricCell.cell,
          metricValue: metricCell.value,
          metricFill: metricCell.fill,
          metricPercent: metricCell.percent,
        };
        handle.rows.set(row.key, rowHandle);
      }
      rowHandle.tr.id = controlledRowId(handle, row.key);
      rowHandle.tr.classList?.toggle("file-type-summary-child-row", row.child === true);
      const paletteKey = row.paletteKey ?? row.key;
      const extension = row.extension || (row.key.startsWith(".") ? row.key : null);
      const iconPath = row.iconPath || (extension ? `x${extension}` : "file");
      const showIcon = Boolean(extension) || row.kind === "filename";
      const fileIcon = showIcon ? handle.fileTypeIcon(iconPath) : { className: "", svg: "" };
      rowHandle.icon.hidden = !fileIcon.svg;
      rowHandle.icon.className = `file-identity-icon ${fileIcon.className}`.trim();
      rowHandle.icon.innerHTML = fileIcon.svg;
      rowHandle.label.textContent = row.label;
      rowHandle.disclosureLabel.textContent = row.label;
      const disclosable = row.disclosable === true;
      rowHandle.label.hidden = disclosable;
      rowHandle.disclosure.hidden = !disclosable;
      if (disclosable) {
        rowHandle.disclosure.dataset.rowKey = row.key;
      } else {
        delete rowHandle.disclosure.dataset.rowKey;
      }
      rowHandle.disclosure.setAttribute(
        "aria-expanded",
        String(disclosable && handle.expandedFamilies.has(row.key)),
      );
      if (disclosable) {
        rowHandle.disclosure.setAttribute(
          "aria-controls",
          (row.children || []).map((child) => controlledRowId(handle, child.key)).join(" "),
        );
      } else {
        rowHandle.disclosure.removeAttribute("aria-controls");
      }
      rowHandle.disclosure.setAttribute(
        "aria-label",
        `${handle.expandedFamilies.has(row.key) ? "Collapse" : "Expand"} ${row.label}`,
      );
      const normalizedMetric = metric === "size" ? "size" : "files";
      const isFiles = normalizedMetric === "files";
      rowHandle.metricCell.className = `file-type-summary-metric file-type-summary-metric-${normalizedMetric}`;
      updateMetricValue(
        rowHandle.metricValue,
        normalizedMetric,
        isFiles ? row.files : row.bytes,
        isFiles ? row.filesText : row.bytesText,
        handle.metricClasses,
      );
      rowHandle.metricFill.className = "file-type-summary-fill";
      // After the class assignment above, which would otherwise drop the
      // neutral class paint adds for a segment with no family behind it.
      handle.palette.paint(rowHandle.metricFill, paletteKey);
      rowHandle.metricFill.style.width = `${isFiles ? row.fileShare : row.byteShare}%`;
      rowHandle.metricPercent.textContent = isFiles ? row.filePercent : row.bytePercent;
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

/** @typedef {{id: string, label: string}} SummaryGroup */
/** @typedef {{key: string, rawKey?: string | null, extension?: string | null, iconPath?: string | null, label: string, category: string, kind?: string, child?: boolean, paletteKey?: string, disclosable?: boolean, children?: ReadonlyArray<SummaryRow>, files: number, bytes: number, filesText: string, bytesText: string, filePercent: string, bytePercent: string, fileShare: number, byteShare: number}} SummaryRow */
/** @typedef {{classFor: (key: string) => string, styleFor: (key: string) => string, paint: (element: HTMLElement, key: string) => void}} Palette */
/** @typedef {{countClass: (value: number) => string, sizeClass: (value: number) => string}} MetricClasses */
/** @typedef {(path: string) => {svg: string, className: string}} FileTypeIconResolver */
/** @typedef {{state: "pending" | "failed" | "unavailable" | "populated" | "empty" | "ignored-only" | "zero-bytes" | "truncated", metric?: "files" | "size", rows: ReadonlyArray<SummaryRow>, groups?: ReadonlyArray<SummaryGroup>, files?: number, bytes?: number, filesText?: string, allFilesText?: string, bytesText?: string, showIgnored?: boolean, ignoredFiles?: number, ignoredBytes?: number, ignoredFilesText?: string, ignoredBytesText?: string, ignoredFilePercent?: string, ignoredBytePercent?: string, ignoredFileShare?: number, ignoredByteShare?: number, scanning?: boolean, indexFailed?: boolean, indexedFiles?: number, maxFiles?: number}} SummaryModel */
/** @typedef {{body: HTMLTableSectionElement}} SummaryGroupHandle */
/** @typedef {{tr: HTMLTableRowElement, icon: HTMLElement, label: HTMLElement, disclosure: HTMLButtonElement, disclosureLabel: HTMLElement, metricCell: HTMLTableCellElement, metricValue: HTMLElement, metricFill: HTMLElement, metricPercent: HTMLElement}} SummaryRowHandle */
/** @typedef {{body: HTMLElement, container: HTMLElement, root: HTMLElement, palette: Palette, metricClasses: MetricClasses, fileTypeIcon: FileTypeIconResolver, idPrefix: string, rows: Map<string, SummaryRowHandle>, groups: Map<string, SummaryGroupHandle>, expandedFamilies: Set<string>, lastRows: ReadonlyArray<SummaryRow>, lastGroupOrder: ReadonlyArray<SummaryGroup>, table: HTMLTableElement | null, metricHeader: HTMLTableCellElement | null, metric: "files" | "size", status: HTMLElement | null, mode: string}} DistributionHandle */
