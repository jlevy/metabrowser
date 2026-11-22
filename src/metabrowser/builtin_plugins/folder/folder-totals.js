/** @typedef {import("./distribution-hover.js").DistributionHover} DistributionHover */
/** @typedef {import("./distribution-hover.js").DistributionHoverTarget} DistributionHoverTarget */
/**
 * A segment on screen and its two tooltips: `tooltip`, which names the family, for the
 * segment itself, and `counts`, its file count and byte size alone, for a legend entry
 * that shows the name.
 *
 * @typedef {{fill: HTMLElement, tooltip: string, counts: string}} DrawnSegment
 */
/** @typedef {{state: "pending" | "complete", totalFiles?: number, totalBytes?: number, unignoredFiles?: number, unignoredBytes?: number}} FolderTotals */
/** @typedef {{files: number, bytes: number, filesText: string, bytesText: string}} FolderTotalsMetricRow */
/** @typedef {{key: string, label: string, paletteKey: string, files: number, bytes: number, value: number, share: number}} FolderTotalsSegment */
/** @typedef {{value: number, segments: ReadonlyArray<FolderTotalsSegment>}} FolderTotalsPopulation */
/** @typedef {{metric: "files" | "size", all: FolderTotalsPopulation, files: FolderTotalsPopulation, ignored: FolderTotalsPopulation}} FolderTotalsComposition */

/** Why a folder the inventory leaves out has no totals, by the envelope's `dir.not_indexed`. */
const NOT_INDEXED_STATEMENTS = Object.freeze({
  hidden: "Metabrowser does not index hidden folders, so this one has no file totals.",
  symlink:
    "Metabrowser does not follow symbolic links when it indexes, so this folder has no file totals here.",
});

/**
 * @param {unknown} raw The folder envelope.
 * @returns {string | null}
 */
