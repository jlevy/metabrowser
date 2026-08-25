// Unified diff renderer over File Diff Format.
//
// Each file renders as a section under a bar: the section-disclosure
// primitive carrying the filename (styled as a filename, not a
// heading), change notes, the inline +N −N stat pair, and a copy-path
// control riding the shell's [data-copy-path] delegation. Sections
// start expanded; the bar collapses the body without disposing it.
// Every availability state has exactly one rendering path — an absent
// patch is a labeled state, never an empty box. Rendering is
// deliberately dumber than the model: the data plane is tested by the
// conformance corpus and CLI goldens, and this layer only projects it.

import { fileChangeLabel, validateDocument } from "./diff-model.js";
import { buildFileRenderModel, refineFileChangedRuns } from "./diff-render-model.js";
import { highlightFileSyntax, syntaxInputBytes } from "./diff-syntax.js";

/**
 * @typedef {object} DiffViewApi
 * @property {(data: Record<string, unknown>) => boolean} isLargeTextPreview
 * @property {(source: string, language: string, options?: {signal?: AbortSignal, inputBytes?: number}) => Promise<MetabrowserSyntaxTokenLines | null>} highlightSyntax
 * @property {(pathOrName: string) => string} langForPath
 * @property {NonNullable<MetabrowserPublicSdk["filterControls"]> | undefined} [filterControls]
 * @property {Pick<MetabrowserPublicSdk["perf"], "measureAsync"> | undefined} [perf]
 * @property {{get: <T>(name: string, fallback: T) => T, set: (name: string, value: unknown) => boolean} | undefined} [prefs]
 */

/**
 * @typedef {object} FileViewState
 * @property {Record<string, unknown>} change
 * @property {HTMLElement} body
 * @property {Set<string>} expandedFolds
 * @property {Record<string, unknown>} patch
 * @property {ReturnType<typeof buildFileRenderModel>} renderModel
 * @property {{host: HTMLElement, line: ReturnType<typeof buildFileRenderModel>["hunks"][number]["lines"][number], side: "old" | "new"}[]} textHosts
 */

/**
 * @typedef {object} MountedDiffState
 * @property {DiffViewApi | undefined} api
 * @property {AbortController} controller
 * @property {boolean} disposed
 * @property {FileViewState[]} files
 * @property {number} generation
 * @property {"unified" | "split"} layout
 * @property {HTMLElement | null} layoutControl
 * @property {number} layoutGeneration
 * @property {HTMLElement} root
 * @property {Promise<void>} enhancementTail
 * @property {Set<number>} timers
 * @property {Set<{timer: number, resolve: (active: boolean) => void}>} yielders
 */

/**
 * Fetch one file's change from a comparison. Injected by the plugin so
 * this module keeps its only job — projecting a document — and stays
 * testable without a shell.
 *
 * @type {(revision: string, path: string, options?: {signal?: AbortSignal}) => Promise<Record<string, unknown>>}
 */
let loadOneChange = async () => {
  throw new Error("no loader configured");
};

/** @returns {DiffViewApi} */
function plainSyntaxApi() {
  return {
    highlightSyntax: async () => null,
    isLargeTextPreview: () => true,
    langForPath: () => "",
    filterControls: undefined,
    prefs: undefined,
  };
}

/** @param {(revision: string, path: string, options?: {signal?: AbortSignal}) => Promise<Record<string, unknown>>} loader */
export function setChangeLoader(loader) {
  loadOneChange = loader;
}

// Copy for states that are facts about the change, not steps the
// reader can take. `deferred` is deliberately absent: it is progress,
// and progress is a spinner, never prose.
const AVAILABILITY_COPY = /** @type {Record<string, string>} */ ({
  binary: "Binary file; no textual diff.",
  too_large: "This change is too large to show inline.",
  timed_out: "Producing this diff timed out.",
  failed: "Could not produce this diff.",
  stale: "The comparison changed underneath this file. Refresh to reload it.",
  unsupported: "This change cannot be shown as a text diff.",
});

// Chrome 151, five runs of explorations/diff-intraline/benchmark.html:
// ordinary edits completed in <= 1.2 ms, an 8 MiB mostly-equal line in
// <= 20.5 ms, and unrelated 8 MiB lines reached this bound in <= 32.6 ms.
// This deterministic limit caps edit-distance work; it does not impose a
// smaller input-size cutoff than the existing patch bound.
const INTRALINE_WORK_BUDGET = 1_000_000;

// A load this slow is worth a console record even when it eventually
// succeeds: a reader watching a spinner deserves a diagnosable stall.
const SLOW_LOAD_MS = 4000;

/**
 * The app's standard progress box: hidden until --loading-state-delay,
 * so a fast load never flashes a spinner.
 *
 * @param {string} label Accessible name; never rendered as prose.
 * @returns {HTMLElement}
 */
function progressBox(label) {
  const box = el("div", "diff-progress mb-delayed-loading");
  box.setAttribute("role", "status");
  box.setAttribute("aria-label", label);
  const spinner = el("span", "spinner spinner-sm");
  spinner.setAttribute("aria-hidden", "true");
  box.append(spinner);
  return box;
}

