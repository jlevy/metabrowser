import { createDistributionLegend } from "./distribution-legend.js";

/** @param {HTMLElement} parent @param {string} className */
function element(parent, className) {
  const child = document.createElement("div");
  child.className = className;
  parent.append(child);
  return child;
}

let distributionViewSequence = 0;

/**
 * Make the section's status line a `.notice` of one severity, or plain muted text for
 * `null`. A line that says something is incomplete or failed is a notice; progress and a
 * neutral fact are not.
 *
 * @param {Element} status
 * @param {"warning" | "error" | null} severity
 */
export function setStatusNotice(status, severity) {
  status.classList?.toggle("notice", severity !== null);
  if (severity === null) {
    status.removeAttribute?.("data-severity");
  } else {
    status.setAttribute?.("data-severity", severity);
  }
}

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
  percent.className = "file-type-summary-percent data-num";
  contents.append(value, track, percent);
  cell.append(contents);
  return { cell, fill, percent, value };
}

/**
 * A group's rows under its heading. The heading names the category in the shared
 * category heading's type, led by the category's icon, `iconSvg`, when it has one
 * (docs/design-system.md, "File-Type Category Icons").
 * @param {string} className @param {string} label @param {string} iconSvg
 */
function createGroupBody(className, label, iconSvg) {
  const body = document.createElement("tbody");
  body.className = className;
  const headingRow = document.createElement("tr");
  headingRow.className = "file-type-summary-group-row";
  const heading = document.createElement("th");
  heading.scope = "rowgroup";
  // The table's resting label type (docs/design-system.md, "Data Tables").
  heading.className = "data-label";
  heading.colSpan = 2;
  // The icon's markup is the shell's own icon registry's, never the folder's data.
  heading.innerHTML = iconSvg;
  const name = document.createElement("span");
  name.textContent = label;
  heading.append(name);
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
 * @param {DistributionHover} hover The hover the legend shares with the population bars
 *   above it, which draw it, as the Details table's rows do while it is open.
 * @param {CategoryIconResolver} categoryIcon A category's icon, by the name a group gives.
 */
export function mountDistributionView(
  container,
  model,
  palette,
  metricClasses,
  fileTypeIcon,
  hover,
  categoryIcon,
) {
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
    categoryIcon,
    hover,
    // The legend, bound to the hover while the body shows one (distribution-legend.js).
    legendView: /** @type {DistributionLegend | null} */ (null),
    // The Details row's bar the hover marks, while Details is open (drawHover).
    /** @type {Array<HTMLElement>} */
    hovered: [],
    unsubscribeHover: () => {},
    idPrefix: `file-type-summary-${++distributionViewSequence}`,
    /** @type {Map<string, SummaryRowHandle>} */
    rows: new Map(),
    /** @type {Map<string, SummaryGroupHandle>} */
    groups: new Map(),
    /** @type {Set<string>} */
    expandedFamilies: new Set(),
    // Whether Details is open. Held on the handle rather than the body, so it
    // survives every repaint of this mount — a control change, a refresh, a
    // skeleton while a rescan runs — and starts closed on the next mount, like
    // every other default in the Overview, rather than becoming a preference.
    detailsExpanded: false,
    /** @type {ReadonlyArray<SummaryRow>} */
    lastRows: [],
    /** @type {ReadonlyArray<SummaryGroup>} */
    lastGroupOrder: [],
    table: /** @type {HTMLTableElement | null} */ (null),
    metricHeader: /** @type {HTMLTableCellElement | null} */ (null),
    caption: /** @type {HTMLElement | null} */ (null),
    detailsToggle: /** @type {HTMLButtonElement | null} */ (null),
    metric: /** @type {"files" | "size"} */ ("files"),
    status: /** @type {HTMLElement | null} */ (null),
    mode: "",
  };
  handle.unsubscribeHover = hover.subscribe(() => drawHover(handle));
  container.append(root);
  updateDistributionView(handle, model);
  return handle;
}

