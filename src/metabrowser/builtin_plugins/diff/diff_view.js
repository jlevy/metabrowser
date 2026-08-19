// Unified diff renderer over File Diff Format.
//
// Renders the manifest as sticky file sections and each hydrated patch
// as hunks of line rows. Every availability state has exactly one
// rendering path — an absent patch is a labeled state, never an empty
// box. Rendering is deliberately dumber than the model: the data plane
// is tested by the conformance corpus and CLI goldens, and this layer
// only projects it.

import { fileChangeLabel } from "./diff_model.js";

const AVAILABILITY_COPY = /** @type {Record<string, string>} */ ({
  deferred: "This file's changes have not been loaded yet.",
  binary: "Binary file; no textual diff.",
  too_large: "This change is too large to show inline.",
  timed_out: "Producing this diff timed out.",
  failed: "Could not produce this diff.",
  stale: "The comparison changed underneath this file. Refresh to reload it.",
  unsupported: "This change cannot be shown as a text diff.",
});

/** @param {string} tag @param {string} className @param {string} [text] */
function el(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
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
  for (const line of /** @type {Record<string, unknown>[]} */ (hunk.lines)) {
    const op = String(line.op);
    const row = el("div", `diff-line diff-line-${op}`);
    const oldNumber = el("span", "diff-line-number", op === "add" ? "" : String(oldLine));
    const newNumber = el("span", "diff-line-number", op === "del" ? "" : String(newLine));
    const marker = el("span", "diff-line-marker", op === "add" ? "+" : op === "del" ? "-" : " ");
    const text = el("span", "diff-line-text", String(line.text));
    row.append(oldNumber, newNumber, marker, text);
    if (line.no_newline) {
      row.append(el("span", "diff-line-no-newline", "⏎ absent"));
      row.title = "No newline at end of file";
    }
    section.append(row);
    if (op !== "add") {
      oldLine += 1;
    }
    if (op !== "del") {
      newLine += 1;
    }
  }
  return section;
}

/** @param {Record<string, unknown>} change @returns {HTMLElement} */
function renderFileHeader(change) {
  const { letter, label, notes } = fileChangeLabel(change);
  const header = el("div", "diff-file-header");
  header.append(el("span", `diff-file-kind diff-file-kind-${String(change.kind)}`, letter));
  header.append(el("span", "diff-file-path", label));
  for (const note of notes) {
    header.append(el("span", "diff-file-note", note));
  }
  if (change.additions !== null && change.additions !== undefined) {
    header.append(el("span", "diff-file-counts", `+${change.additions} −${change.deletions}`));
  }
  return header;
}

/**
 * @param {Record<string, unknown>} change
 * @param {Record<string, unknown> | undefined} patch
 * @returns {HTMLElement}
 */
function renderFileSection(change, patch) {
  const section = el("section", "diff-file");
  section.append(renderFileHeader(change));
  const availability = String(change.availability);
  if (availability !== "ready" || patch === undefined) {
    const copy = AVAILABILITY_COPY[availability] || "This file's changes are unavailable.";
    section.append(el("div", "diff-availability", copy));
    return section;
  }
  const hunks = /** @type {Record<string, unknown>[]} */ (patch.hunks);
  if (hunks.length === 0) {
    // A hydrated patch with no hunks is a metadata-only change (a chmod,
    // a pure rename): the header already says everything it changes.
    section.append(el("div", "diff-availability", "No content changes."));
    return section;
  }
  for (const hunk of hunks) {
    section.append(renderHunk(hunk));
  }
  if (patch.truncated) {
    section.append(el("div", "diff-availability", "This patch was truncated at its bounds."));
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
  root.append(
    el(
      "div",
      "diff-summary",
      `${totals.files} changed ${Number(totals.files) === 1 ? "file" : "files"}  +${plus} −${minus}${exactness}`,
    ),
  );
  for (const change of manifest.files) {
    root.append(renderFileSection(change, patches[String(change.id)]));
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
