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
import { buildFileSyntaxModel, highlightFileSyntax } from "./diff-syntax.js";

/**
 * @typedef {object} DiffViewApi
 * @property {(data: Record<string, unknown>) => boolean} isLargeTextPreview
 * @property {(source: string, language: string, options?: {signal?: AbortSignal}) => Promise<MetabrowserSyntaxTokenLines | null>} highlightSyntax
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
 * @property {ReturnType<typeof buildFileSyntaxModel>} syntax
 * @property {{host: HTMLElement, line: ReturnType<typeof buildFileSyntaxModel>["hunks"][number]["lines"][number], side: "old" | "new"}[]} textHosts
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
 * @property {HTMLElement} root
 * @property {Promise<void>} syntaxTail
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
 * Put scanner-validated token data into an existing text host.
 * @param {HTMLElement} host
 * @param {MetabrowserSyntaxTokenRun[]} runs
 */
export function appendTokenRuns(host, runs) {
  const spans = runs.map((run) => {
    const span = el("span", run.classes.join(" "));
    span.textContent = run.text;
    return span;
  });
  host.replaceChildren(...spans);
}

/** @typedef {ReturnType<typeof buildFileSyntaxModel>["hunks"][number]["lines"][number]} DiffLine */
/** @typedef {{changedRun: number | null, old: DiffLine | null, new: DiffLine | null}} SplitRow */

/**
 * @param {DiffLine} line
 * @param {"old" | "new"} side
 */
function sideTokens(line, side) {
  return side === "old" ? line.oldTokens : line.newTokens;
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
  if (runs !== null) {
    appendTokenRuns(host, runs);
  }
  state.textHosts.push({ host, line, side });
  return host;
}

/** @param {ReturnType<typeof buildFileSyntaxModel>["hunks"][number]} hunk */
function renderHunkHeader(hunk) {
  const heading = hunk.heading ? ` ${hunk.heading}` : "";
  return el(
    "div",
    "diff-hunk-header",
    `@@ -${hunk.oldStart},${hunk.oldCount} +${hunk.newStart},${hunk.newCount} @@${heading}`,
  );
}

/** @param {ReturnType<typeof buildFileSyntaxModel>["hunks"][number]} hunk */
export function projectUnifiedHunk(hunk) {
  return hunk.lines.slice();
}

/** @param {DiffLine[]} lines @returns {SplitRow[]} */
export function pairChangedRun(lines) {
  const oldLines = lines.filter((line) => line.op === "del");
  const newLines = lines.filter((line) => line.op === "add");
  const changedRun = lines[0]?.changedRun ?? null;
  return Array.from({ length: Math.max(oldLines.length, newLines.length) }, (_, index) => ({
    changedRun,
    new: newLines[index] ?? null,
    old: oldLines[index] ?? null,
  }));
}

/**
 * Duplicate context and positionally pair each contiguous changed run.
 * @param {ReturnType<typeof buildFileSyntaxModel>["hunks"][number]} hunk
 * @returns {SplitRow[]}
 */
export function projectSplitHunk(hunk) {
  /** @type {SplitRow[]} */
  const rows = [];
  for (let index = 0; index < hunk.lines.length; ) {
    const line = hunk.lines[index];
    if (line.op === "context") {
      rows.push({ changedRun: null, new: line, old: line });
      index += 1;
      continue;
    }
    const run = line.changedRun;
    let end = index + 1;
    while (end < hunk.lines.length && hunk.lines[end].changedRun === run) {
      end += 1;
    }
    rows.push(...pairChangedRun(hunk.lines.slice(index, end)));
    index = end;
  }
  return rows;
}

/**
 * @param {FileViewState} state
 * @param {DiffLine} line
 */
function renderUnifiedLine(state, line) {
  const row = el("div", `diff-line diff-line-${line.op}`);
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
  const cell = el("div", `diff-split-side diff-split-${side} diff-line-${op}`);
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
  const className = row.changedRun === null ? "diff-split-context" : "diff-split-change";
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
 * @param {ReturnType<typeof buildFileSyntaxModel>["hunks"][number]} hunk
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
 * @param {ReturnType<typeof buildFileSyntaxModel>["hunks"][number]} hunk
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
    syntax: buildFileSyntaxModel(change, patch, api.langForPath),
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
  for (const [hunkIndex, hunk] of state.syntax.hunks.entries()) {
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
 * Record diff syntax work when the host profiler is present without
 * making progressive enhancement depend on diagnostics.
 * @template T
 * @param {DiffViewApi} api
 * @param {string} label
 * @param {() => Promise<T>} work
 * @param {Record<string, unknown>} metadata
 * @returns {Promise<T>}
 */
function measureSyntax(api, label, work, metadata) {
  return api.perf ? api.perf.measureAsync(label, work, metadata) : work();
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
    const metadata = {
      hunk_count: state.syntax.hunks.length,
      input_bytes: state.syntax.inputBytes,
      lexer_calls: 0,
    };
    const measuredApi = {
      ...api,
      highlightSyntax: /** @type {DiffViewApi["highlightSyntax"]} */ (
        (source, language, options) => {
          metadata.lexer_calls += 1;
          return measureSyntax(
            api,
            "diffSyntax:lexer",
            () => api.highlightSyntax(source, language, options),
            {
              input_bytes: new TextEncoder().encode(source).byteLength,
              language,
            },
          );
        }
      ),
    };
    const enhanced = await measureSyntax(
      api,
      "diffSyntax:file",
      () => highlightFileSyntax(state.syntax, measuredApi, signal),
      metadata,
    );
    if (!enhanced || !isCurrent()) {
      return;
    }
    for (const { host, line, side } of state.textHosts) {
      const runs = sideTokens(line, side);
      if (runs !== null) {
        appendTokenRuns(host, runs);
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
function yieldForSyntax(view, generation) {
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
 * Serialize syntax enhancement in document order. Each file failure is
 * contained by enhanceFileSyntax, so the tail always reaches later files.
 * @param {MountedDiffState} view
 * @param {FileViewState} state
 */
function scheduleSyntaxEnhancement(view, state) {
  if (!view.api) {
    return;
  }
  const api = view.api;
  const generation = view.generation;
  view.syntaxTail = view.syntaxTail.then(async () => {
    if (!(await yieldForSyntax(view, generation))) {
      return;
    }
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
  for (const state of view.files) {
    renderFileBody(state, layout);
  }
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
      scheduleSyntaxEnhancement(view, state);
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
  scheduleSyntaxEnhancement(view, state);
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
    root,
    syntaxTail: Promise.resolve(),
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
