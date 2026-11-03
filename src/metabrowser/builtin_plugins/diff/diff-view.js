// Unified diff renderer over File Diff Format.
//
// Each file renders as a section under a bar: the section-disclosure
// primitive carrying the filename (styled as a filename, not a
// heading), change notes, the inline +N −N stat pair, the View file
// controls of diff-view-file.js when the page can open a file at a
// commit, and a copy-path control riding the shared [data-mb-copy]
// delegation. Sections start expanded; the bar collapses the body
// without disposing it.
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
 * @property {(<T extends Element>(element: T) => T) | undefined} [ownDelegate]
 * @property {NonNullable<MetabrowserPublicSdk["filterControls"]> | undefined} [filterControls]
 * @property {Pick<MetabrowserPublicSdk["perf"], "measure" | "measureAsync"> | undefined} [perf]
 * @property {{get: <T>(name: string, fallback: T) => T, set: (name: string, value: unknown) => boolean} | undefined} [prefs]
 */

/**
 * @typedef {object} FileViewState
 * @property {Record<string, unknown>} change
 * @property {HTMLElement} body
 * @property {Set<string>} expandedFolds
 * @property {Map<string, {timer: number}>} foldTasks
 * @property {Record<string, unknown>} patch
 * @property {DiffViewApi} api
 * @property {ReturnType<typeof buildFileRenderModel>} renderModel
 * @property {{host: HTMLElement, line: ReturnType<typeof buildFileRenderModel>["hunks"][number]["lines"][number], side: "old" | "new"}[]} textHosts
 */

/**
 * @typedef {object} MountedDiffState
 * @property {DiffViewApi | undefined} api
 * @property {Map<string, FileEntry>} byNewPath Each file by the path it has now.
 * @property {Map<string, FileEntry>} byOldPath Each file by the path it had.
 * @property {Map<HTMLElement, FileEntry>} bySection Each file by its mounted section.
 * @property {() => void} notifyCurrentFile Queue a current-file report for subscribers.
 * @property {AbortController} controller
 * @property {Map<string, DeferredFile>} deferred Files asked for when they are reached, by id.
 * @property {number} deferredLeft Files of this comparison not here yet.
 * @property {number} deferredFailed Files of this comparison that could not be loaded.
 * @property {Map<HTMLElement, string>} deferredBySection
 * @property {boolean} disposed
 * @property {number} fileTotal
 * @property {FileViewState[]} files
 * @property {number} generation
 * @property {ReturnType<typeof createHydrationScheduler>} hydration
 * @property {IntersectionObserver | null} hydrationObserver
 * @property {boolean} awaitingWidth Nothing is drawn until the first report of a width.
 * @property {"unified" | "split"} chosenLayout What the reader chose, whatever fits.
 * @property {boolean} insistedOnSplit The reader chose Split where it does not fit.
 * @property {"unified" | "split"} layout What the diff draws.
 * @property {HTMLElement | null} layoutControl
 * @property {number} layoutGeneration
 * @property {boolean} listTruncated The comparison's own list stopped at its bound.
 * @property {boolean} narrow The diff is too narrow for Split.
 * @property {HTMLElement | null} partialNote
 * @property {HTMLElement | null} pinned The file a jump put at the top, until the reader moves.
 * @property {number} pinnedAt When the pin was set, on the event clock, so the key that
 *   caused a jump does not also release it.
 * @property {AbortController | null} pinListeners
 * @property {Record<string, unknown>} resolved
 * @property {HTMLElement} root
 * @property {Promise<void>} enhancementTail
 * @property {HTMLElement[]} sections In the comparison's order.
 * @property {HTMLElement | null} spacer Room past the last file, for a jump near the end.
 * @property {Set<number>} timers
 * @property {import("./diff-view-file.js").ViewFileOpener | null} viewFile
 * @property {HTMLElement | null} viewFileBusy The control whose switch is on its way.
 * @property {Set<{timer: number, resolve: (active: boolean) => void}>} yielders
 */

/**
 * @typedef {object} FileEntry
 * @property {Record<string, unknown>} change
 * @property {HTMLElement} section
 * @property {() => void} expand
 */

/**
 * @typedef {{manifest: {files: Record<string, unknown>[]}, patches: Record<string, Record<string, unknown>>}} OneFileAnswer
 *   One file's answer, as the comparison route gives it for one path.
 *
 * @typedef {object} DeferredFile
 * @property {HTMLElement} section
 * @property {HTMLElement} body
 * @property {Record<string, unknown>} change
 * @property {OneFileAnswer | null} held The answer already in hand, for a ready file the
 *   mount did not draw: drawn when it is reached, and never asked for.
 * @property {string} revision
 * @property {HTMLElement | null} box The progress box while it is being asked for.
 * @property {ReturnType<typeof setTimeout> | null} slow
 * @property {number} startedAt
 */

/**
 * What the mount draws its first rows by, measured with the root in its container: the
 * pane's height, how far down the pane the diff starts, and what one file's bar and one row
 * of lines take on the page.
 *
 * @typedef {{paneHeight: number, rootTop: number, barPx: number, rowPx: number}} ScreenGeometry
 */

/**
 * What a jump did, for the changed-files list that asked. A row in that list comes from
 * GitHub's own list of the pull request's files, so it can name a path this comparison does
 * not hold: the two are computed apart, and this one stops at its bound.
 *
 * @typedef {(
 *   {kind: "jumped", fileId: string, path: string, availability: string, lines: Promise<JumpOutcome>} |
 *   {kind: "not_in_comparison", path: string, listTruncated: boolean} |
 *   {kind: "disposed", path: string}
 * )} FileJump
 *
 * What a comparison holds at a path, for the same list, with nothing moved. `changeKind` is
 * the change's own kind (`modified`, `renamed`, and so on), apart from the answer's.
 *
 * @typedef {(
 *   {kind: "file", path: string, fileId: string, changeKind: string, availability: string} |
 *   {kind: "not_in_comparison", path: string, listTruncated: boolean}
 * )} FileLookup
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

// A single file's answer owes the file or a reason. `deferred` there is neither, so it is
// said as what it is and not as a failure of this page; in a document with no source to
// ask, a deferred file is simply unavailable, which the table above's fallback says.
const DEFERRED_AGAIN_COPY =
  "The server did not load this file's changes. Reload the page to ask again.";

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
// The existing measured layout projection batch creates at least three row
// elements per file. Keeping fold expansion to 100 rows is the stricter of
// the two projection budgets and gives the browser a task boundary between
// chunks of a very large changed run.
const FOLD_MATERIALIZATION_BATCH_ROWS = 100;
// Chrome 151 took 223.7 ms to reproject 1,000 ready files in one pass.
// One-tenth-sized batches keep the same measured work below the 200 ms
// interaction budget; explorations/diff-layout/README.md records the fixture.
const LAYOUT_PROJECTION_BATCH_FILES = 100;
// What Split needs to show both sides: the `min-width` of `.diff-hunk-split` in styles.css,
// in ems of the diff's text, which tests/test_diff_browser_js.py keeps equal to this, and
// the 2 px of border around a file. Measured 2026-11-02 in Chrome 152 at 14 px on a 34-file
// pull request: with `.diff-root` 618 px wide every file body fits, and at 617 px each
// overflows by a pixel. At 440 px a body shows 438 of its 616 px, and the right column's
// text is behind a sideways scroll, so an added line reads as a blank gap.
export const SPLIT_MIN_WIDTH_EM = 44;
const FILE_BORDER_PX = 2;
// How much more room going back to Split takes. Drawing the other layout changes the page's
// height, and so whether the pane has a scrollbar, which takes width: 11 px in the same
// Chrome. With no margin, a pane within that of the limit could flip for as long as it stayed.
export const SPLIT_RETURN_MARGIN_PX = 20;
const SPLIT_TOO_NARROW_TIP =
  "Too narrow for Split, so this shows Unified. Choose Split to scroll sideways.";

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
    const key = `${String(state.change.id)}:${hunkIndex}:${changedRun}`;
    const expanded = state.expandedFolds.has(key);
    foldSequence += 1;
    const group = el("div", `diff-fold-group${expanded ? "" : " diff-fold-collapsed"}`);
    group.setAttribute("id", `diff-fold-group-${foldSequence}`);
    section.append(renderFoldControl(group, run.slice(FOLD_VISIBLE), renderRow, state, key), group);
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
  const hunks = /** @type {Record<string, unknown>[]} */ (patch.hunks);
  return {
    api,
    body,
    change,
    expandedFolds: new Set(),
    foldTasks: new Map(),
    patch,
    renderModel: measureProjection(
      api,
      "diffMount:model",
      () => buildFileRenderModel(change, patch, api.langForPath),
      {
        hunk_count: hunks.length,
        line_count: hunks.reduce(
          (total, hunk) => total + (Array.isArray(hunk.lines) ? hunk.lines.length : 0),
          0,
        ),
      },
    ),
    textHosts: [],
  };
}

