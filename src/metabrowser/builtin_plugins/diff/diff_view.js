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

let sectionSequence = 0;

/** @param {string} tag @param {string} className @param {string} [text] */
function el(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

/** @returns {string} The shell's copy glyph, or "" outside the shell. */
function copyIconSvg() {
  const shell = /** @type {{metabrowser?: {icons?: Record<string, string>}}} */ (
    /** @type {unknown} */ (globalThis)
  );
  return shell.metabrowser?.icons?.copy ?? "";
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
  const toggle = el(
    "button",
    "diff-file-toggle section-disclosure-trigger section-disclosure-leading",
  );
  toggle.setAttribute("type", "button");
  toggle.setAttribute("id", toggleId);
  toggle.setAttribute("aria-controls", bodyId);
  toggle.setAttribute("aria-expanded", "true");
  toggle.append(el("span", `diff-file-kind diff-file-kind-${String(change.kind)}`, letter));
  toggle.append(el("span", "diff-file-path", label));
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
    const svg = copyIconSvg();
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
 * @param {Record<string, unknown>} change
 * @param {Record<string, unknown> | undefined} patch
 * @returns {HTMLElement}
 */
function renderFileSection(change, patch) {
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
    body.classList.toggle("diff-file-body-collapsed", !expanded);
  });

  const availability = String(change.availability);
  if (availability !== "ready" || patch === undefined) {
    const copy = AVAILABILITY_COPY[availability] || "This file's changes are unavailable.";
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