/**
 * Report a load that failed or overran, with everything needed to
 * diagnose it from the console alone.
 *
 * @param {string} what
 * @param {Record<string, unknown>} detail
 * @param {unknown} [error]
 */
function reportLoad(what, detail, error) {
  const payload = { ...detail, elapsedMs: Math.round(Number(detail.elapsedMs) || 0) };
  if (error === undefined) {
    console.warn(`metabrowser diff: ${what} is slow`, payload);
    return;
  }
  console.error(`metabrowser diff: ${what} failed`, payload, error);
}

let sectionSequence = 0;
let foldSequence = 0;

const SETTINGS = /** @type {Record<string, number>} */ (
  /** @type {{METABROWSER_SETTINGS?: Record<string, number>}} */ (globalThis)
    .METABROWSER_SETTINGS ?? {}
);
// Server-set, with the same defaults, so a page served by an older
// build still folds sensibly. 0 disables folding.
const FOLD_THRESHOLD = Number(SETTINGS.DIFF_FOLD_THRESHOLD ?? 40);
const FOLD_VISIBLE = Number(SETTINGS.DIFF_FOLD_VISIBLE ?? 20);
// Chrome 151 took 223.7 ms to reproject 1,000 ready files in one pass.
// One-tenth-sized batches keep the same measured work below the 200 ms
// interaction budget; explorations/diff-layout/README.md records the fixture.
const LAYOUT_PROJECTION_BATCH_FILES = 100;