/**
 * Draw the hover on the Details table; the legend marks its own entry
 * (distribution-legend.js), and the bars draw the rest and the tooltip (folder-totals.js,
 * showHover). A hover from a legend entry, which names the family, marks the bar of the
 * family's own row, not its extensions' rows, which are its parts and other values; a
 * segment names one value and marks no row. Only while Details is open, so the marks on
 * the page are the ones a reader sees, and opening or closing Details draws it again
 * (applyDetailsState).
 *
 * @param {DistributionHandle} handle
 */
function drawHover(handle) {
  for (const marked of handle.hovered) {
    delete marked.dataset.hovered;
  }
  handle.hovered = [];
  const target = handle.hover.current();
  if (!target) {
    return;
  }
  const fill =
    handle.detailsExpanded && target.marks === "family"
      ? handle.rows.get(target.key)?.metricFill
      : undefined;
  if (fill) {
    fill.dataset.hovered = "";
    handle.hovered.push(fill);
  }
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
    setStatusNotice(failure, "error");
    failure.setAttribute("role", "alert");
    failure.textContent = "Could not scan this folder; no file summary is available.";
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
    return;
  }

  ensureDistributionBody(handle);
  handle.metric = model.metric === "size" ? "size" : "files";
  if (handle.metricHeader) {
    handle.metricHeader.textContent = handle.metric === "size" ? "Bytes" : "Files";
  }
  if (handle.caption) {
    handle.caption.textContent = model.caption ?? "";
  }
  // The tally row the legend's shares are of, Total while Show ignored is on and Files
  // while it is off: the row whose segment of a family gives an entry's tooltip.
  handle.legendView?.update(model.legend ?? [], model.showIgnored ? "all" : "files");
  // The rows are kept current while Details is closed. They are bounded — ten
  // to a group and the families someone opened — so opening Details has
  // nothing left to build and shows the numbers at once.
  updateRows(handle, model.rows, model.groups || [], handle.metric);
  if (!handle.status) {
    return;
  }
  handle.status.hidden = false;
  setStatusNotice(handle.status, null);
  if (model.scanning && model.state !== "truncated" && !model.indexFailed) {
    window.metabrowser.renderIndexProgress(
      handle.status,
      model.indexedFilesText ? `~${model.indexedFilesText} files scanned` : "Scanning…",
    );
    return;
  }
  handle.status.replaceChildren();
  handle.status.classList?.remove("index-progress");
  if (model.state === "truncated") {
    setStatusNotice(handle.status, "warning");
    handle.status.textContent = `Only the first ${model.maxFilesText ?? "0 files"} were scanned; percentages cover those files.`;
  } else if (model.indexFailed) {
    setStatusNotice(handle.status, "warning");
    handle.status.textContent =
      "Could not finish scanning this folder; percentages cover the files found before it stopped.";
  } else if (model.state === "zero-bytes") {
    handle.status.textContent = "All included files are zero bytes.";
  } else {
    handle.status.hidden = true;
  }
}

/** @param {DistributionHandle} handle @param {string} mode */
function resetBody(handle, mode) {
  // The legend leaves with the body: it lets go of the hover an entry under the pointer
  // holds, which a removed element never hears leave, and stops listening.
  handle.legendView?.dispose();
  handle.legendView = null;
  handle.mode = mode;
  handle.body.replaceChildren();
  handle.hovered = [];
  handle.rows.clear();
  handle.groups.clear();
  handle.table = null;
  handle.metricHeader = null;
  handle.caption = null;
  handle.detailsToggle = null;
  handle.status = null;
}

/**
 * Release what this view holds: its markup, its rows, and its disclosure state.
 * The handle is done after this; a later update would build an empty body.
 *
 * @param {DistributionHandle} handle
 */
export function disposeDistributionView(handle) {
  resetBody(handle, "disposed");
  handle.unsubscribeHover();
  handle.expandedFamilies.clear();
  handle.detailsExpanded = false;
  handle.lastRows = [];
  handle.lastGroupOrder = [];
  handle.root.remove();
}

