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

/** @param {"files" | "bytes"} metric */
function createMetricCell(metric) {
  const cell = document.createElement("td");
  cell.className = `file-type-summary-metric file-type-summary-metric-${metric}`;
  const contents = document.createElement("div");
  contents.className = "file-type-summary-metric-content";
  const value = document.createElement("span");
  value.className = `file-type-summary-value ${metric === "files" ? "count" : "size"}`;
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
function createMetricRow(className, label) {
  const tr = document.createElement("tr");
  tr.className = className;
  const rowLabel = document.createElement("th");
  rowLabel.scope = "row";
  rowLabel.textContent = label;
  const files = createMetricCell("files");
  const bytes = createMetricCell("bytes");
  tr.append(rowLabel, files.cell, bytes.cell);
  return {
    tr,
    label: rowLabel,
    fileValue: files.value,
    fileFill: files.fill,
    filePercent: files.percent,
    byteValue: bytes.value,
    byteFill: bytes.fill,
    bytePercent: bytes.percent,
  };
}

/** @param {string} className @param {string} label */
function createGroupBody(className, label) {
  const body = document.createElement("tbody");
  body.className = className;
  const headingRow = document.createElement("tr");
  headingRow.className = "file-type-summary-group-row";
  const heading = document.createElement("th");
  heading.scope = "rowgroup";
  heading.colSpan = 3;
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
    ignoredRow: /** @type {SummaryMetricRowHandle | null} */ (null),
    totalRow: /** @type {SummaryTotalHandle | null} */ (null),
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
    const skeleton = element(handle.body, "file-type-summary-skeleton");
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
  updateRows(handle, model.rows, model.groups || []);
  updateTotalRows(handle, model);
  if (!handle.status) {
    return;
  }
  handle.status.hidden = false;
  handle.status.textContent = "";
  if (model.state === "truncated") {
    handle.status.textContent = `Summary is partial: ${(model.indexedFiles ?? 0).toLocaleString()} files indexed at the ${(model.maxFiles ?? 0).toLocaleString()}-file cap.`;
  } else if (model.indexFailed) {
    handle.status.textContent =
      "Indexing failed; percentages cover files indexed before the failure.";
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
  handle.ignoredRow = null;
  handle.totalRow = null;
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
  thead.className = "sr-only";
  const headerRow = document.createElement("tr");
  for (const label of ["Type", "Files", "Size"]) {
    const header = document.createElement("th");
    header.scope = "col";
    header.textContent = label;
    headerRow.append(header);
  }
  thead.append(headerRow);
  table.append(columns, thead);
  const totalsBody = createGroupBody("file-type-summary-group file-type-summary-totals", "Totals");
  const total = createMetricRow("file-type-summary-total-row", "Total");
  const ignored = createMetricRow("file-type-summary-ignored-row", "Ignored");
  totalsBody.append(total.tr, ignored.tr);
  table.append(totalsBody);
  handle.body.append(table);
  handle.table = table;
  handle.ignoredRow = ignored;
  handle.totalRow = {
    body: totalsBody,
    ...total,
  };
  handle.status = element(handle.body, "file-type-summary-status");
  handle.status.setAttribute("role", "status");
}

/** @param {DistributionHandle} handle @param {SummaryModel} model */
function updateTotalRows(handle, model) {
  const ignored = handle.ignoredRow;
  const total = handle.totalRow;
  if (!ignored || !total || !handle.table) {
    return;
  }
  const ignoredVisible = model.showIgnored === true && (model.ignoredFiles ?? 0) > 0;
  ignored.tr.hidden = !ignoredVisible;
  updateMetricValue(
    ignored.fileValue,
    "files",
    model.ignoredFiles ?? 0,
    model.ignoredFilesText ?? "0 files",
    handle.metricClasses,
  );
  ignored.fileFill.className = "file-type-summary-fill mb-distribution-other";
  ignored.fileFill.style.width = `${model.ignoredFileShare ?? 0}%`;
  ignored.filePercent.textContent = model.ignoredFilePercent ?? "0%";
  updateMetricValue(
    ignored.byteValue,
    "bytes",
    model.ignoredBytes ?? 0,
    model.ignoredBytesText ?? "0 B",
    handle.metricClasses,
  );
  ignored.byteFill.className = "file-type-summary-fill mb-distribution-other";
  ignored.byteFill.style.width = `${model.ignoredByteShare ?? 0}%`;
  ignored.bytePercent.textContent = model.ignoredBytePercent ?? "0%";
  const filesPopulated = (model.files ?? 0) > 0;
  const bytesPopulated = (model.bytes ?? 0) > 0;
  updateMetricValue(
    total.fileValue,
    "files",
    model.files ?? 0,
    model.filesText ?? "0 files",
    handle.metricClasses,
  );
  total.fileFill.className = "file-type-summary-fill mb-distribution-other";
  total.fileFill.style.width = filesPopulated ? "100%" : "0%";
  total.filePercent.textContent = filesPopulated ? "100%" : "0%";
  updateMetricValue(
    total.byteValue,
    "bytes",
    model.bytes ?? 0,
    model.bytesText ?? "0 B",
    handle.metricClasses,
  );
  total.byteFill.className = "file-type-summary-fill mb-distribution-other";
  total.byteFill.style.width = bytesPopulated ? "100%" : "0%";
  total.bytePercent.textContent = bytesPopulated ? "100%" : "0%";
}

/**
 * @param {HTMLElement} element
 * @param {"files" | "bytes"} metric
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
function updateRows(handle, rows, groupOrder) {
  if (!handle.table) {
    return;
  }
  handle.lastRows = rows;
  handle.lastGroupOrder = groupOrder;
  const liveKeys = new Set();
  const liveCategories = new Set();
  const liveFamilyKeys = new Set(rows.filter((row) => row.disclosable).map((row) => row.key));
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
    const categoryRows = rows
      .filter((row) => row.category === category)
      .flatMap((row) => [
        row,
        ...(row.disclosable && handle.expandedFamilies.has(row.key) ? row.children || [] : []),
      ]);
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
          updateRows(handle, handle.lastRows, handle.lastGroupOrder);
        });
        typeContent.append(icon, label, disclosure);
        type.append(typeContent);
        const files = createMetricCell("files");
        const bytes = createMetricCell("bytes");
        tr.append(type, files.cell, bytes.cell);
        rowHandle = {
          tr,
          icon,
          label,
          disclosure,
          disclosureLabel,
          fileValue: files.value,
          fileFill: files.fill,
          filePercent: files.percent,
          byteValue: bytes.value,
          byteFill: bytes.fill,
          bytePercent: bytes.percent,
        };
        handle.rows.set(row.key, rowHandle);
      }
      rowHandle.tr.id = controlledRowId(handle, row.key);
      rowHandle.tr.classList?.toggle("file-type-summary-child-row", row.child === true);
      const colorClass = handle.palette.classFor(row.paletteKey ?? row.key);
      const extension = row.extension || (row.key.startsWith(".") ? row.key : null);
      const iconPath = row.iconPath || (extension ? `x${extension}` : "file");
      const fileIcon = handle.fileTypeIcon(iconPath);
      const showIcon = row.kind !== "family";
      rowHandle.icon.hidden = !showIcon || !fileIcon.svg;
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
      updateMetricValue(
        rowHandle.fileValue,
        "files",
        row.files,
        row.filesText,
        handle.metricClasses,
      );
      rowHandle.fileFill.className = `file-type-summary-fill ${colorClass}`;
      rowHandle.fileFill.style.width = `${row.fileShare}%`;
      rowHandle.filePercent.textContent = row.filePercent;
      updateMetricValue(
        rowHandle.byteValue,
        "bytes",
        row.bytes,
        row.bytesText,
        handle.metricClasses,
      );
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

/** @typedef {{id: string, label: string}} SummaryGroup */
/** @typedef {{key: string, rawKey?: string | null, extension?: string | null, iconPath?: string | null, label: string, category: string, kind?: string, child?: boolean, paletteKey?: string, disclosable?: boolean, children?: ReadonlyArray<SummaryRow>, files: number, bytes: number, filesText: string, bytesText: string, filePercent: string, bytePercent: string, fileShare: number, byteShare: number}} SummaryRow */
/** @typedef {{classFor: (key: string) => string}} Palette */
/** @typedef {{countClass: (value: number) => string, sizeClass: (value: number) => string}} MetricClasses */
/** @typedef {(path: string) => {svg: string, className: string}} FileTypeIconResolver */
/** @typedef {{state: "pending" | "failed" | "unavailable" | "populated" | "empty" | "ignored-only" | "zero-bytes" | "truncated", rows: ReadonlyArray<SummaryRow>, groups?: ReadonlyArray<SummaryGroup>, files?: number, bytes?: number, filesText?: string, allFilesText?: string, bytesText?: string, showIgnored?: boolean, ignoredFiles?: number, ignoredBytes?: number, ignoredFilesText?: string, ignoredBytesText?: string, ignoredFilePercent?: string, ignoredBytePercent?: string, ignoredFileShare?: number, ignoredByteShare?: number, scanning?: boolean, indexFailed?: boolean, indexedFiles?: number, maxFiles?: number}} SummaryModel */
/** @typedef {{body: HTMLTableSectionElement}} SummaryGroupHandle */
/** @typedef {{tr: HTMLTableRowElement, icon: HTMLElement, label: HTMLElement, disclosure: HTMLButtonElement, disclosureLabel: HTMLElement, fileValue: HTMLElement, fileFill: HTMLElement, filePercent: HTMLElement, byteValue: HTMLElement, byteFill: HTMLElement, bytePercent: HTMLElement}} SummaryRowHandle */
/** @typedef {{tr: HTMLTableRowElement, label: HTMLElement, fileValue: HTMLElement, fileFill: HTMLElement, filePercent: HTMLElement, byteValue: HTMLElement, byteFill: HTMLElement, bytePercent: HTMLElement}} SummaryMetricRowHandle */
/** @typedef {SummaryMetricRowHandle & {body: HTMLTableSectionElement}} SummaryTotalHandle */
/** @typedef {{body: HTMLElement, container: HTMLElement, root: HTMLElement, palette: Palette, metricClasses: MetricClasses, fileTypeIcon: FileTypeIconResolver, idPrefix: string, rows: Map<string, SummaryRowHandle>, groups: Map<string, SummaryGroupHandle>, expandedFamilies: Set<string>, lastRows: ReadonlyArray<SummaryRow>, lastGroupOrder: ReadonlyArray<SummaryGroup>, table: HTMLTableElement | null, ignoredRow: SummaryMetricRowHandle | null, totalRow: SummaryTotalHandle | null, status: HTMLElement | null, mode: string}} DistributionHandle */