/**
 * Render one active projection from cached source and token facts.
 * @param {FileViewState} state
 * @param {"unified" | "split"} layout
 */
export function renderFileBody(state, layout) {
  cancelFoldMaterializations(state);
  return measureProjection(
    state.api,
    "diffMount:fileProjection",
    () => {
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
        state.body.append(
          el("div", "diff-availability", "This patch was truncated at its bounds."),
        );
      }
    },
    {
      hunk_count: state.renderModel.hunks.length,
      layout,
      line_count: state.renderModel.hunks.reduce((total, hunk) => total + hunk.lines.length, 0),
    },
  );
}

/**
 * Record synchronous projection work when the host profiler is present.
 * @template T
 * @param {DiffViewApi | undefined} api
 * @param {string} label
 * @param {() => T} work
 * @param {Record<string, unknown>} metadata
 * @returns {T}
 */
function measureProjection(api, label, work, metadata) {
  return api?.perf?.measure ? api.perf.measure(label, work, metadata) : work();
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
 * @param {() => "unified" | "split" | null} currentLayout `null` until a layout is drawn.
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
      () => (view.awaitingWidth ? null : view.layout),
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
 * @template T
 * @param {HTMLElement} group
 * @param {T[]} hiddenRows
 * @param {(row: T) => HTMLElement} renderRow
 * @param {FileViewState} state
 * @param {string} key
 * @returns {HTMLElement}
 */
function renderFoldControl(group, hiddenRows, renderRow, state, key) {
  let expanded = state.expandedFolds.has(key);
  const hidden = hiddenRows.length;
  const control = el("button", "fold-expander diff-fold-control");
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

  function cancelMaterialization() {
    const task = state.foldTasks.get(key);
    if (task) {
      clearTimeout(task.timer);
      state.foldTasks.delete(key);
    }
    state.textHosts = state.textHosts.filter(({ host }) => !group.contains(host));
    group.replaceChildren();
  }

  function scheduleMaterialization() {
    cancelMaterialization();
    let index = 0;
    const task = { timer: 0 };
    const appendBatch = () => {
      if (state.foldTasks.get(key) !== task || !state.expandedFolds.has(key)) {
        return;
      }
      const end = Math.min(index + FOLD_MATERIALIZATION_BATCH_ROWS, hiddenRows.length);
      group.append(...hiddenRows.slice(index, end).map(renderRow));
      index = end;
      if (index >= hiddenRows.length) {
        state.foldTasks.delete(key);
        return;
      }
      task.timer = setTimeout(appendBatch, 0);
    };
    task.timer = setTimeout(appendBatch, 0);
    state.foldTasks.set(key, task);
  }

  control.addEventListener("click", (event) => {
    // The bar above owns clicks on the file section; a fold is its own
    // control and must not also collapse the whole file.
    event.stopPropagation();
    expanded = !expanded;
    if (expanded) {
      state.expandedFolds.add(key);
      scheduleMaterialization();
    } else {
      state.expandedFolds.delete(key);
      cancelMaterialization();
    }
    control.setAttribute("aria-expanded", String(expanded));
    control.classList.toggle("expanded", expanded);
    group.classList.toggle("diff-fold-collapsed", !expanded);
    label.textContent = expanded
      ? `Hide ${hidden} line${hidden === 1 ? "" : "s"}`
      : `${hidden} more changed line${hidden === 1 ? "" : "s"}`;
  });
  if (expanded) {
    scheduleMaterialization();
  }
  return control;
}

/** @param {FileViewState} state */
function cancelFoldMaterializations(state) {
  for (const task of state.foldTasks.values()) {
    clearTimeout(task.timer);
  }
  state.foldTasks.clear();
}

/**
 * One View file control of a file bar: a link when the page already has the file's
 * address, and a button when following it first switches the served pin. The link has
 * no handler, so a click, a new tab, and a copied address are the browser's own. The
 * text is the application's; the path reaches only the tooltip and accessible name, as
 * text.
 *
 * @param {import("./diff-view-file.js").ViewFileAction} action
 * @param {MountedDiffState} view
 * @param {{element: HTMLElement, timer: number}} notice Where a refusal is said, under
 *   the bar.
 * @returns {HTMLElement}
 */
function renderViewFileControl(action, view, notice) {
  const opener = /** @type {NonNullable<MountedDiffState["viewFile"]>} */ (view.viewFile);
  const link = action.mode === "link";
  const control = el(link ? "a" : "button", `diff-file-view diff-file-view-${action.side}`);
  control.textContent = action.label;
  control.setAttribute("data-tip-text", action.detail);
  control.setAttribute("aria-label", `${action.label}: ${action.detail}`);
  if (link) {
    control.setAttribute("href", action.href);
    return control;
  }
  control.setAttribute("type", "button");
  control.addEventListener("click", () => {
    if (opener.switching()) {
      // Another control's switch is on its way: this click changes nothing, and that
      // control stays the busy one.
      return;
    }
    clearTimeout(notice.timer);
    view.timers.delete(notice.timer);
    notice.element.textContent = "";
    notice.element.hidden = true;
    control.setAttribute("aria-busy", "true");
    view.viewFileBusy = control;
    void opener.switchTo(action).then((outcome) => {
      if (outcome.kind === "navigated") {
        // The page is leaving; the control stays busy until it does, or until the
        // browser brings the page back (the opener's `released`).
        return;
      }
      control.setAttribute("aria-busy", "false");
      view.viewFileBusy = null;
      if (outcome.kind !== "refused") {
        return;
      }
      // A live region announces a change it was shown before: unhide it first, and
      // set its text in the next task.
      notice.element.hidden = false;
      notice.timer = setTimeout(() => {
        view.timers.delete(notice.timer);
        notice.element.textContent = outcome.message;
      }, 0);
      view.timers.add(notice.timer);
    });
  });
  return control;
}

/**
 * The per-file bar: one disclosure trigger (kind, path, notes, stats)
 * plus sibling View file and copy controls, per the section-disclosure
 * and icon button primitives in the design system.
 *
 * @param {Record<string, unknown>} change
 * @param {string} toggleId
 * @param {string} bodyId
 * @param {MountedDiffState} view
 * @returns {{bar: HTMLElement, toggle: HTMLElement, notice: HTMLElement | null}}
 */
function renderFileBar(change, toggleId, bodyId, view) {
  const api = view.api;
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

  /** @type {HTMLElement | null} */
  let notice = null;
  const actions = view.viewFile?.actions(change, view.resolved) ?? [];
  if (actions.length > 0) {
    notice = el("div", "diff-availability diff-file-notice");
    notice.setAttribute("role", "status");
    notice.hidden = true;
    const said = { element: notice, timer: 0 };
    for (const action of actions) {
      bar.append(renderViewFileControl(action, view, said));
    }
  }

  const side = /** @type {Record<string, unknown> | undefined} */ (change.new ?? change.old);
  if (side !== undefined) {
    const copy = el("button", "icon-btn icon-btn-reveal diff-file-copy");
    copy.setAttribute("type", "button");
    copy.setAttribute("data-mb-copy", "text");
    copy.setAttribute("data-mb-copy-text", String(side.path));
    copy.setAttribute("data-mb-copy-label", "Copy path");
    api?.ownDelegate?.(copy);
    copy.setAttribute("data-tip-text", "Copy path");
    copy.setAttribute("aria-label", "Copy path");
    const svg = shellIcon("copy");
    if (svg) {
      copy.innerHTML = svg;
    } else {
      copy.textContent = "⧉";
    }
    bar.append(copy);
  }
  return { bar, toggle, notice };
}

/** @param {DiffViewApi | undefined} api @returns {"unified" | "split"} */
export function readLayoutPreference(api) {
  const value = api?.prefs?.get("diff.layout", /** @type {unknown} */ ("split"));
  return value === "unified" ? "unified" : "split";
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

/**
 * Whether a diff *width* px wide is too narrow for Split, given what it was. Pure.
 *
 * @param {number} width
 * @param {number} fontSize The diff's text, in px.
 * @param {boolean} narrow
 */
export function tooNarrowForSplit(width, fontSize, narrow) {
  if (!(width > 0) || !(fontSize > 0)) {
    // Not laid out, as in a hidden tab: nothing is known, so nothing changes.
    return narrow;
  }
  const needs = SPLIT_MIN_WIDTH_EM * fontSize + FILE_BORDER_PX;
  return width < (narrow ? needs + SPLIT_RETURN_MARGIN_PX : needs);
}

/**
 * The first decision, with no earlier one to hold it. A width within the return margin of
 * the limit counts as narrow, because a pane has no scrollbar until what is drawn brings
 * one: measured 2026-11-02 in Chrome 152, Files changed with its root resting at 617 px
 * measured 628 at mount, and drew Split to throw it away. An unknown width is not narrow,
 * which is what a browserless caller gets. Pure.
 *
 * @param {number} width
 * @param {number} fontSize The diff's text, in px.
 */
export function opensTooNarrowForSplit(width, fontSize) {
  return width > 0 && fontSize > 0 && tooNarrowForSplit(width, fontSize, true);
}

/**
 * What a diff draws: the reader's choice, except Split where it does not fit, unless the
 * reader chose it there. Pure.
 *
 * @param {"unified" | "split"} chosen
 * @param {boolean} narrow
 * @param {boolean} insisted
 * @returns {"unified" | "split"}
 */
export function drawnLayout(chosen, narrow, insisted) {
  return chosen === "split" && narrow && !insisted ? "unified" : chosen;
}

/** @param {HTMLElement} element */
function fontSizeOf(element) {
  return typeof getComputedStyle === "function"
    ? Number.parseFloat(getComputedStyle(element).fontSize)
    : 0;
}

/** @param {MountedDiffState} view */
function renderLayoutControl(view) {
  const control = view.layoutControl;
  const filterControls = view.api?.filterControls;
  if (!control || !filterControls) {
    return;
  }
  // The control shows what the diff draws. While Split does not fit that is Unified, and
  // the reader's choice waits in `chosenLayout`, so Split says why it is not selected.
  const fellBack = view.chosenLayout === "split" && view.layout === "unified";
  control.innerHTML = filterControls.groupHtml({
    key: "diff-layout",
    label: "Diff layout",
    layout: "joined",
    options: [
      { label: "Split", value: "split", ...(fellBack ? { tip: SPLIT_TOO_NARROW_TIP } : {}) },
      { label: "Unified", value: "unified" },
    ],
    select: "one",
    value: view.layout,
  });
}

/**
 * The reader's choice: draw it, and optionally persist it. Choosing Split where it does not
 * fit gets Split, with its sideways scroll, until the diff has room and loses it again.
 * Choosing what is already drawn changes nothing, so Unified chosen while Split does not
 * fit leaves Split the choice for when it does.
 *
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
  view.chosenLayout = layout;
  view.insistedOnSplit = layout === "split" && view.narrow;
  if (persist) {
    view.api?.prefs?.set("diff.layout", layout);
  }
  drawLayout(view, layout);
}

/**
 * The diff's width changed: draw what now fits. The reader's choice is not touched.
 *
 * The pane keeps its pixel `scrollTop` through the redraw, as it does through the control,
 * and Unified is taller than Split, so a long diff moves under the reader: measured in
 * Chrome 152 on 10 files, a reader 3,744 px into a file was 5,029 px into it after narrowing
 * and stayed there after widening. Accepted: keeping the line would need an anchor both
 * layouts share, across a projection that runs in batches above 100 files.
 *
 * @param {MountedDiffState} view
 * @param {number} width
 */
function fitLayout(view, width) {
  if (view.disposed) {
    return;
  }
  const narrow = tooNarrowForSplit(width, fontSizeOf(view.root), view.narrow);
  if (narrow === view.narrow) {
    return;
  }
  view.narrow = narrow;
  view.insistedOnSplit = view.insistedOnSplit && narrow;
  const layout = drawnLayout(view.chosenLayout, narrow, view.insistedOnSplit);
  if (layout !== view.layout) {
    drawLayout(view, layout);
  }
}

/**
 * Reproject cached file state.
 *
 * @param {MountedDiffState} view
 * @param {"unified" | "split"} layout
 */
function drawLayout(view, layout) {
  view.awaitingWidth = false;
  view.layout = layout;
  view.root.dataset.layout = layout;
  renderLayoutControl(view);
  view.notifyCurrentFile();
  for (const file of view.deferred.values()) {
    reserveFileBody(file, layout);
  }
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
 * @param {boolean} showSummary
 * @returns {{toolbar: HTMLElement, unbind: () => void}}
 */
function renderDiffToolbar(totals, view, showSummary) {
  const toolbar = el("div", "diff-toolbar");
  if (showSummary && Number(totals.files) !== 1) {
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
 * What the reader is told while a comparison's files are not all here. A deferred file looks
 * like a collapsed one until it comes near, so a page that does not say so reads as complete,
 * and a file that could not be loaded is not counted as loaded. Null once nothing is deferred
 * and nothing failed. Pure.
 *
 * @param {number} deferred
 * @param {number} total
 * @param {number} [failed]
 * @returns {string | null}
 */
export function partialNote(deferred, total, failed = 0) {
  if (deferred <= 0 && failed <= 0) {
    return null;
  }
  const count = (/** @type {number} */ n) => n.toLocaleString("en-US");
  const loaded = `${count(total - deferred - failed)} of ${count(total)} files loaded`;
  const rest = deferred > 0 ? "; the rest load as you reach them" : "";
  const lost = failed > 0 ? `; ${count(failed)} could not be loaded` : "";
  return `${loaded}${lost}${rest}`;
}

/** @param {MountedDiffState} view */
function renderPartialNote(view) {
  const note = view.partialNote;
  if (note === null) {
    return;
  }
  const text = partialNote(view.deferredLeft, view.fileTotal, view.deferredFailed);
  note.textContent = text ?? "";
  note.hidden = text === null;
}

// ── Which deferred file is asked for next ───────────────────────
//
// A large comparison's files past its first page are bars with no lines until a reader reaches
// them. This decides when each is requested and rendered, and owns no DOM, so
// tests/dom/diff-file-jump-session.js runs it with a scripted clock. It is here and not in a
// module of its own because a served folder's first diff requests the modules v0.11.0 did,
// which tests/test_diff_view_file_session.py holds.
//
// - One request at a time. On a store the route answers a file in tens of milliseconds from
//   its kept manifest, so a second one buys nothing, and a viewport that shows several bars
//   would otherwise fan out. On a folder nothing is kept, so each file costs the manifest
//   run again (about 0.7 s at 1,183 files, measured in the adapter), one after the other,
//   which is still ahead of the two-at-a-time whole-patch runs it replaced.
// - At most one file rendered per frame: the next request starts only after the frame
//   that rendered the last, so input is never waiting behind rendering it caused.
// - The file a reader jumped to is first, ahead of anything else, and latest wins: a jump
//   cancels the request for anything else, and a request for a file that left the viewport
//   is cancelled too, because the reader did not ask for the files they passed.
// - A jump after a quiet moment asks at once. A jump during a burst, which is a held key, waits
//   until the burst stops, so a key held through ninety files asks for the one it rests on.

// How long a burst of jumps has to stop before the file it rests on is asked for. A key held
// down repeats about every 33 ms, so this is past one repeat, and it is what's left of the lines
// budget of 150 ms after a request of 13 to 30 ms and a frame of 16 ms.
export const JUMP_QUIET_MS = 50;

/**
 * @typedef {"painted" | "none" | "failed" | "superseded"} JumpOutcome
 *   What became of a jump's lines: on the page, none to show, the request failed, or another
 *   jump came first.
 *
 * @typedef {{
 *   load(id: string, signal: AbortSignal): Promise<unknown>,
 *   render(id: string, payload: unknown): JumpOutcome,
 *   fail(id: string, error: unknown): void,
 *   abandon(id: string): void,
 *   frame(callback: () => void): unknown,
 *   cancelFrame(handle: unknown): void,
 *   after(delayMs: number, callback: () => void): unknown,
 *   cancelAfter(handle: unknown): void,
 *   now(): number,
 * }} HydrationDependencies
 *
 * @typedef {{id: string, index: number, state: "pending" | "loading" | "done"}} HydrationEntry
 */

/**
 * @param {HydrationDependencies} deps
 */
export function createHydrationScheduler(deps) {
  /** @type {Map<string, HydrationEntry>} */
  const entries = new Map();
  /** The pending entries the viewport shows. @type {Set<HydrationEntry>} */
  const visible = new Set();
  /**
   * The request in flight. A request, not its file: an abandoned request's rejection
   * arrives after its file may have been asked for again, and must not answer for the
   * new request.
   *
   * @type {{entry: HydrationEntry, controller: AbortController} | null}
   */
  let active = null;
  /** A request that answered, waiting for its frame. @type {{entry: HydrationEntry, frame: unknown} | null} */
  let arrived = null;
  /** @type {{entry: HydrationEntry, settle: (outcome: JumpOutcome) => void} | null} */
  let target = null;
  /** @type {unknown} */
  let quietTimer = null;
  let lastJumpAt = Number.NEGATIVE_INFINITY;
  let requests = 0;
  let disposed = false;

  /** @param {JumpOutcome} outcome */
  function settleTarget(outcome) {
    if (target !== null) {
      target.settle(outcome);
      target = null;
    }
  }

  function clearQuiet() {
    if (quietTimer !== null) {
      deps.cancelAfter(quietTimer);
      quietTimer = null;
    }
  }

  /** Forget the request or the answer in hand, and leave its file to be asked for again. */
  function abandonWork() {
    if (active !== null) {
      const { entry, controller } = active;
      active = null;
      entry.state = "pending";
      controller.abort();
      deps.abandon(entry.id);
    }
    if (arrived !== null) {
      const { entry, frame } = arrived;
      arrived = null;
      entry.state = "pending";
      deps.cancelFrame(frame);
      deps.abandon(entry.id);
    }
  }

  /** @param {HydrationEntry} entry */
  function begin(entry) {
    const controller = new AbortController();
    entry.state = "loading";
    const ticket = { entry, controller };
    active = ticket;
    requests += 1;
    deps.load(entry.id, controller.signal).then(
      (payload) => {
        if (active !== ticket) {
          return;
        }
        active = null;
        arrived = {
          entry,
          frame: deps.frame(() => {
            arrived = null;
            entry.state = "done";
            visible.delete(entry);
            /** @type {JumpOutcome} */
            let outcome = "failed";
            try {
              outcome = deps.render(entry.id, payload);
            } catch (error) {
              // One file's render is one file's: the next is still asked for.
              deps.fail(entry.id, error);
            } finally {
              if (target?.entry === entry) {
                settleTarget(outcome);
              }
              pump();
            }
          }),
        };
      },
      (error) => {
        if (active !== ticket) {
          return;
        }
        active = null;
        if (isAbortError(error)) {
          // Not an answer: the file is asked for again when it is next needed.
          entry.state = "pending";
          pump();
          return;
        }
        entry.state = "done";
        visible.delete(entry);
        deps.fail(entry.id, error);
        if (target?.entry === entry) {
          settleTarget("failed");
        }
        pump();
      },
    );
  }

  /** The topmost file the viewport shows. @returns {HydrationEntry | null} */
  function nextVisible() {
    /** @type {HydrationEntry | null} */
    let best = null;
    for (const entry of visible) {
      if (entry.state === "pending" && (best === null || entry.index < best.index)) {
        best = entry;
      }
    }
    return best;
  }

  function pump() {
    if (disposed || active !== null || arrived !== null || quietTimer !== null) {
      return;
    }
    if (target !== null) {
      begin(target.entry);
      return;
    }
    const quietLeft = lastJumpAt + JUMP_QUIET_MS - deps.now();
    if (quietLeft > 0) {
      quietTimer = deps.after(quietLeft, () => {
        quietTimer = null;
        pump();
      });
      return;
    }
    const entry = nextVisible();
    if (entry !== null) {
      begin(entry);
    }
  }

  return Object.freeze({
    /**
     * @param {string} id
     * @param {number} index The file's place in the comparison.
     */
    add(id, index) {
      entries.set(id, { id, index, state: "pending" });
    },
    /**
     * The viewport began or stopped showing a file.
     *
     * @param {string} id
     * @param {boolean} shown
     */
    setVisible(id, shown) {
      const entry = entries.get(id);
      if (disposed || entry === undefined || entry.state === "done") {
        return;
      }
      if (shown) {
        visible.add(entry);
      } else {
        visible.delete(entry);
        // A request for a file that left is cancelled; an answer already in hand is
        // rendered, since fetching it again would cost more than its one frame.
        if (active?.entry === entry && target?.entry !== entry) {
          abandonWork();
        }
      }
      pump();
    },
    /**
     * The reader asked for this file. Whatever else is under way stops.
     *
     * @param {string} id
     * @returns {Promise<JumpOutcome> | null} Its lines' outcome, or null for a file that has
     *   nothing left to ask for.
     */
    jump(id) {
      if (disposed) {
        return null;
      }
      const quiet = deps.now() - lastJumpAt >= JUMP_QUIET_MS;
      lastJumpAt = deps.now();
      settleTarget("superseded");
      clearQuiet();
      const entry = entries.get(id);
      const working = active?.entry ?? arrived?.entry ?? null;
      if (working !== null && working !== entry) {
        abandonWork();
      }
      if (entry === undefined || entry.state === "done") {
        pump();
        return null;
      }
      /** @type {Promise<JumpOutcome>} */
      const lines = new Promise((settle) => {
        target = { entry, settle };
      });
      if (entry.state === "pending") {
        if (quiet) {
          begin(entry);
        } else {
          quietTimer = deps.after(JUMP_QUIET_MS, () => {
            quietTimer = null;
            pump();
          });
        }
      }
      return lines;
    },
    dispose() {
      disposed = true;
      clearQuiet();
      abandonWork();
      settleTarget("superseded");
      visible.clear();
    },
    snapshot: () => ({
      asking: active?.entry.id ?? null,
      rendering: arrived?.entry.id ?? null,
      target: target?.entry.id ?? null,
      visible: [...visible].map((entry) => entry.id),
      requests,
    }),
  });
}

/** @param {unknown} error */
function isAbortError(error) {
  return (
    typeof error === "object" &&
    error !== null &&
    /** @type {{name?: unknown}} */ (error).name === "AbortError"
  );
}

/**
 * Rows a deferred file should reserve until it arrives. An estimate from the manifest's line
 * counts, in the layout it will draw: a long run folds to its visible rows, and a change on
 * both sides has context around it. Pure.
 *
 * @param {Record<string, unknown>} change
 * @param {"unified" | "split"} layout
 */
export function reservedRows(change, layout) {
  const adds = Number(change.additions ?? 0);
  const dels = Number(change.deletions ?? 0);
  const changed = layout === "split" ? Math.max(adds, dels) : adds + dels;
  const shown = FOLD_THRESHOLD > 0 && changed > FOLD_THRESHOLD ? FOLD_VISIBLE + 1 : changed;
  const context = adds > 0 && dels > 0 ? 6 : 0;
  return shown + context + 1;
}

/**
 * Rows a patch in hand draws in *layout*, before intraline pairing: a header per hunk, a row
 * per context line, and each changed run its rows, or its visible rows and the fold control
 * when it folds. Exact for what the mount would draw, so a ready file it holds back reserves
 * its own height. Pure.
 *
 * @param {Record<string, unknown>} patch
 * @param {"unified" | "split"} layout
 */
export function patchRows(patch, layout) {
  let rows = patch.truncated ? 1 : 0;
  for (const hunk of /** @type {{lines?: {op?: unknown}[]}[]} */ (patch.hunks ?? [])) {
    rows += 1;
    let adds = 0;
    let dels = 0;
    const endRun = () => {
      const run = layout === "split" ? Math.max(adds, dels) : adds + dels;
      rows += FOLD_THRESHOLD > 0 && run > FOLD_THRESHOLD ? FOLD_VISIBLE + 1 : run;
      adds = 0;
      dels = 0;
    };
    for (const line of hunk.lines ?? []) {
      if (line.op === "context") {
        endRun();
        rows += 1;
      } else if (line.op === "add") {
        adds += 1;
      } else {
        dels += 1;
      }
    }
    endRun();
  }
  return rows;
}

/**
 * How far below the diff's top the mount draws rows: what the pane shows of the diff, and one
 * screen more, so the first scroll finds lines and not reserved space. Infinite where nothing
 * was measured, so a diff mounted where nothing is laid out draws every ready file at once, as
 * it always did. Pure.
 *
 * @param {ScreenGeometry | null} screen
 */
export function firstScreenBudget(screen) {
  if (screen === null) {
    return Number.POSITIVE_INFINITY;
  }
  const shown = Math.max(0, screen.paneHeight - Math.max(0, screen.rootTop));
  return shown + screen.paneHeight;
}

/**
 * Hold a file's place on the page until its lines arrive, so what they push down is the
 * difference between this estimate and the truth and not a whole file.
 *
 * @param {HTMLElement} body
 * @param {number} rows
 */
function reserveBody(body, rows) {
  if (body.style) {
    // The rows' own height: `line-height: 1.5` at the code font's size, in styles.css.
    body.style.setProperty(
      "--diff-reserved-height",
      `calc(${rows} * 1.5 * var(--code-font-size, 0.85rem))`,
    );
  }
}

/**
 * Reserve the rows this file will draw in the current layout. Held answers use
 * their patch; a file not fetched yet uses the manifest estimate.
 * @param {DeferredFile} file
 * @param {"unified" | "split"} layout
 */
function reserveFileBody(file, layout) {
  reserveBody(
    file.body,
    file.held === null
      ? reservedRows(file.change, layout)
      : patchRows(file.held.patches[String(file.change.id)], layout),
  );
}

/** @param {HTMLElement} body */
function unreserveBody(body) {
  if (body.style) {
    body.style.removeProperty("--diff-reserved-height");
  }
}

/** @param {DeferredFile} file */
function deferredPath(file) {
  const side = /** @type {Record<string, unknown> | undefined} */ (
    file.change.new ?? file.change.old
  );
  return String(side?.path ?? "");
}

/**
 * Resolve after the next frame, or reject as aborted when *signal* is, cancelling the frame.
 * Immediate where there are no frames.
 *
 * @param {AbortSignal} signal
 * @returns {Promise<void>}
 */
function afterNextFrame(signal) {
  return new Promise((resolve, reject) => {
    if (typeof requestAnimationFrame !== "function") {
      resolve();
      return;
    }
    /** @type {number} */
    let handle = 0;
    const stop = () => {
      cancelAnimationFrame(handle);
      reject(new DOMException("The jump moved on.", "AbortError"));
    };
    handle = requestAnimationFrame(() => {
      signal.removeEventListener("abort", stop);
      resolve();
    });
    signal.addEventListener("abort", stop, { once: true });
  });
}

/**
 * Ask for one deferred file, behind the standard progress box. A file whose answer is in hand
 * is not asked for. When it is the file a jump put at the top, it waits one frame first, so the
 * frame that shows its bar there is not also the one that draws its rows: drawn in the same
 * frame, a jump to a held file showed its bar in 49 to 54 ms on a 1,031-file comparison and in
 * 137 ms on a 1,627-file one, against a budget of 50 (2026-11-03, Chrome 152, load 8 to 21).
 *
 * @param {DeferredFile} file
 * @param {AbortSignal} signal
 * @param {MountedDiffState} view
 * @returns {Promise<OneFileAnswer>}
 */
async function loadDeferred(file, signal, view) {
  if (file.held !== null) {
    if (view.pinned === file.section) {
      await afterNextFrame(signal);
    }
    return file.held;
  }
  const path = deferredPath(file);
  file.box = progressBox(`Loading the diff for ${path}`);
  file.body.append(file.box);
  file.startedAt = Date.now();
  const generation = view.generation;
  file.slow = setTimeout(() => {
    if (mountIsCurrent(view, generation)) {
      reportLoad("file hydration", {
        revision: file.revision,
        path,
        elapsedMs: Date.now() - file.startedAt,
      });
    }
  }, SLOW_LOAD_MS);
  const payload = await loadOneChange(file.revision, path, { signal });
  const result = validateDocument(payload);
  if (!result.ok) {
    throw new Error(`invalid document: ${result.error}`);
  }
  return /** @type {OneFileAnswer} */ (result.document);
}

/** @param {DeferredFile} file */
function stopLoading(file) {
  if (file.slow !== null) {
    clearTimeout(file.slow);
    file.slow = null;
  }
  file.box?.remove();
  file.box = null;
}

/**
 * A deferred file is no longer waited for: it arrived or it failed. A file whose answer was in
 * hand was loaded all along, so it was never counted as one still to load.
 *
 * @param {DeferredFile} file
 * @param {MountedDiffState} view
 */
function settleDeferred(file, view) {
  stopLoading(file);
  unreserveBody(file.body);
  if (file.held === null) {
    view.deferredLeft -= 1;
  }
  renderPartialNote(view);
  view.hydrationObserver?.unobserve(file.section);
  view.deferred.delete(String(file.change.id));
  view.deferredBySection.delete(file.section);
  if (view.deferred.size === 0) {
    view.hydrationObserver?.disconnect();
    view.hydrationObserver = null;
  }
}

/**
 * Splice an answer in. Runs in its own frame, and what the reader is looking at stays where it
 * is: a jump's file, or the first file at the top of the pane.
 *
 * @param {DeferredFile} file
 * @param {OneFileAnswer} loaded
 * @param {MountedDiffState} view
 * @returns {JumpOutcome}
 */
function renderDeferred(file, loaded, view) {
  const anchor = view.pinned === null ? placeOfTopFile(view) : null;
  settleDeferred(file, view);
  /** @type {JumpOutcome} */
  let outcome;
  try {
    outcome = spliceDeferred(file, loaded, view);
  } catch (error) {
    // The file is settled, so its failure is its own to show and count: the scheduler's
    // own failure path looks the file up by id and would find nothing (review of #284, D4).
    outcome = failDeferred(file, error, view);
  }
  holdPlace(view, anchor);
  view.notifyCurrentFile();
  return outcome;
}

/**
 * What a settled file's answer puts in its body.
 *
 * @param {DeferredFile} file
 * @param {OneFileAnswer} loaded
 * @param {MountedDiffState} view
 * @returns {JumpOutcome}
 */
function spliceDeferred(file, loaded, view) {
  const only = loaded.manifest.files[0];
  const patch = only ? loaded.patches[String(only.id)] : undefined;
  const availability = only ? String(only.availability) : "";
  const reason =
    availability === "deferred" ? DEFERRED_AGAIN_COPY : AVAILABILITY_COPY[availability];
  if (only && patch === undefined && reason) {
    // The server looked and has a reason: a file past the bound of one patch.
    file.body.append(el("div", "diff-availability", reason));
    return "none";
  }
  if (!only || patch === undefined) {
    return failDeferred(file, new Error("the comparison returned no hunks for this file"), view);
  }
  if (/** @type {unknown[]} */ (patch.hunks).length === 0) {
    file.body.append(el("div", "diff-availability", "No content changes."));
    return "none";
  }
  const state = createFileState(only, patch, view.api ?? plainSyntaxApi(), file.body);
  if (!view.awaitingWidth) {
    renderFileBody(state, view.layout);
  }
  // Only a file whose rows are in the page is a file of the view: one whose render threw
  // would throw again at every relayout.
  view.files.push(state);
  scheduleFileEnhancement(view, state);
  return "painted";
}

/**
 * @param {DeferredFile} file
 * @param {unknown} error
 * @param {MountedDiffState} [view] Counts the failure apart from the loads, when the file
 *   was settled by `settleDeferred` and not by `renderDeferred`.
 * @returns {JumpOutcome}
 */
function failDeferred(file, error, view) {
  if (view !== undefined) {
    view.deferredFailed += 1;
    renderPartialNote(view);
  }
  reportLoad(
    "file hydration",
    {
      revision: file.revision,
      path: deferredPath(file),
      hook: "diff/comparison",
      elapsedMs: Date.now() - file.startedAt,
    },
    error,
  );
  file.body.append(el("div", "diff-availability", "Could not load this file's changes."));
  return "failed";
}

/**
 * Defer one file request until its section reaches the visible scroll area.
 * The comparison payload already hydrates the leading files; observing the
 * remainder prevents a large commit from launching an unbounded request fanout.
 *
 * A ready file past the first screen takes the same path with its answer in *held*: it is
 * drawn when it is reached or gone to, one file a frame like the rest, and never asked for.
 *
 * @param {HTMLElement} section
 * @param {HTMLElement} body
 * @param {Record<string, unknown>} change
 * @param {string} revision
 * @param {MountedDiffState} view
 * @param {OneFileAnswer | null} [held]
 */
function queueDeferredHydration(section, body, change, revision, view, held = null) {
  const id = String(change.id);
  view.deferred.set(id, {
    body,
    box: null,
    change,
    held,
    revision,
    section,
    slow: null,
    startedAt: 0,
  });
  view.deferredBySection.set(section, id);
  view.hydration.add(id, view.deferred.size);
  reserveFileBody(/** @type {DeferredFile} */ (view.deferred.get(id)), view.layout);
  if (view.hydrationObserver === null) {
    view.hydrationObserver = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        const shown = view.deferredBySection.get(/** @type {HTMLElement} */ (entry.target));
        if (shown !== undefined && !view.disposed && !view.controller.signal.aborted) {
          view.hydration.setVisible(shown, entry.isIntersecting);
        }
      }
    });
  }
  view.hydrationObserver.observe(section);
}

/**
 * What runs a view's hydration in a browser: its frames and its timers.
 *
 * @param {MountedDiffState} view
 * @returns {HydrationDependencies}
 */
function hydrationHost(view) {
  /** @param {string} id */
  const fileOf = (id) => /** @type {DeferredFile} */ (view.deferred.get(id));
  return {
    load: (id, signal) => loadDeferred(fileOf(id), signal, view),
    render: (id, payload) =>
      renderDeferred(
        fileOf(id),
        /** @type {Parameters<typeof renderDeferred>[1]} */ (payload),
        view,
      ),
    fail(id, error) {
      const file = view.deferred.get(id);
      if (file === undefined) {
        // Settled already: `renderDeferred` owns a throw past `settleDeferred` and has
        // counted and said it, so this is the one its own message could not be appended
        // for. Nothing is settled twice, and the frame it runs in ends clean.
        reportLoad("file hydration", { fileId: id, hook: "diff/comparison" }, error);
        return;
      }
      settleDeferred(file, view);
      failDeferred(file, error, view);
    },
    abandon: (id) => stopLoading(fileOf(id)),
    frame: (callback) =>
      typeof requestAnimationFrame === "function"
        ? requestAnimationFrame(callback)
        : setTimeout(callback, 0),
    cancelFrame(handle) {
      if (typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(/** @type {number} */ (handle));
      } else {
        clearTimeout(/** @type {ReturnType<typeof setTimeout>} */ (handle));
      }
    },
    after: (delayMs, callback) => setTimeout(callback, delayMs),
    cancelAfter: (handle) => clearTimeout(/** @type {ReturnType<typeof setTimeout>} */ (handle)),
    now: () => Date.now(),
  };
}

// ── Going to a file ─────────────────────────────────────────────

/** The element that scrolls this diff. @param {MountedDiffState} view */
function scrollerOf(view) {
  return /** @type {HTMLElement | null} */ (
    view.root.closest?.("[data-kpress-viewport]") ??
      view.root.ownerDocument?.scrollingElement ??
      null
  );
}

/**
 * Where a jump puts the pane, and the room past the last file it takes for the target to
 * reach the top. Pure. Tops and bottoms are in the viewport's coordinates, and *contentBottom*
 * is the end of the diff without any room already added.
 *
 * @param {{paneTop: number, paneHeight: number, scrollTop: number, targetTop: number, contentBottom: number}} geometry
 * @returns {{scrollTop: number, spacer: number}}
 */
export function jumpPlacement({ paneTop, paneHeight, scrollTop, targetTop, contentBottom }) {
  return {
    scrollTop: scrollTop + targetTop - paneTop,
    spacer: Math.max(0, paneHeight - (contentBottom - targetTop)),
  };
}

/**
 * Put a file at the top of the pane, with no smooth scroll, and room below it if it is near
 * the end. Room rather than a smaller scroll, because a file that cannot reach the top is
 * pushed off the screen by the files above it filling in: 53,661 px, measured 2026-11-02
 * on a comparison of 1,183 files, whatever the browser's scroll anchoring holds.
 *
 * @param {MountedDiffState} view
 * @param {HTMLElement} section
 */
function placeAtTop(view, section) {
  const pane = scrollerOf(view);
  const spacer = view.spacer;
  if (pane === null || spacer === null) {
    return;
  }
  const paneRect = pane.getBoundingClientRect();
  const place = jumpPlacement({
    paneTop: paneRect.top,
    paneHeight: pane.clientHeight,
    scrollTop: pane.scrollTop,
    targetTop: section.getBoundingClientRect().top,
    contentBottom: view.root.getBoundingClientRect().bottom - spacer.getBoundingClientRect().height,
  });
  spacer.style.height = `${place.spacer}px`;
  pane.scrollTop = place.scrollTop;
}

/**
 * The first file at the top of the pane and where it is, for a change that should not move it.
 * Found by bisection, since the sections are in order: ten reads at 1,183 files.
 *
 * @param {MountedDiffState} view
 * @returns {{section: HTMLElement, top: number} | null}
 */
function placeOfTopFile(view) {
  const pane = scrollerOf(view);
  if (pane === null || view.sections.length === 0) {
    return null;
  }
  const paneTop = pane.getBoundingClientRect().top;
  let low = 0;
  let high = view.sections.length - 1;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (view.sections[middle].getBoundingClientRect().bottom > paneTop) {
      high = middle;
    } else {
      low = middle + 1;
    }
  }
  const section = view.sections[low];
  return { section, top: section.getBoundingClientRect().top };
}

/**
 * The page changed height: put back what the reader was looking at. A browser's scroll
 * anchoring usually has, and this measures rather than assumes, so it adds nothing to that
 * and holds in a browser without it.
 *
 * @param {MountedDiffState} view
 * @param {{section: HTMLElement, top: number} | null} [anchor]
 */
function holdPlace(view, anchor = null) {
  if (view.pinned !== null) {
    placeAtTop(view, view.pinned);
    return;
  }
  if (anchor !== null) {
    const pane = scrollerOf(view);
    const moved = anchor.section.getBoundingClientRect().top - anchor.top;
    if (pane !== null && Math.abs(moved) >= 0.5) {
      pane.scrollTop += moved;
    }
  }
}

/**
 * From the reader's own move on, the place is theirs. Only input says so: a browser's scroll
 * anchoring and this view's own corrections move the pane too.
 *
 * @param {MountedDiffState} view
 * @param {HTMLElement} pane
 */
function releasePinOnInput(view, pane) {
  if (view.pinListeners !== null) {
    return;
  }
  const listening = new AbortController();
  view.pinListeners = listening;
  const options = { capture: true, passive: true, signal: listening.signal };
  /** @param {{timeStamp?: number}} [event] */
  const release = (event) => {
    // The key that caused a jump is older than the pin it would release: a list's own
    // handler may run before or after this one, and the pin holds either way. A key
    // pressed after the jump releases it.
    if (typeof event?.timeStamp === "number" && event.timeStamp < view.pinnedAt) {
      return;
    }
    view.pinned = null;
  };
  for (const type of ["wheel", "touchstart", "pointerdown"]) {
    pane.addEventListener(type, release, options);
  }
  pane.ownerDocument?.defaultView?.addEventListener("keydown", release, options);
}

/**
 * The file a path names: what it is called now, which is what GitHub's list of a pull request's
 * files gives as `filename`, or else what it was called, its `previous_filename`.
 *
 * @param {MountedDiffState} view
 * @param {string} path
 */
function fileEntryForPath(view, path) {
  return view.byNewPath.get(path) ?? view.byOldPath.get(path) ?? null;
}

/** The clock an event's `timeStamp` is on, where there is one. */
function eventClockNow() {
  return typeof performance === "object" && typeof performance.now === "function"
    ? performance.now()
    : Date.now();
}

/**
 * Whether this comparison holds a path, for a list of files from elsewhere, without moving
 * anything. Typed as `scrollToFile`'s answer is, so a list can tell a file the comparison
 * lacks from one it holds.
 *
 * @param {MountedDiffState} view
 * @param {string} path
 * @returns {FileLookup}
 */
export function lookupFile(view, path) {
  const entry = fileEntryForPath(view, path);
  if (entry === null) {
    return { kind: "not_in_comparison", path, listTruncated: view.listTruncated };
  }
  return {
    kind: "file",
    path,
    fileId: String(entry.change.id),
    changeKind: String(entry.change.kind),
    availability: String(entry.change.availability),
  };
}

/**
 * Go to one file of this diff, at the top of the pane, and ask for its lines first.
 *
 * @param {MountedDiffState} view
 * @param {string} path
 * @returns {FileJump}
 */
export function jumpToFile(view, path) {
  if (view.disposed) {
    return { kind: "disposed", path };
  }
  const entry = fileEntryForPath(view, path);
  if (entry === null) {
    return { kind: "not_in_comparison", path, listTruncated: view.listTruncated };
  }
  entry.expand();
  view.pinned = entry.section;
  view.pinnedAt = eventClockNow();
  placeAtTop(view, entry.section);
  view.notifyCurrentFile();
  const pane = scrollerOf(view);
  if (pane !== null) {
    releasePinOnInput(view, pane);
  }
  const fileId = String(entry.change.id);
  const lines = view.hydration.jump(fileId);
  const availability = String(entry.change.availability);
  return {
    kind: "jumped",
    fileId,
    path,
    availability,
    lines:
      lines ?? Promise.resolve(entry.section.querySelector?.(".diff-hunk") ? "painted" : "none"),
  };
}

/**
 * Keep a file findable by either of its paths. A path a file has now wins over a path another
 * had: a copy's source can be a file changed in its own right.
 *
 * @param {MountedDiffState} view
 * @param {Record<string, unknown>} change
 * @param {HTMLElement} section
 * @param {() => void} expand
 */
function rememberFile(view, change, section, expand) {
  const entry = { change, section, expand };
  view.sections.push(section);
  view.bySection.set(section, entry);
  const oldSide = /** @type {{path?: string} | undefined | null} */ (change.old);
  const newSide = /** @type {{path?: string} | undefined | null} */ (change.new);
  if (newSide?.path !== undefined && !view.byNewPath.has(newSide.path)) {
    view.byNewPath.set(newSide.path, entry);
  }
  if (oldSide?.path !== undefined && !view.byOldPath.has(oldSide.path)) {
    view.byOldPath.set(oldSide.path, entry);
  }
}

/**
 * @param {Record<string, unknown>} change
 * @param {Record<string, unknown> | undefined} patch
 * @param {{revision?: string}} context
 * @param {MountedDiffState} view
 * @param {boolean} draw Whether a ready file's rows are drawn now. One past the first screen
 *   is held, with its answer, until it is reached.
 * @returns {HTMLElement}
 */
function renderFileSection(change, patch, context, view, draw) {
  sectionSequence += 1;
  const toggleId = `diff-file-toggle-${sectionSequence}`;
  const bodyId = `diff-file-body-${sectionSequence}`;
  const section = el("section", "diff-file");
  section.setAttribute("aria-labelledby", toggleId);
  const { bar, toggle, notice } = renderFileBar(change, toggleId, bodyId, view);
  const body = el("div", "diff-file-body");
  body.setAttribute("id", bodyId);
  if (notice) {
    section.append(bar, notice, body);
  } else {
    section.append(bar, body);
  }

  // The whole bar is one activation surface, like a tree row; the
  // button stays the semantic trigger for focus and keyboard, whose
  // synthesized click bubbles here. Only the copy and View file
  // controls opt out.
  let expanded = true;
  /** @param {boolean} next */
  const setExpanded = (next) => {
    expanded = next;
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.classList.toggle("expanded", expanded);
    toggle.classList.toggle("collapsed", !expanded);
    body.classList.toggle("diff-file-body-collapsed", !expanded);
    section.classList.toggle("diff-file-collapsed", !expanded);
    view.notifyCurrentFile();
  };
  bar.addEventListener("click", (event) => {
    const origin = /** @type {{closest?: (selector: string) => unknown}} */ (event.target);
    if (
      typeof origin?.closest === "function" &&
      (origin.closest("[data-mb-copy]") || origin.closest(".diff-file-view"))
    ) {
      return;
    }
    setExpanded(!expanded);
  });
  rememberFile(view, change, section, () => {
    if (!expanded) {
      setExpanded(true);
    }
  });

  const availability = String(change.availability);
  if (availability === "deferred" && context.revision) {
    queueDeferredHydration(section, body, change, context.revision, view);
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
  if (!draw) {
    const id = String(change.id);
    const held = { manifest: { files: [change] }, patches: { [id]: patch } };
    queueDeferredHydration(section, body, change, context.revision ?? "", view, held);
    return section;
  }
  const state = createFileState(change, patch, view.api ?? plainSyntaxApi(), body);
  view.files.push(state);
  if (!view.awaitingWidth) {
    renderFileBody(state, view.layout);
  }
  scheduleFileEnhancement(view, state);
  return section;
}

/**
 * The rows a file's body takes or holds a place for, in *layout*, by the same rules that draw
 * or reserve it: a ready file's own patch, a deferred file's estimate, and one row for a
 * sentence. Pure.
 *
 * @param {Record<string, unknown>} change
 * @param {Record<string, unknown> | undefined} patch
 * @param {{revision?: string}} context
 * @param {"unified" | "split"} layout
 */
function bodyRows(change, patch, context, layout) {
  const availability = String(change.availability);
  if (availability === "deferred" && context.revision) {
    return reservedRows(change, layout);
  }
  if (availability === "ready" && patch !== undefined) {
    return Math.max(1, patchRows(patch, layout));
  }
  return 1;
}

/**
 * Two empty files of one row each, for measuring what a bar and a row take before anything is
 * drawn. The root holds them for the measurement alone.
 */
function screenProbe() {
  const probe = el("section", "diff-file");
  const row = el("div", "diff-line");
  row.append(el("span", "diff-line-number", "0"));
  const body = el("div", "diff-file-body");
  body.append(row);
  probe.append(el("div", "diff-file-bar"), body);
  return { probe, row };
}

/**
 * The first screen's geometry, read while the root and its probes are laid out for the width
 * and before anything else changes, so it is the same layout and not another. Null where
 * nothing is laid out, as in a container with no box or without a browser.
 *
 * @param {HTMLElement} root
 * @param {ReturnType<typeof screenProbe>[]} probes Two, one after the other.
 * @returns {ScreenGeometry | null}
 */
function measureScreen(root, probes) {
  const owner = root.ownerDocument;
  const pane = /** @type {HTMLElement | null} */ (
    root.closest?.("[data-kpress-viewport]") ?? owner?.scrollingElement ?? null
  );
  const [first, second] = probes;
  if (pane === null || typeof first.probe.getBoundingClientRect !== "function") {
    return null;
  }
  const paneHeight = Number(pane.clientHeight);
  // The document's own scroller's box moves with its scroll; what it shows starts at 0.
  const paneTop = pane === owner?.scrollingElement ? 0 : pane.getBoundingClientRect().top;
  const top = first.probe.getBoundingClientRect().top;
  const rowPx = first.row.getBoundingClientRect().height;
  const barPx = second.probe.getBoundingClientRect().top - top - rowPx;
  if (!(paneHeight > 0) || !(rowPx > 0) || !(barPx > 0) || !Number.isFinite(top)) {
    return null;
  }
  return { paneHeight, rootTop: top - paneTop, barPx, rowPx };
}

/**
 * The width and text size a diff has in *container*, from the root's own box, which is what
 * every later report measures: a container's `clientWidth` also holds its padding. And, from
 * the same layout, the geometry its first screen is drawn by. The root is back out before
 * anything can paint.
 *
 * @param {HTMLElement} root
 * @param {HTMLElement} container
 */
function measureInContainer(root, container) {
  const probes = [screenProbe(), screenProbe()];
  root.append(...probes.map(({ probe }) => probe));
  container.append(root);
  const width = root.getBoundingClientRect?.().width ?? 0;
  const fontSize = fontSizeOf(root);
  const screen = width > 0 ? measureScreen(root, probes) : null;
  for (const { probe } of probes) {
    probe.remove();
  }
  root.remove();
  return { width, fontSize, screen };
}

/**
 * Mount a validated ChangeSetDocument.
 *
 * @param {HTMLElement} container
 * @param {Record<string, unknown>} document_
 * @param {DiffViewApi} [api]
 * @param {{showSummary?: boolean, viewFile?: import("./diff-view-file.js").ViewFileOpenerFactory | null}} [options]
 *   *viewFile* makes the opener for a page that can open a file at a commit; without it
 *   the bars carry no View file control. The plugin imports diff-view-file.js for such a
 *   page alone, so this module names it only in types.
 * @returns {{scrollToFile: (path: string) => FileJump, fileForPath: (path: string) => FileLookup, currentFile: () => Extract<FileLookup, {kind: "file"}> | null, onCurrentFile: (listener: (file: Extract<FileLookup, {kind: "file"}> | null) => void) => () => void, cancelPending: () => void, dispose: () => void}}
 */
export function mountDiffView(container, document_, api, options = {}) {
  const root = el("div", "diff-root");
  const chosenLayout = readLayoutPreference(api);
  // Measured before the first draw, so a narrow pane never draws Split to throw it away. A
  // container that is not laid out yet has no width, as a commit's stage has none until it
  // is placed, so nothing is drawn until its first report decides.
  const { width: mountWidth, fontSize, screen } = measureInContainer(root, container);
  const narrow = opensTooNarrowForSplit(mountWidth, fontSize);
  /** @type {MountedDiffState} */
  const view = {
    api,
    awaitingWidth: !(mountWidth > 0) && typeof ResizeObserver === "function",
    byNewPath: new Map(),
    byOldPath: new Map(),
    bySection: new Map(),
    notifyCurrentFile: () => {},
    chosenLayout,
    controller: new AbortController(),
    deferred: new Map(),
    deferredBySection: new Map(),
    deferredFailed: 0,
    deferredLeft: 0,
    disposed: false,
    fileTotal: 0,
    files: [],
    generation: 1,
    hydration: /** @type {MountedDiffState["hydration"]} */ (/** @type {unknown} */ (null)),
    hydrationObserver: null,
    insistedOnSplit: false,
    layout: drawnLayout(chosenLayout, narrow, false),
    layoutControl: null,
    layoutGeneration: 0,
    listTruncated: false,
    narrow,
    partialNote: null,
    pinListeners: null,
    pinned: null,
    pinnedAt: Number.NEGATIVE_INFINITY,
    resolved: /** @type {Record<string, unknown>} */ (document_.resolved ?? {}),
    root,
    enhancementTail: Promise.resolve(),
    sections: [],
    spacer: null,
    timers: new Set(),
    viewFile: null,
    viewFileBusy: null,
    yielders: new Set(),
  };
  view.hydration = createHydrationScheduler(hydrationHost(view));
  if (options.viewFile) {
    view.viewFile = options.viewFile({
      released() {
        view.viewFileBusy?.setAttribute("aria-busy", "false");
        view.viewFileBusy = null;
      },
    });
  }
  const removeSelectionGate = installSplitSelectionGate(root);
  if (!view.awaitingWidth) {
    root.dataset.layout = view.layout;
  }
  const manifest =
    /** @type {{files: Record<string, unknown>[], totals: Record<string, unknown>, truncated: unknown, cursor?: unknown}} */ (
      document_.manifest
    );
  const patches = /** @type {Record<string, Record<string, unknown>>} */ (document_.patches);
  const totals = manifest.totals;
  view.listTruncated = manifest.truncated === true;
  const { toolbar, unbind } = renderDiffToolbar(totals, view, options.showSummary !== false);
  root.append(toolbar);
  // What the source could not model is left out of the files below, so it is said above them.
  for (const warning of /** @type {string[]} */ (view.resolved.warnings ?? [])) {
    root.append(el("div", "diff-availability diff-warning", warning));
  }
  const context = { revision: String(document_.__revision ?? "") };
  view.fileTotal = manifest.files.length;
  if (context.revision) {
    view.deferredLeft = manifest.files.filter((f) => f.availability === "deferred").length;
  }
  if (view.deferredLeft > 0) {
    view.partialNote = el("div", "diff-availability diff-partial-note");
    root.append(view.partialNote);
    renderPartialNote(view);
  }
  // Rows are drawn for the files whose estimated top is within the first screen and one more;
  // every later ready file is held, with its answer, and drawn when it is reached. The bars
  // are all here, and each held file reserves its own rows, so the page is as tall as it
  // will be. Drawing every hydrated file at once was one task of style, layout and commit
  // proportional to the rows: 1,083 ms at 114,609 nodes on a 1,031-file comparison (review
  // of #284, E1). The toolbar is counted as about a bar.
  const budget = firstScreenBudget(screen);
  let estimatedTop = screen?.barPx ?? 0;
  measureProjection(
    api,
    "diffMount:projection",
    () => {
      for (const change of manifest.files) {
        const patch = patches[String(change.id)];
        const draw = estimatedTop < budget;
        root.append(renderFileSection(change, patch, context, view, draw));
        if (screen !== null) {
          estimatedTop +=
            screen.barPx + bodyRows(change, patch, context, view.layout) * screen.rowPx;
        }
      }
      if (manifest.truncated) {
        root.append(el("div", "diff-availability", "The change list was truncated at its bounds."));
      }
      view.spacer = el("div", "diff-end-spacer");
      root.append(view.spacer);
    },
    { file_count: manifest.files.length },
  );
  measureProjection(api, "diffMount:attach", () => container.append(root), {
    file_count: manifest.files.length,
  });
  // Drawing changes the root's height, which this also reports, so it waits for a task of its
  // own: done in the callback, it would be a ResizeObserver loop error. A width is one frame
  // late at the moment it crosses the limit, and the first draw above is not late at all.
  /** @type {number | null} */
  let observedWidth = null;
  /** @type {ReturnType<typeof setTimeout> | null} */
  let fitTimer = null;
  const widths =
    typeof ResizeObserver === "function"
      ? new ResizeObserver((entries) => {
          // Before this frame paints: a height that changed does not show a place that moved.
          holdPlace(view);
          view.notifyCurrentFile();
          const width = entries.at(-1)?.contentRect.width ?? 0;
          if (width === observedWidth) {
            return;
          }
          observedWidth = width;
          if (view.awaitingWidth) {
            if (width > 0) {
              drawAtFirstWidth(width);
            }
            return;
          }
          if (fitTimer !== null) {
            clearTimeout(fitTimer);
            view.timers.delete(/** @type {number} */ (fitTimer));
          }
          const timer = setTimeout(() => {
            view.timers.delete(timer);
            fitTimer = null;
            fitLayout(view, width);
          }, 0);
          fitTimer = timer;
          view.timers.add(timer);
        })
      : null;
  widths?.observe(root);

  /**
   * The first report of a container that had no width at mount. Drawn in the report itself,
   * which the browser makes before it paints, so the diff arrives whole and in one layout.
   * The root is watched again from the next task: the height this changes would otherwise
   * be a ResizeObserver loop error.
   *
   * @param {number} width
   */
  function drawAtFirstWidth(width) {
    view.narrow = opensTooNarrowForSplit(width, fontSizeOf(root));
    widths?.unobserve(root);
    drawLayout(view, drawnLayout(view.chosenLayout, view.narrow, false));
    const timer = setTimeout(() => {
      view.timers.delete(timer);
      widths?.observe(root);
    }, 0);
    view.timers.add(timer);
  }

  /**
   * The first file whose bar or body intersects the pane, including undrawn files.
   * Reuses the ordered-section bisection: a scroll never measures every file.
   * @returns {Extract<FileLookup, {kind: "file"}> | null}
   */
  function currentFile() {
    if (view.disposed) {
      return null;
    }
    const pane = scrollerOf(view);
    const place = placeOfTopFile(view);
    if (pane === null || place === null) {
      return null;
    }
    const bounds = pane.getBoundingClientRect();
    const rect = place.section.getBoundingClientRect();
    if (rect.bottom <= bounds.top || rect.top >= bounds.top + pane.clientHeight) {
      return null;
    }
    const entry = view.bySection.get(place.section);
    if (entry === undefined) {
      return null;
    }
    const side = /** @type {{path?: string}} */ (entry.change.new ?? entry.change.old);
    const path = String(side.path ?? "");
    return {
      kind: "file",
      path,
      fileId: String(entry.change.id),
      changeKind: String(entry.change.kind),
      availability: String(entry.change.availability),
    };
  }
  /** @type {Map<(file: Extract<FileLookup, {kind: "file"}> | null) => void, string | null>} */
  const currentListeners = new Map();
  const currentController = new AbortController();
  /** @type {number | null} */
  let currentFrame = null;
  view.notifyCurrentFile = () => {
    if (view.disposed || currentListeners.size === 0 || currentFrame !== null) {
      return;
    }
    const report = () => {
      currentFrame = null;
      if (view.disposed) {
        return;
      }
      const file = currentFile();
      const id = file?.fileId ?? null;
      for (const [listener, previous] of currentListeners) {
        if (previous !== id) {
          currentListeners.set(listener, id);
          listener(file);
        }
      }
    };
    currentFrame =
      typeof requestAnimationFrame === "function"
        ? requestAnimationFrame(report)
        : setTimeout(report, 0);
  };
  scrollerOf(view)?.addEventListener("scroll", view.notifyCurrentFile, {
    passive: true,
    signal: currentController.signal,
  });

  function cancelPendingWork() {
    view.generation += 1;
    view.controller.abort();
    view.hydrationObserver?.disconnect();
    view.hydrationObserver = null;
    view.hydration.dispose();
    view.deferred.clear();
    view.deferredBySection.clear();
    view.pinListeners?.abort();
    view.pinListeners = null;
    view.pinned = null;
    for (const file of view.files) {
      cancelFoldMaterializations(file);
    }
    for (const timer of view.timers) {
      clearTimeout(timer);
    }
    view.timers.clear();
    for (const waiter of view.yielders) {
      clearTimeout(waiter.timer);
      waiter.resolve(false);
    }
    view.yielders.clear();
  }
  return {
    /**
     * Go to the file a path names: see `FileJump`, and docs/large-content-rendering.md
     * ("Going to a file") for what it promises.
     *
     * @param {string} path
     */
    scrollToFile: (path) => jumpToFile(view, path),
    /**
     * Whether this comparison holds a path, for a list of files from elsewhere: see
     * `FileLookup`.
     *
     * @param {string} path
     */
    fileForPath: (path) => lookupFile(view, path),
    currentFile,
    /** Report immediately, then only when the file changes; unsubscribe is idempotent. */
    onCurrentFile(listener) {
      if (view.disposed) {
        return () => {};
      }
      const file = currentFile();
      currentListeners.set(listener, file?.fileId ?? null);
      listener(file);
      return () => {
        currentListeners.delete(listener);
      };
    },
    cancelPending() {
      if (!view.disposed) {
        cancelPendingWork();
      }
    },
    dispose() {
      if (view.disposed) {
        return;
      }
      view.disposed = true;
      widths?.disconnect();
      currentController.abort();
      currentListeners.clear();
      if (currentFrame !== null) {
        if (typeof cancelAnimationFrame === "function") {
          cancelAnimationFrame(currentFrame);
        } else {
          clearTimeout(currentFrame);
        }
        currentFrame = null;
      }
      cancelPendingWork();
      view.viewFile?.dispose();
      unbind();
      removeSelectionGate();
      root.remove();
    },
  };
}