/**
 * Open or close Details. The one transition of the compact summary: the
 * caption and legend above it never move, and the table inside keeps the
 * families someone opened in it. A legend entry under a pointer that has not
 * moved, as while a key opens Details, keeps its hover, so the row it names
 * is marked as it appears and unmarked as it goes.
 *
 * @param {DistributionHandle} handle
 */
export function toggleDetails(handle) {
  handle.detailsExpanded = !handle.detailsExpanded;
  applyDetailsState(handle);
}

/** @param {DistributionHandle} handle */
function applyDetailsState(handle) {
  if (!handle.detailsToggle || !handle.table) {
    return;
  }
  handle.detailsToggle.setAttribute("aria-expanded", String(handle.detailsExpanded));
  handle.table.hidden = !handle.detailsExpanded;
  drawHover(handle);
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

  // The compact summary: the largest types. The caption names the population
  // their shares are of, for the legend and the table alike, so it labels both.
  // It is for assistive technology only: on screen the population bars above
  // and the Show ignored checkbox already say which population that is, and a
  // line restating it was one more thing to read before the legend.
  const captionId = `${handle.idPrefix}-caption`;
  const share = element(handle.body, "file-type-summary-share");
  const caption = element(share, "file-type-summary-caption sr-only");
  caption.id = captionId;
  const legend = document.createElement("ul");
  legend.className = "file-type-summary-legend";
  legend.setAttribute("aria-labelledby", captionId);
  share.append(legend);
  handle.legendView = createDistributionLegend(legend, handle.palette, handle.hover);

  // Everything else, behind the same disclosure an "N more" row uses.
  const details = element(handle.body, "file-type-summary-details");
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className =
    "file-type-summary-disclosure section-disclosure-trigger file-type-summary-details-toggle disclosure-toggle";
  toggle.textContent = "Details";
  table.id = `${handle.idPrefix}-details`;
  table.setAttribute("aria-labelledby", captionId);
  toggle.setAttribute("aria-controls", table.id);
  toggle.addEventListener("click", () => toggleDetails(handle));
  details.append(toggle, table);

  handle.caption = caption;
  handle.detailsToggle = toggle;
  handle.table = table;
  applyDetailsState(handle);
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
  element.className = `file-type-summary-value data-num ${baseClass} ${emphasisClass}`.trim();
  element.textContent = text;
}