/** @param {string} tag @param {string} className @param {string} [text] */
function el(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

/**
 * A glyph from the shell's shared registry, or "" outside the shell.
 *
 * @param {string} name
 * @returns {string}
 */
function shellIcon(name) {
  const shell = /** @type {{metabrowser?: {icons?: Record<string, string>}}} */ (
    /** @type {unknown} */ (globalThis)
  );
  return shell.metabrowser?.icons?.[name] ?? "";
}

/**
 * @typedef {object} ComposedTextRun
 * @property {string[]} classes
 * @property {string} text
 */

/**
 * Intersect syntax and intraline boundaries while preserving the source exactly.
 * @param {string} text
 * @param {MetabrowserSyntaxTokenRun[] | null} tokenRuns
 * @param {import("./diff-intraline.js").IntralineRange[]} intralineRanges
 * @returns {ComposedTextRun[]}
 */
export function composeTextRuns(text, tokenRuns, intralineRanges) {
  const boundaries = new Set([0, text.length]);
  /** @type {{start: number, end: number, classes: string[]}[]} */
  const tokens = [];
  let tokenOffset = 0;
  for (const run of tokenRuns ?? [{ classes: [], text }]) {
    const end = tokenOffset + run.text.length;
    boundaries.add(tokenOffset);
    boundaries.add(end);
    tokens.push({ classes: run.classes, end, start: tokenOffset });
    tokenOffset = end;
  }
  const ranges = intralineRanges.filter(
    (range) => 0 <= range.start && range.start < range.end && range.end <= text.length,
  );
  for (const range of ranges) {
    boundaries.add(range.start);
    boundaries.add(range.end);
  }
  const offsets = [...boundaries].sort((left, right) => left - right);
  /** @type {ComposedTextRun[]} */
  const result = [];
  let tokenIndex = 0;
  let rangeIndex = 0;
  for (let index = 0; index + 1 < offsets.length; index += 1) {
    const start = offsets[index];
    const end = offsets[index + 1];
    if (start === end) {
      continue;
    }
    while (tokenIndex + 1 < tokens.length && tokens[tokenIndex].end <= start) {
      tokenIndex += 1;
    }
    while (rangeIndex + 1 < ranges.length && ranges[rangeIndex].end <= start) {
      rangeIndex += 1;
    }
    const classes = [...(tokens[tokenIndex]?.classes ?? [])];
    const range = ranges[rangeIndex];
    if (range !== undefined && range.start <= start && end <= range.end) {
      classes.push("diff-intraline-change");
    }
    result.push({ classes, text: text.slice(start, end) });
  }
  return result;
}

/**
 * Put composed scanner and intraline runs into an existing text host.
 * @param {HTMLElement} host
 * @param {string} text
 * @param {MetabrowserSyntaxTokenRun[] | null} tokenRuns
 * @param {import("./diff-intraline.js").IntralineRange[]} intralineRanges
 */
function renderComposedText(host, text, tokenRuns, intralineRanges) {
  const spans = composeTextRuns(text, tokenRuns, intralineRanges).map((run) => {
    const span = el("span", run.classes.join(" "));
    span.textContent = run.text;
    return span;
  });
  host.replaceChildren(...spans);
}

/** @typedef {ReturnType<typeof buildFileRenderModel>["hunks"][number]["lines"][number]} DiffLine */
/** @typedef {import("./diff-render-model.js").DiffSplitRow} SplitRow */

/**
 * @param {DiffLine} line
 * @param {"old" | "new"} side
 */
function sideTokens(line, side) {
  return side === "old" ? line.oldTokens : line.newTokens;
}

/**
 * @param {DiffLine} line
 * @param {"old" | "new"} side
 */
function sideIntralineRanges(line, side) {
  return side === "old" ? line.oldIntralineRanges : line.newIntralineRanges;
}

/**
 * @param {FileViewState} state
 * @param {DiffLine} line
 * @param {"old" | "new"} side
 */
function renderTextHost(state, line, side) {
  // `hljs` marks this as already owned by the token pipeline. The
  // first paint remains complete plain text, and the shell's global
  // `pre code:not(.hljs)` enhancer cannot select this span.
  const host = el("span", "diff-line-text hljs", line.text);
  const runs = sideTokens(line, side);
  const intralineRanges = sideIntralineRanges(line, side);
  if (runs !== null || intralineRanges.length > 0) {
    renderComposedText(host, line.text, runs, intralineRanges);
  }
  state.textHosts.push({ host, line, side });
  return host;
}

/** @param {ReturnType<typeof buildFileRenderModel>["hunks"][number]} hunk */
function renderHunkHeader(hunk) {
  const heading = hunk.heading ? ` ${hunk.heading}` : "";
  return el(
    "div",
    "diff-hunk-header",
    `@@ -${hunk.oldStart},${hunk.oldCount} +${hunk.newStart},${hunk.newCount} @@${heading}`,
  );
}

/** @param {ReturnType<typeof buildFileRenderModel>["hunks"][number]} hunk */
export function projectUnifiedHunk(hunk) {
  return hunk.lines.slice();
}

/** @param {DiffLine[]} lines @returns {SplitRow[]} */
function positionalChangedRunRows(lines) {
  const oldLines = lines.filter((line) => line.op === "del");
  const newLines = lines.filter((line) => line.op === "add");
  const changedRun = lines[0]?.changedRun ?? null;
  return Array.from({ length: Math.max(oldLines.length, newLines.length) }, (_, index) => ({
    changedRun,
    new: newLines[index] ?? null,
    old: oldLines[index] ?? null,
    refined: false,
  }));
}

/**
 * Duplicate context and positionally pair each contiguous changed run.
 * @param {ReturnType<typeof buildFileRenderModel>["hunks"][number]} hunk
 * @returns {SplitRow[]}
 */
export function projectSplitHunk(hunk) {
  /** @type {SplitRow[]} */
  const rows = [];
  for (let index = 0; index < hunk.lines.length; ) {
    const line = hunk.lines[index];
    if (line.op === "context") {
      rows.push({ changedRun: null, new: line, old: line, refined: false });
      index += 1;
      continue;
    }
    const run = line.changedRun;
    let end = index + 1;
    while (end < hunk.lines.length && hunk.lines[end].changedRun === run) {
      end += 1;
    }
    rows.push(
      ...(run === null
        ? []
        : (hunk.changedRunRows.get(run) ?? positionalChangedRunRows(hunk.lines.slice(index, end)))),
    );
    index = end;
  }
  return rows;
}

/**
 * @param {FileViewState} state
 * @param {DiffLine} line
 */
function renderUnifiedLine(state, line) {
  const refined = line.intralineRefined ? " diff-line-refined" : "";
  const row = el("div", `diff-line diff-line-${line.op}${refined}`);
  row.append(
    el("span", "diff-line-number", line.oldNumber === null ? "" : String(line.oldNumber)),
    el("span", "diff-line-number", line.newNumber === null ? "" : String(line.newNumber)),
    el("span", "diff-line-marker", line.op === "add" ? "+" : line.op === "del" ? "-" : " "),
    renderTextHost(state, line, line.op === "del" ? "old" : "new"),
  );
  if (line.noNewline) {
    row.append(el("span", "diff-line-no-newline", "⏎ absent"));
    row.dataset.tipText = "No newline at end of file";
  }
  return row;
}

/**
 * @param {FileViewState} state
 * @param {DiffLine | null} line
 * @param {"old" | "new"} side
 */
function renderSplitSide(state, line, side) {
  if (line === null) {
    const empty = el("div", `diff-split-side diff-split-${side} diff-split-empty`);
    empty.setAttribute("aria-hidden", "true");
    return empty;
  }
  const op = line.op === "context" ? "context" : side === "old" ? "del" : "add";
  const number = side === "old" ? line.oldNumber : line.newNumber;
  const refined = line.intralineRefined ? " diff-line-refined" : "";
  const cell = el("div", `diff-split-side diff-split-${side} diff-line-${op}${refined}`);
  cell.append(
    el("span", "diff-line-number", number === null ? "" : String(number)),
    el("span", "diff-line-marker", op === "del" ? "-" : op === "add" ? "+" : " "),
    renderTextHost(state, line, side),
  );
  if (line.noNewline) {
    cell.append(el("span", "diff-line-no-newline", "⏎ absent"));
    cell.dataset.tipText = "No newline at end of file";
  }
  return cell;
}

/** @param {FileViewState} state @param {SplitRow} row */
function renderSplitLine(state, row) {
  const className =
    row.changedRun === null
      ? "diff-split-context"
      : `diff-split-change${row.refined ? " diff-line-refined" : ""}`;
  const element = el("div", `diff-split-row ${className}`);
  element.append(renderSplitSide(state, row.old, "old"), renderSplitSide(state, row.new, "new"));
  return element;
}

/**
 * Append context rows and foldable changed runs. Split calls this with
 * paired rows, so thresholds and labels count paired rows.
 * @template T
 * @param {HTMLElement} section
 * @param {T[]} rows
 * @param {(row: T) => number | null} changedRunOf
 * @param {(row: T) => HTMLElement} renderRow
 * @param {FileViewState} state
 * @param {number} hunkIndex
 */
function appendFoldedRows(section, rows, changedRunOf, renderRow, state, hunkIndex) {
  for (let index = 0; index < rows.length; ) {
    const changedRun = changedRunOf(rows[index]);
    if (changedRun === null) {
      section.append(renderRow(rows[index]));
      index += 1;
      continue;
    }
    let end = index + 1;
    while (end < rows.length && changedRunOf(rows[end]) === changedRun) {
      end += 1;
    }
    const run = rows.slice(index, end);
    if (FOLD_THRESHOLD <= 0 || run.length <= FOLD_THRESHOLD) {
      section.append(...run.map(renderRow));
      index = end;
      continue;
    }
    section.append(...run.slice(0, FOLD_VISIBLE).map(renderRow));
    const hidden = run.length - FOLD_VISIBLE;
    const key = `${String(state.change.id)}:${hunkIndex}:${changedRun}`;
    const expanded = state.expandedFolds.has(key);
    foldSequence += 1;
    const group = el("div", `diff-fold-group${expanded ? "" : " diff-fold-collapsed"}`);
    group.setAttribute("id", `diff-fold-group-${foldSequence}`);
    group.append(...run.slice(FOLD_VISIBLE).map(renderRow));
    section.append(renderFoldControl(group, hidden, state, key), group);
    index = end;
  }
}

/**
 * @param {ReturnType<typeof buildFileRenderModel>["hunks"][number]} hunk
 * @param {FileViewState} state
 * @param {number} hunkIndex
 */
function renderUnifiedHunk(hunk, state, hunkIndex) {
  const section = el("div", "diff-hunk diff-hunk-unified");
  section.append(renderHunkHeader(hunk));
  const rows = projectUnifiedHunk(hunk);
  appendFoldedRows(
    section,
    rows,
    (line) => line.changedRun,
    (line) => renderUnifiedLine(state, line),
    state,
    hunkIndex,
  );
  return section;
}

/**
 * @param {ReturnType<typeof buildFileRenderModel>["hunks"][number]} hunk
 * @param {FileViewState} state
 * @param {number} hunkIndex
 */
function renderSplitHunk(hunk, state, hunkIndex) {
  const section = el("div", "diff-hunk diff-hunk-split");
  section.append(renderHunkHeader(hunk));
  const rows = projectSplitHunk(hunk);
  appendFoldedRows(
    section,
    rows,
    (row) => row.changedRun,
    (row) => renderSplitLine(state, row),
    state,
    hunkIndex,
  );
  return section;
}

/**
 * Build the cached semantic state shared by every projection.
 * @param {Record<string, unknown>} change
 * @param {Record<string, unknown>} patch
 * @param {DiffViewApi} api
 * @param {HTMLElement} body
 * @returns {FileViewState}
 */
export function createFileState(change, patch, api, body) {
  return {
    body,
    change,
    expandedFolds: new Set(),
    patch,
    renderModel: buildFileRenderModel(change, patch, api.langForPath),
    textHosts: [],
  };
}

/**
 * Render one active projection from cached source and token facts.
 * @param {FileViewState} state
 * @param {"unified" | "split"} layout
 */
export function renderFileBody(state, layout) {
  state.body.replaceChildren();
  state.textHosts = [];
  for (const [hunkIndex, hunk] of state.renderModel.hunks.entries()) {
    state.body.append(
      layout === "split"
        ? renderSplitHunk(hunk, state, hunkIndex)
        : renderUnifiedHunk(hunk, state, hunkIndex),
    );
  }
  if (state.patch.truncated) {
    state.body.append(el("div", "diff-availability", "This patch was truncated at its bounds."));
  }
}

/**
 * Record progressive diff work when the host profiler is present without
 * making progressive enhancement depend on diagnostics.
 * @template T
 * @param {DiffViewApi} api
 * @param {string} label
 * @param {() => Promise<T>} work
 * @param {Record<string, unknown>} metadata
 * @returns {Promise<T>}
 */
function measureEnhancement(api, label, work, metadata) {
  return api.perf ? api.perf.measureAsync(label, work, metadata) : work();
}

/**
 * Refresh current text hosts without changing unified row order or fold DOM.
 * @param {FileViewState} state
 */
function refreshTextHosts(state) {
  for (const { host, line, side } of state.textHosts) {
    const runs = sideTokens(line, side);
    const ranges = sideIntralineRanges(line, side);
    renderComposedText(host, line.text, runs, ranges);
    const row = host.closest(".diff-line");
    row?.classList.toggle("diff-line-refined", line.intralineRefined);
  }
}

/**
 * Attach browser-local changed ranges before syntax for the same file.
 * @param {FileViewState} state
 * @param {DiffViewApi} api
 * @param {AbortSignal} signal
 * @param {() => boolean} isCurrent
 * @param {() => "unified" | "split"} currentLayout
 */
async function enhanceFileIntraline(state, api, signal, isCurrent, currentLayout) {
  try {
    const enhanced = await measureEnhancement(
      api,
      "diffIntraline:file",
      async () =>
        refineFileChangedRuns(state.renderModel, { maxWork: INTRALINE_WORK_BUDGET }, signal),
      { hunk_count: state.renderModel.hunks.length },
    );
    if (!enhanced || !isCurrent()) {
      return;
    }
    if (currentLayout() === "split") {
      renderFileBody(state, "split");
    } else {
      refreshTextHosts(state);
    }
  } catch (error) {
    if (signal.aborted || (error instanceof DOMException && error.name === "AbortError")) {
      return;
    }
    console.warn("metabrowser diff: intraline enhancement failed", error);
  }
}

/**
 * Enhance only the text hosts from the current projection. Token data
 * stays on the semantic records for later projections.
 * @param {FileViewState} state
 * @param {DiffViewApi} api
 * @param {AbortSignal} signal
 * @param {() => boolean} isCurrent
 */
async function enhanceFileSyntax(state, api, signal, isCurrent) {
  try {
    state.renderModel.inputBytes ??= syntaxInputBytes(state.renderModel.hunks);
    const metadata = {
      hunk_count: state.renderModel.hunks.length,
      input_bytes: state.renderModel.inputBytes,
      lexer_calls: 0,
    };
    const measuredApi = {
      ...api,
      highlightSyntax: /** @type {DiffViewApi["highlightSyntax"]} */ (
        (source, language, options) => {
          metadata.lexer_calls += 1;
          return measureEnhancement(
            api,
            "diffSyntax:lexer",
            () => api.highlightSyntax(source, language, { signal: options?.signal }),
            {
              input_bytes: options?.inputBytes ?? 0,
              language,
            },
          );
        }
      ),
    };
    const enhanced = await measureEnhancement(
      api,
      "diffSyntax:file",
      () => highlightFileSyntax(state.renderModel, measuredApi, signal),
      metadata,
    );
    if (!enhanced || !isCurrent()) {
      return;
    }
    for (const { host, line, side } of state.textHosts) {
      const runs = sideTokens(line, side);
      if (runs !== null) {
        renderComposedText(host, line.text, runs, sideIntralineRanges(line, side));
      }
    }
  } catch (error) {
    if (signal.aborted || (error instanceof DOMException && error.name === "AbortError")) {
      return;
    }
    console.warn("metabrowser diff: syntax enhancement failed", error);
  }
}

/** @param {MountedDiffState} view @param {number} generation */
function mountIsCurrent(view, generation) {
  return !view.disposed && view.generation === generation;
}

/**
 * Yield one task between file-sized lexer units. Disposal resolves the
 * waiter as inactive instead of leaving the queue pending.
 * @param {MountedDiffState} view
 * @param {number} generation
 */
function yieldForEnhancement(view, generation) {
  return new Promise((resolve) => {
    if (!mountIsCurrent(view, generation)) {
      resolve(false);
      return;
    }
    const waiter = { resolve, timer: 0 };
    waiter.timer = setTimeout(() => {
      view.yielders.delete(waiter);
      resolve(mountIsCurrent(view, generation));
    }, 0);
    view.yielders.add(waiter);
  });
}

/**
 * Serialize file-sized enrichment in document order, with intraline first.
 * @param {MountedDiffState} view
 * @param {FileViewState} state
 */
function scheduleFileEnhancement(view, state) {
  const api = view.api ?? plainSyntaxApi();
  const generation = view.generation;
  view.enhancementTail = view.enhancementTail.then(async () => {
    if (!(await yieldForEnhancement(view, generation))) {
      return;
    }
    await enhanceFileIntraline(
      state,
      api,
      view.controller.signal,
      () => mountIsCurrent(view, generation),
      () => view.layout,
    );
    await enhanceFileSyntax(state, api, view.controller.signal, () =>
      mountIsCurrent(view, generation),
    );
  });
}

/**
 * The fold expander: the tree's disclosure vocabulary on a full-width
 * row, stating the count it holds so the reader knows what is hidden.
 *
 * @param {HTMLElement} group
 * @param {number} hidden
 * @param {FileViewState} state
 * @param {string} key
 * @returns {HTMLElement}
 */
function renderFoldControl(group, hidden, state, key) {
  let expanded = state.expandedFolds.has(key);
  const control = el("button", "diff-fold-control");
  control.setAttribute("type", "button");
  control.setAttribute("aria-expanded", String(expanded));
  control.setAttribute("aria-controls", group.getAttribute("id") || "");
  control.classList.toggle("expanded", expanded);
  const chevron = el("span", "diff-fold-chevron");
  const svg = shellIcon("toggle");
  if (svg) {
    chevron.innerHTML = svg;
  } else {
    chevron.textContent = "›";
  }
  const label = el(
    "span",
    "diff-fold-label",
    expanded
      ? `Hide ${hidden} line${hidden === 1 ? "" : "s"}`
      : `${hidden} more changed line${hidden === 1 ? "" : "s"}`,
  );
  control.append(chevron, label);
  control.addEventListener("click", (event) => {
    // The bar above owns clicks on the file section; a fold is its own
    // control and must not also collapse the whole file.
    event.stopPropagation();
    expanded = !expanded;
    if (expanded) {
      state.expandedFolds.add(key);
    } else {
      state.expandedFolds.delete(key);
    }
    control.setAttribute("aria-expanded", String(expanded));
    control.classList.toggle("expanded", expanded);
    group.classList.toggle("diff-fold-collapsed", !expanded);
    label.textContent = expanded
      ? `Hide ${hidden} line${hidden === 1 ? "" : "s"}`
      : `${hidden} more changed line${hidden === 1 ? "" : "s"}`;
  });
  return control;
}

/**
 * The per-file bar: one disclosure trigger (kind, path, notes, stats)
 * plus a sibling copy control, per the section-disclosure and icon
 * button primitives in the design system.
 *
 * @param {Record<string, unknown>} change
 * @param {string} toggleId
 * @param {string} bodyId
 * @returns {{bar: HTMLElement, toggle: HTMLElement}}
 */
function renderFileBar(change, toggleId, bodyId) {
  const { letter, label, notes } = fileChangeLabel(change);
  const bar = el("div", "diff-file-bar");
  const toggle = el("button", "diff-file-toggle expanded");
  toggle.setAttribute("type", "button");
  toggle.setAttribute("id", toggleId);
  toggle.setAttribute("aria-controls", bodyId);
  toggle.setAttribute("aria-expanded", "true");
  // The same disclosure glyph the nav tree leads with, rotated by the
  // same expanded/collapsed rules.
  const chevron = el("span", "diff-file-chevron");
  const chevronSvg = shellIcon("toggle");
  if (chevronSvg) {
    chevron.innerHTML = chevronSvg;
  } else {
    chevron.textContent = "›";
  }
  toggle.append(chevron);
  toggle.append(el("span", `diff-file-kind diff-file-kind-${String(change.kind)}`, letter));
  const pathSpan = el("span", "diff-file-path", label);
  pathSpan.dataset.tipText = label;
  toggle.append(pathSpan);
  if (change.additions !== null && change.additions !== undefined) {
    const stats = el("span", "diff-file-stats");
    stats.append(el("span", "diff-stat-add", `+${change.additions}`));
    stats.append(el("span", "diff-stat-del", `−${change.deletions}`));
    toggle.append(stats);
  }
  for (const note of notes) {
    toggle.append(el("span", "diff-file-note", note));
  }
  bar.append(toggle);

  const side = /** @type {Record<string, unknown> | undefined} */ (change.new ?? change.old);
  if (side !== undefined) {
    const copy = el("button", "icon-btn icon-btn-reveal diff-file-copy");
    copy.setAttribute("type", "button");
    copy.setAttribute("data-copy-path", String(side.path));
    copy.setAttribute("title", "Copy path");
    copy.setAttribute("aria-label", "Copy path");
    const svg = shellIcon("copy");
    if (svg) {
      copy.innerHTML = svg;
    } else {
      copy.textContent = "⧉";
    }
    bar.append(copy);
  }
  return { bar, toggle };
}

/** @param {DiffViewApi | undefined} api @returns {"unified" | "split"} */
export function readLayoutPreference(api) {
  const value = api?.prefs?.get("diff.layout", /** @type {unknown} */ ("unified"));
  return value === "split" ? "split" : "unified";
}

/**
 * Let a drag select one split code column without interleaving the
 * opposite side's row-major DOM text. Full-width rows clear the gate.
 * @param {HTMLElement} root
 */
export function installSplitSelectionGate(root) {
  const owner = root.ownerDocument || document;
  function clear() {
    delete root.dataset.selectionSide;
  }
  /** @param {Event} event */
  function onPointerDown(event) {
    const target = /** @type {{closest?: (selector: string) => unknown} | null} */ (event.target);
    const text = typeof target?.closest === "function" ? target.closest(".diff-line-text") : null;
    const side =
      text && typeof (/** @type {{closest?: unknown}} */ (text).closest) === "function"
        ? /** @type {HTMLElement | null} */ (
            /** @type {{closest: (selector: string) => unknown}} */ (text).closest(
              ".diff-split-side",
            )
          )
        : null;
    if (!side || !root.contains(side)) {
      clear();
      return;
    }
    root.dataset.selectionSide = side.classList.contains("diff-split-old") ? "old" : "new";
  }
  root.addEventListener("pointerdown", onPointerDown);
  owner.addEventListener("pointerup", clear);
  owner.addEventListener("pointercancel", clear);
  return () => {
    clear();
    root.removeEventListener("pointerdown", onPointerDown);
    owner.removeEventListener("pointerup", clear);
    owner.removeEventListener("pointercancel", clear);
  };
}

/** @param {MountedDiffState} view */
function renderLayoutControl(view) {
  const control = view.layoutControl;
  const filterControls = view.api?.filterControls;
  if (!control || !filterControls) {
    return;
  }
  control.innerHTML = filterControls.groupHtml({
    key: "diff-layout",
    label: "Diff layout",
    layout: "joined",
    options: [
      { label: "Unified", value: "unified" },
      { label: "Split", value: "split" },
    ],
    select: "one",
    value: view.layout,
  });
}

/**
 * Reproject cached file state and optionally persist the display choice.
 * @param {MountedDiffState} view
 * @param {string} value
 * @param {boolean} [persist]
 */
export function setLayout(view, value, persist = true) {
  if (view.disposed) {
    return;
  }
  const layout = value === "split" ? "split" : "unified";
  if (layout === view.layout) {
    return;
  }
  view.layout = layout;
  view.root.dataset.layout = layout;
  if (persist) {
    view.api?.prefs?.set("diff.layout", layout);
  }
  renderLayoutControl(view);
  view.layoutGeneration += 1;
  const layoutGeneration = view.layoutGeneration;
  if (view.files.length <= LAYOUT_PROJECTION_BATCH_FILES) {
    delete view.root.dataset.layoutPending;
    for (const state of view.files) {
      renderFileBody(state, layout);
    }
    return;
  }
  view.root.dataset.layoutPending = "true";
  projectLayoutBatch(view, layout, layoutGeneration, 0);
}

/**
 * Reproject one measured file batch and yield before the next. A generation
 * check makes a rapid second switch authoritative without cancelling shared
 * hydration or syntax work.
 * @param {MountedDiffState} view
 * @param {"unified" | "split"} layout
 * @param {number} layoutGeneration
 * @param {number} start
 */
function projectLayoutBatch(view, layout, layoutGeneration, start) {
  if (view.disposed || view.layoutGeneration !== layoutGeneration) {
    return;
  }
  const end = Math.min(start + LAYOUT_PROJECTION_BATCH_FILES, view.files.length);
  for (let index = start; index < end; index += 1) {
    renderFileBody(view.files[index], layout);
  }
  if (end >= view.files.length) {
    delete view.root.dataset.layoutPending;
    return;
  }
  const timer = setTimeout(() => {
    view.timers.delete(timer);
    projectLayoutBatch(view, layout, layoutGeneration, end);
  }, 0);
  view.timers.add(timer);
}

/**
 * The layout control is always present in the shell. Multi-file totals
 * share its toolbar; single-file views avoid repeating their file bar.
 * @param {Record<string, unknown>} totals
 * @param {MountedDiffState} view
 * @returns {{toolbar: HTMLElement, unbind: () => void}}
 */
function renderDiffToolbar(totals, view) {
  const toolbar = el("div", "diff-toolbar");
  if (Number(totals.files) !== 1) {
    const plus = totals.additions === null ? "?" : String(totals.additions);
    const minus = totals.deletions === null ? "?" : String(totals.deletions);
    const summary = el("div", "diff-summary");
    summary.append(
      el(
        "span",
        "diff-summary-files",
        `${totals.files} changed ${Number(totals.files) === 1 ? "file" : "files"}`,
      ),
      el("span", "diff-stat-add", `+${plus}`),
      el("span", "diff-stat-del", `−${minus}`),
    );
    if (!totals.exact) {
      summary.append(el("span", "diff-summary-note", "(estimated)"));
    }
    toolbar.append(summary);
  }
  const filterControls = view.api?.filterControls;
  if (!filterControls) {
    return { toolbar, unbind: () => {} };
  }
  const control = el("div", "diff-layout-control");
  view.layoutControl = control;
  renderLayoutControl(view);
  toolbar.append(control);
  const unbind = filterControls.bind(control, {
    onChange(key, value, select) {
      if (key === "diff-layout" && select === "one") {
        setLayout(view, value);
      }
    },
  });
  return { toolbar, unbind };
}

/**
 * Fetch one deferred file's hunks and splice them in, behind the
 * standard progress box.
 *
 * @param {HTMLElement} body
 * @param {Record<string, unknown>} change
 * @param {string} revision
 * @param {MountedDiffState} view
 */
async function hydrateDeferred(body, change, revision, view) {
  const generation = view.generation;
  const side = /** @type {Record<string, unknown> | undefined} */ (change.new ?? change.old);
  const path = String(side?.path ?? "");
  const box = progressBox(`Loading the diff for ${path}`);
  body.append(box);
  const started = Date.now();
  const slow = setTimeout(() => {
    view.timers.delete(slow);
    if (mountIsCurrent(view, generation)) {
      reportLoad("file hydration", { revision, path, elapsedMs: Date.now() - started });
    }
  }, SLOW_LOAD_MS);
  view.timers.add(slow);
  try {
    const payload = await loadOneChange(revision, path, { signal: view.controller.signal });
    if (!mountIsCurrent(view, generation)) {
      return;
    }
    const result = validateDocument(payload);
    if (!result.ok) {
      throw new Error(`invalid document: ${result.error}`);
    }
    const loaded =
      /** @type {{manifest: {files: Record<string, unknown>[]}, patches: Record<string, Record<string, unknown>>}} */ (
        result.document
      );
    const only = loaded.manifest.files[0];
    const patch = only ? loaded.patches[String(only.id)] : undefined;
    if (!only || patch === undefined) {
      throw new Error("the comparison returned no hunks for this file");
    }
    box.remove();
    const hunks = /** @type {Record<string, unknown>[]} */ (patch.hunks);
    if (hunks.length === 0) {
      body.append(el("div", "diff-availability", "No content changes."));
    } else {
      const renderApi = view.api ?? plainSyntaxApi();
      const state = createFileState(only, patch, renderApi, body);
      view.files.push(state);
      renderFileBody(state, view.layout);
      scheduleFileEnhancement(view, state);
    }
  } catch (error) {
    if (
      !mountIsCurrent(view, generation) ||
      view.controller.signal.aborted ||
      (error instanceof DOMException && error.name === "AbortError")
    ) {
      return;
    }
    reportLoad(
      "file hydration",
      { revision, path, hook: "diff/comparison", elapsedMs: Date.now() - started },
      error,
    );
    box.remove();
    body.append(el("div", "diff-availability", "Could not load this file's changes."));
  } finally {
    clearTimeout(slow);
    view.timers.delete(slow);
  }
}

/**
 * @param {Record<string, unknown>} change
 * @param {Record<string, unknown> | undefined} patch
 * @param {{revision?: string}} context
 * @param {MountedDiffState} view
 * @returns {HTMLElement}
 */
function renderFileSection(change, patch, context, view) {
  sectionSequence += 1;
  const toggleId = `diff-file-toggle-${sectionSequence}`;
  const bodyId = `diff-file-body-${sectionSequence}`;
  const section = el("section", "diff-file");
  section.setAttribute("aria-labelledby", toggleId);
  const { bar, toggle } = renderFileBar(change, toggleId, bodyId);
  const body = el("div", "diff-file-body");
  body.setAttribute("id", bodyId);
  section.append(bar, body);

  // The whole bar is one activation surface, like a tree row; the
  // button stays the semantic trigger for focus and keyboard, whose
  // synthesized click bubbles here. Only the copy control opts out.
  let expanded = true;
  bar.addEventListener("click", (event) => {
    const origin = /** @type {{closest?: (selector: string) => unknown}} */ (event.target);
    if (typeof origin?.closest === "function" && origin.closest("[data-copy-path]")) {
      return;
    }
    expanded = !expanded;
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.classList.toggle("expanded", expanded);
    toggle.classList.toggle("collapsed", !expanded);
    body.classList.toggle("diff-file-body-collapsed", !expanded);
    section.classList.toggle("diff-file-collapsed", !expanded);
  });

  const availability = String(change.availability);
  if (availability === "deferred" && context.revision) {
    // Deferred is progress, not a state to explain: show the standard
    // progress box and fetch this file's hunks.
    void hydrateDeferred(body, change, context.revision, view);
    return section;
  }
  if (availability !== "ready" || patch === undefined) {
    const copy = AVAILABILITY_COPY[availability] || "These changes are unavailable.";
    body.append(el("div", "diff-availability", copy));
    return section;
  }
  const hunks = /** @type {Record<string, unknown>[]} */ (patch.hunks);
  if (hunks.length === 0) {
    // A hydrated patch with no hunks is a metadata-only change (a chmod,
    // a pure rename): the bar already says everything it changes.
    body.append(el("div", "diff-availability", "No content changes."));
    return section;
  }
  const state = createFileState(change, patch, view.api ?? plainSyntaxApi(), body);
  view.files.push(state);
  renderFileBody(state, view.layout);
  scheduleFileEnhancement(view, state);
  return section;
}

/**
 * Mount a validated ChangeSetDocument.
 *
 * @param {HTMLElement} container
 * @param {Record<string, unknown>} document_
 * @param {DiffViewApi} [api]
 * @returns {{dispose: () => void}}
 */
export function mountDiffView(container, document_, api) {
  const root = el("div", "diff-root");
  /** @type {MountedDiffState} */
  const view = {
    api,
    controller: new AbortController(),
    disposed: false,
    files: [],
    generation: 1,
    layout: readLayoutPreference(api),
    layoutControl: null,
    layoutGeneration: 0,
    root,
    enhancementTail: Promise.resolve(),
    timers: new Set(),
    yielders: new Set(),
  };
  const removeSelectionGate = installSplitSelectionGate(root);
  root.dataset.layout = view.layout;
  const manifest =
    /** @type {{files: Record<string, unknown>[], totals: Record<string, unknown>, truncated: unknown, cursor?: unknown}} */ (
      document_.manifest
    );
  const patches = /** @type {Record<string, Record<string, unknown>>} */ (document_.patches);
  const totals = manifest.totals;
  const { toolbar, unbind } = renderDiffToolbar(totals, view);
  root.append(toolbar);
  const context = { revision: String(document_.__revision ?? "") };
  for (const change of manifest.files) {
    root.append(renderFileSection(change, patches[String(change.id)], context, view));
  }
  if (manifest.truncated) {
    root.append(el("div", "diff-availability", "The change list was truncated at its bounds."));
  }
  container.append(root);
  return {
    dispose() {
      if (view.disposed) {
        return;
      }
      view.disposed = true;
      view.generation += 1;
      view.controller.abort();
      for (const timer of view.timers) {
        clearTimeout(timer);
      }
      view.timers.clear();
      for (const waiter of view.yielders) {
        clearTimeout(waiter.timer);
        waiter.resolve(false);
      }
      view.yielders.clear();
      unbind();
      removeSelectionGate();
      root.remove();
    },
  };
}
