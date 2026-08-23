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

import { fileChangeLabel, validateDocument } from "./diff_model.js";

/**
 * Fetch one file's change from a comparison. Injected by the plugin so
 * this module keeps its only job — projecting a document — and stays
 * testable without a shell.
 *
 * @type {(revision: string, path: string) => Promise<Record<string, unknown>>}
 */
let loadOneChange = async () => {
  throw new Error("no loader configured");
};

/** @param {(revision: string, path: string) => Promise<Record<string, unknown>>} loader */
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

/** @param {Record<string, unknown>} hunk @returns {HTMLElement} */
function renderHunk(hunk) {
  const section = el("div", "diff-hunk");
  const heading = hunk.heading ? ` ${hunk.heading}` : "";
  section.append(
    el(
      "div",
      "diff-hunk-header",
      `@@ -${hunk.old_start},${hunk.old_count} +${hunk.new_start},${hunk.new_count} @@${heading}`,
    ),
  );
  let oldLine = Number(hunk.old_start);
  let newLine = Number(hunk.new_start);
  const lines = /** @type {Record<string, unknown>[]} */ (hunk.lines);
  // Index the contiguous runs of changed lines first, so each line knows
  // whether it belongs to a run long enough to fold and where it sits
  // within it. Folding is per run, not per hunk: a hunk may hold a large
  // rewrite beside ordinary edits, and only the rewrite should collapse.
  const runIndex = new Array(lines.length).fill(-1);
  const runLength = new Array(lines.length).fill(0);
  for (let start = 0; start < lines.length; ) {
    if (String(lines[start].op) === "context") {
      start += 1;
      continue;
    }
    let end = start;
    while (end < lines.length && String(lines[end].op) !== "context") {
      end += 1;
    }
    for (let i = start; i < end; i += 1) {
      runIndex[i] = i - start;
      runLength[i] = end - start;
    }
    start = end;
  }

  /** @type {HTMLElement | null} The group hidden lines are appended to. */
  let foldGroup = null;
  for (const [index, line] of lines.entries()) {
    const op = String(line.op);
    const row = el("div", `diff-line diff-line-${op}`);
    const oldNumber = el("span", "diff-line-number", op === "add" ? "" : String(oldLine));
    const newNumber = el("span", "diff-line-number", op === "del" ? "" : String(newLine));
    const marker = el("span", "diff-line-marker", op === "add" ? "+" : op === "del" ? "-" : " ");
    const text = el("span", "diff-line-text", String(line.text));
    row.append(oldNumber, newNumber, marker, text);
    if (line.no_newline) {
      row.append(el("span", "diff-line-no-newline", "⏎ absent"));
      row.dataset.tipText = "No newline at end of file";
    }
    const folds = FOLD_THRESHOLD > 0 && runLength[index] > FOLD_THRESHOLD;
    if (folds && runIndex[index] === FOLD_VISIBLE) {
      // The break: an expander stating exactly how many lines it holds.
      const hidden = runLength[index] - FOLD_VISIBLE;
      foldSequence += 1;
      foldGroup = el("div", "diff-fold-group diff-fold-collapsed");
      foldGroup.setAttribute("id", `diff-fold-group-${foldSequence}`);
      section.append(renderFoldControl(foldGroup, hidden), foldGroup);
    }
    (folds && runIndex[index] >= FOLD_VISIBLE ? (foldGroup ?? section) : section).append(row);
    if (runIndex[index] === runLength[index] - 1) {
      foldGroup = null;
    }
    if (op !== "add") {
      oldLine += 1;
    }
    if (op !== "del") {
      newLine += 1;
    }
  }
  return section;
}

/**
 * The fold expander: the tree's disclosure vocabulary on a full-width
 * row, stating the count it holds so the reader knows what is hidden.
 *
 * @param {HTMLElement} group
 * @param {number} hidden
 * @returns {HTMLElement}
 */
function renderFoldControl(group, hidden) {
  const control = el("button", "diff-fold-control");
  control.setAttribute("type", "button");
  control.setAttribute("aria-expanded", "false");
  control.setAttribute("aria-controls", group.getAttribute("id") || "");
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
    `${hidden} more changed line${hidden === 1 ? "" : "s"}`,
  );
  control.append(chevron, label);
  let expanded = false;
  control.addEventListener("click", (event) => {
    // The bar above owns clicks on the file section; a fold is its own
    // control and must not also collapse the whole file.
    event.stopPropagation();
    expanded = !expanded;
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

/**
 * Fetch one deferred file's hunks and splice them in, behind the
 * standard progress box.
 *
 * @param {HTMLElement} body
 * @param {Record<string, unknown>} change
 * @param {string} revision
 */
async function hydrateDeferred(body, change, revision) {
  const side = /** @type {Record<string, unknown> | undefined} */ (change.new ?? change.old);
  const path = String(side?.path ?? "");
  const box = progressBox(`Loading the diff for ${path}`);
  body.append(box);
  const started = Date.now();
  const slow = setTimeout(() => {
    reportLoad("file hydration", { revision, path, elapsedMs: Date.now() - started });
  }, SLOW_LOAD_MS);
  try {
    const payload = await loadOneChange(revision, path);
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
    for (const hunk of hunks) {
      body.append(renderHunk(hunk));
    }
    if (hunks.length === 0) {
      body.append(el("div", "diff-availability", "No content changes."));
    }
  } catch (error) {
    reportLoad(
      "file hydration",
      { revision, path, hook: "diff/comparison", elapsedMs: Date.now() - started },
      error,
    );
    box.remove();
    body.append(el("div", "diff-availability", "Could not load this file's changes."));
  } finally {
    clearTimeout(slow);
  }
}

/**
 * @param {Record<string, unknown>} change
 * @param {Record<string, unknown> | undefined} patch
 * @param {{revision?: string}} [context]
 * @returns {HTMLElement}
 */
function renderFileSection(change, patch, context = {}) {
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
    void hydrateDeferred(body, change, context.revision);
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
  for (const hunk of hunks) {
    body.append(renderHunk(hunk));
  }
  if (patch.truncated) {
    body.append(el("div", "diff-availability", "This patch was truncated at its bounds."));
  }
  return section;
}

/**
 * Mount a validated ChangeSetDocument.
 *
 * @param {HTMLElement} container
 * @param {Record<string, unknown>} document_
 * @returns {{dispose: () => void}}
 */
export function mountDiffView(container, document_) {
  const root = el("div", "diff-root");
  const manifest =
    /** @type {{files: Record<string, unknown>[], totals: Record<string, unknown>, truncated: unknown, cursor?: unknown}} */ (
      document_.manifest
    );
  const patches = /** @type {Record<string, Record<string, unknown>>} */ (document_.patches);
  const totals = manifest.totals;
  const plus = totals.additions === null ? "?" : String(totals.additions);
  const minus = totals.deletions === null ? "?" : String(totals.deletions);
  const exactness = totals.exact ? "" : " (estimated)";
  // A single-file document is one file's diff — the bar already carries
  // its name and stats, so a one-line summary above it would only repeat
  // itself. Change sets keep the summary.
  if (Number(totals.files) !== 1) {
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
    if (exactness) {
      summary.append(el("span", "diff-summary-note", exactness.trim()));
    }
    root.append(summary);
  }
  const context = { revision: String(document_.__revision ?? "") };
  for (const change of manifest.files) {
    root.append(renderFileSection(change, patches[String(change.id)], context));
  }
  if (manifest.truncated) {
    root.append(el("div", "diff-availability", "The change list was truncated at its bounds."));
  }
  container.append(root);
  return {
    dispose() {
      root.remove();
    },
  };
}