export function notIndexedStatement(raw) {
  const dir = /** @type {{dir?: {not_indexed?: "hidden" | "symlink"}} | null | undefined} */ (raw)
    ?.dir;
  return dir?.not_indexed ? NOT_INDEXED_STATEMENTS[dir.not_indexed] : null;
}

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
    // The union of the two rows above. It is what the type distribution
    // below counts against whenever Show ignored is on, so without it on
    // screen none of the distribution's percentages corresponds to any track
    // a reader can see: each disjoint row normalizes to its own population,
    // and the shares only add up across both.
    all: Object.freeze({
      files: totalFiles,
      bytes: totalBytes,
      filesText: formatters.formatFileCount(totalFiles),
      bytesText: formatters.formatSize(totalBytes),
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
 * The rows are Files (the unignored population), Ignored, and Total, their sum; the first
 * two are disjoint, and each treats its own population as 100%. Total is shown although
 * it is derivable because the type distribution below counts against the whole folder
 * while Show ignored is on, and then only Total's track matches its percentages.
 * Segments follow the registry's group order and then descend by the selected measure
 * within a group, sorted on the combined population, the one basis all three rows share
 * and the one Show ignored cannot move, so the tracks stay comparable column by column.
 * This takes no Show ignored flag: the tallies are fixed populations, and the checkbox
 * changes only what the distribution counts. Until a terminal projection arrives, a
 * nonzero population is one neutral fill; a projection that does not conserve the current
 * tally leaves it neutral, and a zero population has no fill.
 *
 * @param {ReturnType<import("./file-type-summary-model.js").normalizeRollupEnvelope> | null} envelope
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
  // Show ignored is not a parameter here, deliberately.
  //
  // These three rows are fixed populations — the unignored files, the ignored
  // files, and their union — so nothing the checkbox selects can move them.
  // It used to decide the shared segment order, which meant toggling it
  // silently reordered every track, the Ignored row included, whose contents
  // the checkbox has nothing to do with. Taking the argument away makes the
  // invariant structural instead of merely true today: the top table cannot
  // respond to Show ignored, only the distribution below it can.
  //
  // The order comes from the union, the one basis the three rows share, so a
  // reader can compare them column by column.
  const sortPopulation = "all";
  const groups = new Map(envelope.groups.map((group) => [group.id, group]));
  const families = new Map(fileTypes.families.map((family) => [family.id, family]));
  /** @type {Array<{key: string, label: string, paletteKey: string, groupId: string, tally: {allFiles: number, allBytes: number, unignoredFiles: number, unignoredBytes: number}}>} */
  const candidates = [];
  for (const group of fileTypes.displayGroups) {
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
  const orderedCandidates = fileTypes.displayGroups.flatMap((group) =>
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

  /** @param {"all" | "files" | "ignored"} population */
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
    all: buildPopulation("all"),
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

/**
 * @param {HTMLElement} container
 * @param {FolderTotals} totals
 * @param {MetabrowserPublicSdk} mb
 * @param {"files" | "size"} initialMetric
 * @param {DistributionHover} hover The hover these bars share with the legend that names
 *   their segments and the marks beside them: File Overview's Details table, or the
 *   Treemap's cells.
 */
export function mountFolderTotalsView(container, totals, mb, initialMetric, hover) {
  const root = document.createElement("div");
  root.className = "folder-totals";
  container.append(root);
  // The segments on screen, by row and then by key, with each one's tooltip: what the
  // hover is drawn on. Replaced whole on every draw, as the segments are.
  /** @type {Map<"all" | "files" | "ignored", Map<string, DrawnSegment>>} */
  const segmentsDrawn = new Map();
  /** @type {Array<HTMLElement>} */
  let hoveredFills = [];
  // What the tooltip this hover showed is anchored on, so a change puts that one away
  // and no other surface's.
  /** @type {Element | null} */
  let tooltipOn = null;
  /** @type {HTMLTableElement | null} */
  let table = null;
  /** @type {ReturnType<typeof totalsRow> | null} */
  let filesRow = null;
  /** @type {ReturnType<typeof totalsRow> | null} */
  let ignoredRow = null;
  /** @type {ReturnType<typeof totalsRow> | null} */
  let allRow = null;
  /** @type {HTMLTableCellElement | null} */
  let metricHeader = null;
  /** @type {FolderTotals} */
  let currentTotals = totals;
  /** @type {FolderTotalsComposition | null} */
  let currentComposition = null;
  /** @type {{classFor(key: string): string, paint(element: HTMLElement, key: string): void} | null} */
  let currentPalette = null;
  /** @type {"files" | "size"} */
  let currentMetric = initialMetric === "size" ? "size" : "files";
  // Whether pending totals are still on their way. See stopLoading.
  let awaitingTotals = true;

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
    allRow = totalsRow("Total");
    allRow.tr.classList.add("folder-totals-row-all");
    // Last, after the two rows it sums: a reader adds downward.
    body.append(filesRow.tr, ignoredRow.tr, allRow.tr);
    table.append(columns, head, body);
    root.append(table);
  }

  /** @param {ReturnType<typeof totalsRow>} handle @param {"all" | "files" | "ignored"} population @param {number} value */
  function updateTrack(handle, population, value) {
    const projected =
      currentComposition?.metric === currentMetric ? currentComposition[population] : null;
    const segments = projected?.value === value ? projected.segments : null;
    /** @type {Map<string, DrawnSegment>} */
    const drawn = new Map();
    segmentsDrawn.set(population, drawn);
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
        fill.className = "file-type-summary-fill";
        palette.paint(fill, segment.paletteKey);
        fill.dataset.segmentKey = segment.key;
        fill.style.width = `${segment.share}%`;
        const counts = `${mb.formatFileCount(segment.files)} · ${mb.formatSize(segment.bytes)}`;
        drawn.set(segment.key, {
          fill,
          tooltip: `<strong>${mb.escapeHtml(segment.label)}</strong><br>${counts}`,
          counts,
        });
        // The segment says where the pointer is, as a legend entry naming its family does,
        // and the hover draws itself (showHover): one path for both. A segment names one
        // value, its family's share of this row, so it marks itself alone.
        /** @type {DistributionHoverTarget} */
        const target = Object.freeze({
          population,
          key: segment.key,
          anchor: fill,
          marks: /** @type {const} */ ("self"),
        });
        fill.addEventListener("mouseenter", () => hover.enter(target));
        fill.addEventListener("mouseleave", () => hover.leave(target));
        return fill;
      }),
    );
  }

  /**
   * Draw the hover: lift and grow what it marks, and show its segment's tooltip, anchored
   * on the handle the pointer is on, the segment or a legend entry naming its family.
   *
   * A segment marks itself alone. A legend entry marks its family's segment in every row
   * drawn, Files, Ignored, and Total, since the entry names the family and each of those
   * is the family's share of a row; the Details table marks its own row
   * (distribution-view.js). The tooltip is one segment's, never one per mark: on the
   * segment it names the family; on an entry, which shows the name, it gives the file
   * count and byte size alone of the family's segment in the row the legend's shares are
   * of (docs/design-system.md, "Restating is not adding"). A row with no such segment on
   * screen, as while the bars are still one neutral fill, draws nothing of it. A handle
   * that marks itself and is not one of these segments draws nothing here.
   *
   * @param {DistributionHoverTarget | null} target
   */
  function showHover(target) {
    for (const fill of hoveredFills) {
      delete fill.dataset.hovered;
    }
    hoveredFills = [];
    const named = target && segmentsDrawn.get(target.population)?.get(target.key);
    /** @type {DrawnSegment | null | undefined} */
    let segment = null;
    if (target?.marks === "family") {
      for (const drawn of segmentsDrawn.values()) {
        const fill = drawn.get(target.key)?.fill;
        if (fill) {
          fill.dataset.hovered = "";
          hoveredFills.push(fill);
        }
      }
      segment = named;
    } else if (named && named.fill === target?.anchor) {
      named.fill.dataset.hovered = "";
      hoveredFills.push(named.fill);
      segment = named;
    }
    if (target && segment) {
      mb.tooltip.show(
        target.anchor === segment.fill ? segment.tooltip : segment.counts,
        target.anchor,
      );
      tooltipOn = target.anchor;
    } else if (tooltipOn) {
      // Only the tooltip the hover showed, anchored on the handle the pointer was on: a
      // legend entry outside these bars or a segment in them. A hover that showed none
      // has none to put away.
      mb.tooltip.hide(tooltipOn);
      tooltipOn = null;
    }
  }
  const unsubscribeHover = hover.subscribe(showHover);

  /** @param {FolderTotalsMetricRow} row @param {ReturnType<typeof totalsRow>} handle @param {"all" | "files" | "ignored"} population */
  function updateRow(row, handle, population) {
    const selected = selectFolderTotalsMetric(row, currentMetric);
    const displayKind = currentMetric === "files" ? "count" : "size";
    handle.metric.cell.className = `file-type-summary-metric file-type-summary-metric-${currentMetric}`;
    handle.metric.value.className = `file-type-summary-value data-num ${displayKind} ${
      currentMetric === "files" ? mb.countClass(selected.value) : mb.sizeClass(selected.value)
    }`.trim();
    handle.metric.value.textContent = selected.text;
    updateTrack(handle, population, selected.value);
  }

  function render() {
    // A draw replaces the segments the hover was drawn on, so it puts the hover away with
    // its tooltip. A segment the pointer is on is replaced under it, and the browser
    // enters the new one. A legend entry outlives the draw and hears nothing, so a hover
    // held from one is drawn again on the redrawn bars: the folder's sums arrive whenever
    // a file changes, and pointing at the entry stays pointing at its family's segments.
    const held = hover.current();
    hover.clear();
    // Its own segments' tooltip, and no other surface's (mb-alff).
    mb.tooltip.hide(root);
    segmentsDrawn.clear();
    draw();
    if (held?.anchor.isConnected && !root.contains(held.anchor)) {
      hover.enter(held);
    }
  }

  function draw() {
    const model = buildFolderTotalsModel(currentTotals, mb);
    if (model.state === "pending") {
      table = null;
      filesRow = null;
      ignoredRow = null;
      allRow = null;
      metricHeader = null;
      root.innerHTML = awaitingTotals
        ? '<div class="folder-totals-loading mb-delayed-loading" aria-hidden="true"></div>' +
          '<span class="sr-only">Loading file totals…</span>'
        : "";
      return;
    }
    ensureTable();
    if (!filesRow || !ignoredRow || !allRow) {
      throw new TypeError("folder totals table failed to initialize");
    }
    if (metricHeader) {
      metricHeader.textContent = currentMetric === "size" ? "Bytes" : "Files";
    }
    updateRow(model.files, filesRow, "files");
    updateRow(model.ignored, ignoredRow, "ignored");
    updateRow(model.all, allRow, "all");
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

  /** @param {FolderTotalsComposition | null} composition @param {{classFor(key: string): string, paint(element: HTMLElement, key: string): void} | null} palette */
  function updateComposition(composition, palette) {
    currentComposition = composition;
    currentPalette = palette;
    render();
  }

  /**
   * The rollup answered or failed without totals, and whatever shows that says
   * why. A skeleton here would keep promising numbers nothing is going to send.
   * Totals that do arrive later, from a retry or the index, still take its place.
   */
  function stopLoading() {
    awaitingTotals = false;
    render();
  }

  /**
   * A later answer said the scan is still running, so the skeleton is honest again. A scan
   * says so on every refresh, and a repaint each time would restart the skeleton's quiet
   * period and put away a tooltip, so only the change repaints.
   */
  function resumeLoading() {
    if (!awaitingTotals) {
      awaitingTotals = true;
      render();
    }
  }

  function dispose() {
    hover.clear();
    unsubscribeHover();
    segmentsDrawn.clear();
    mb.tooltip.hide(root);
    root.replaceChildren();
  }

  render();
  return Object.freeze({
    dispose,
    resumeLoading,
    stopLoading,
    update,
    updateComposition,
    updateMetric,
  });
}
