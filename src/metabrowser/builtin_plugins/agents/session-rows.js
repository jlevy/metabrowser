// A table of session rows, as the home's recent sessions and the session list draw one.
//
// The route's rows are the data (membership, order, counts); this paints them. A column
// that can be sorted is a button in its header with `aria-sort`, so the table is operable
// from the keyboard, and a row's title is an anchor to the session's file.

import { ageText, durationText } from "./home-model.js";
import { agentLabel, sessionFile, sessionLinkHtml, titleOf } from "./support.js";

/**
 * @typedef {object} SessionRow
 * @property {string} agent
 * @property {string} session_id
 * @property {string | null} title
 * @property {string} origin
 * @property {string | null} project
 * @property {ReadonlyArray<string>} models
 * @property {number | null} started_at
 * @property {number | null} last_activity
 * @property {number | null} duration_seconds
 * @property {number} turns
 * @property {number} size_bytes
 * @property {string} status
 * @property {ReadonlyArray<string>} source_paths
 */

/**
 * @typedef {{id: string, label: string, sort: string | null, numeric?: boolean}} Column
 */

/** Every column the list offers, in order; the home's table takes a subset. */
export const COLUMNS = /** @type {ReadonlyArray<Column>} */ (
  Object.freeze([
    { id: "agent", label: "Agent", sort: "agent" },
    { id: "title", label: "Title", sort: "title" },
    { id: "origin", label: "Origin", sort: "origin" },
    { id: "project", label: "Project", sort: "project" },
    { id: "model", label: "Model", sort: "model" },
    { id: "activity", label: "Active", sort: "activity" },
    { id: "start", label: "Started", sort: "start" },
    { id: "duration", label: "Duration", sort: "duration", numeric: true },
    { id: "turns", label: "Turns", sort: "turns", numeric: true },
    { id: "size", label: "Size", sort: "size", numeric: true },
    { id: "status", label: "Status", sort: "status" },
  ])
);

/** The shell's status badge for a session's status; an unknown status is pending. */
const STATUS_BADGES = Object.freeze({
  running: "badge-running",
  finished: "badge-completed",
  failed: "badge-failed",
});

/** @param {string} status */
function statusBadge(status) {
  const known = /** @type {Record<string, string>} */ (STATUS_BADGES)[status];
  return known ?? "badge-pending";
}

/**
 * @param {MetabrowserPublicSdk} mb
 * @param {Column} column
 * @param {SessionRow} row
 * @param {number} now
 * @returns {string} The cell's content.
 */
function cellHtml(mb, column, row, now) {
  const text = (/** @type {string} */ value) => mb.escapeHtml(value);
  switch (column.id) {
    case "agent":
      return text(agentLabel(row.agent));
    case "title":
      return sessionLinkHtml(mb, titleOf(row), sessionFile(row));
    case "origin":
      return text(row.origin);
    case "project":
      return row.project
        ? `<span data-tip-text="${text(row.project)}">${text(row.project)}</span>`
        : "-";
    case "model":
      return text(row.models.join(", ") || "-");
    case "activity":
      return text(ageText(row.last_activity, now));
    case "start":
      return row.started_at === null ? "-" : text(mb.formatTimestamp(row.started_at));
    case "duration":
      return text(durationText(row.duration_seconds));
    case "turns":
      return text(mb.formatInteger(row.turns));
    case "size":
      return text(mb.formatSize(row.size_bytes));
    case "status":
      return `<span class="file-header-badge ${statusBadge(row.status)}">${text(row.status)}</span>`;
    default:
      return "";
  }
}

/**
 * @param {MetabrowserPublicSdk} mb
 * @param {Column} column
 * @param {{sort: string, order: "asc" | "desc"} | null} sorting `null` for a table that
 *   cannot be re-sorted, as the home's.
 */
function headerHtml(mb, column, sorting) {
  const label = mb.escapeHtml(column.label);
  const numeric = column.numeric ? " agents-numeric" : "";
  if (!sorting || !column.sort) {
    return `<th scope="col" class="agents-col-${column.id}${numeric}">${label}</th>`;
  }
  const active = sorting.sort === column.sort;
  const aria = active ? (sorting.order === "asc" ? "ascending" : "descending") : "none";
  const arrow = active ? (sorting.order === "asc" ? " ↑" : " ↓") : "";
  return (
    `<th scope="col" class="agents-col-${column.id}${numeric}" aria-sort="${aria}">` +
    `<button type="button" class="agents-sort" data-agents-sort="${column.sort}">${label}${arrow}</button>` +
    "</th>"
  );
}

/**
 * The table, or a sentence when there are no rows.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {ReadonlyArray<SessionRow>} rows
 * @param {{columns: ReadonlyArray<string>, now: number, sorting: {sort: string, order: "asc" | "desc"} | null, caption: string, empty: string}} options
 */
export function sessionTableHtml(mb, rows, options) {
  if (rows.length === 0) {
    return `<p class="agents-empty">${mb.escapeHtml(options.empty)}</p>`;
  }
  const columns = COLUMNS.filter((column) => options.columns.includes(column.id));
  const head = columns.map((column) => headerHtml(mb, column, options.sorting)).join("");
  const body = rows
    .map((row) => {
      const cells = columns
        .map(
          (column) =>
            `<td class="agents-col-${column.id}${column.numeric ? " agents-numeric" : ""}">${cellHtml(mb, column, row, options.now)}</td>`,
        )
        .join("");
      return `<tr data-agent="${mb.escapeHtml(row.agent)}" data-session="${mb.escapeHtml(row.session_id)}">${cells}</tr>`;
    })
    .join("");
  return (
    `<table class="agents-table"><caption class="sr-only">${mb.escapeHtml(options.caption)}</caption>` +
    `<thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`
  );
}