/** @param {DistributionHandle} handle @param {SummaryGroup} descriptor */
function ensureGroup(handle, descriptor) {
  const groupId = descriptor.id;
  let group = handle.groups.get(groupId);
  if (group || !handle.table) {
    return group;
  }
  const icon = descriptor.icon ? handle.categoryIcon(descriptor.icon) : "";
  const body = createGroupBody("file-type-summary-group", descriptor.label, icon);
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
    const group = ensureGroup(handle, descriptor);
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
        disclosure.className =
          "file-type-summary-disclosure section-disclosure-trigger disclosure-toggle";
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
      // Which rows carry an icon is the model's answer, given as a path.
      // It used to be inferred here from "does this row name an extension",
      // which put an icon on every extension and none on the family they
      // belong to — the inverse of what the rows mean.
      //
      // A row inside a family never carries one, whatever it names: the family
      // above it holds the single icon for all of its extensions. A top-level
      // row that names an extension still falls back to that extension, since
      // there is no family row above it to do the naming.
      const extension = row.extension || (row.key.startsWith(".") ? row.key : null);
      const iconPath = row.iconPath ?? (row.child === true || !extension ? null : `x${extension}`);
      const fileIcon = iconPath ? handle.fileTypeIcon(iconPath) : { className: "", svg: "" };
      // A family's icon takes the family's own colour, so the glyph, the bar
      // and the row all say the same thing about which family this is. The
      // class rides in the assignment rather than through classList, which is
      // the one write this element gets.
      const familyIcon = row.kind === "family";
      rowHandle.icon.hidden = !fileIcon.svg;
      rowHandle.icon.className = [
        "file-identity-icon",
        fileIcon.className,
        familyIcon ? "file-identity-icon-family" : "",
      ]
        .filter(Boolean)
        .join(" ");
      rowHandle.icon.innerHTML = fileIcon.svg;
      if (familyIcon) {
        handle.palette.paint(rowHandle.icon, paletteKey);
      }
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

/** @typedef {{id: string, label: string, icon?: string | null}} SummaryGroup */
/** @typedef {{key: string, label: string, paletteKey: string, kind: "family" | "other", value: number, percent: string, share: number}} SummaryLegendEntry */
/** @typedef {{key: string, rawKey?: string | null, extension?: string | null, iconPath?: string | null, label: string, category: string, kind?: string, child?: boolean, paletteKey?: string, disclosable?: boolean, children?: ReadonlyArray<SummaryRow>, files: number, bytes: number, filesText: string, bytesText: string, filePercent: string, bytePercent: string, fileShare: number, byteShare: number}} SummaryRow */
/** @typedef {{classFor: (key: string) => string, styleFor: (key: string) => string, paint: (element: HTMLElement, key: string) => void}} Palette */
/** @typedef {{countClass: (value: number) => string, sizeClass: (value: number) => string}} MetricClasses */
/** @typedef {(path: string) => {svg: string, className: string}} FileTypeIconResolver */
/** @typedef {(name: string) => string} CategoryIconResolver */
/** @typedef {{state: "pending" | "failed" | "unavailable" | "populated" | "empty" | "ignored-only" | "zero-bytes" | "truncated", metric?: "files" | "size", rows: ReadonlyArray<SummaryRow>, legend?: ReadonlyArray<SummaryLegendEntry>, groups?: ReadonlyArray<SummaryGroup>, caption?: string, files?: number, bytes?: number, filesText?: string, allFilesText?: string, bytesText?: string, showIgnored?: boolean, ignoredFiles?: number, ignoredBytes?: number, ignoredFilesText?: string, ignoredBytesText?: string, ignoredFilePercent?: string, ignoredBytePercent?: string, ignoredFileShare?: number, ignoredByteShare?: number, scanning?: boolean, indexFailed?: boolean, indexedFiles?: number, maxFiles?: number, indexedFilesText?: string, maxFilesText?: string}} SummaryModel */
/** @typedef {{body: HTMLTableSectionElement}} SummaryGroupHandle */
/** @typedef {{tr: HTMLTableRowElement, icon: HTMLElement, label: HTMLElement, disclosure: HTMLButtonElement, disclosureLabel: HTMLElement, metricCell: HTMLTableCellElement, metricValue: HTMLElement, metricFill: HTMLElement, metricPercent: HTMLElement}} SummaryRowHandle */
/** @typedef {import("./distribution-hover.js").DistributionHover} DistributionHover */
/** @typedef {import("./distribution-legend.js").DistributionLegend} DistributionLegend */
/** @typedef {{body: HTMLElement, container: HTMLElement, root: HTMLElement, palette: Palette, metricClasses: MetricClasses, fileTypeIcon: FileTypeIconResolver, categoryIcon: CategoryIconResolver, hover: DistributionHover, legendView: DistributionLegend | null, hovered: Array<HTMLElement>, unsubscribeHover: () => void, idPrefix: string, rows: Map<string, SummaryRowHandle>, groups: Map<string, SummaryGroupHandle>, expandedFamilies: Set<string>, lastRows: ReadonlyArray<SummaryRow>, lastGroupOrder: ReadonlyArray<SummaryGroup>, table: HTMLTableElement | null, metricHeader: HTMLTableCellElement | null, caption: HTMLElement | null, detailsToggle: HTMLButtonElement | null, detailsExpanded: boolean, metric: "files" | "size", status: HTMLElement | null, mode: string}} DistributionHandle */
