// Lists of sessions: the session list's table, and the two-line rows the home's Active sessions
// and Latest sessions draw.
//
// The route's rows are the data (membership, order, counts); this paints them. A column
// that can be sorted is a button in its header with `aria-sort`, so the table is operable
// from the keyboard, and a row's title is an anchor to the session's file.

import { durationText } from "./home-model.js";
import { agentLabel, separatorHtml, sessionFile, sessionLinkHtml, titleOf } from "./support.js";

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

/** Every column the list offers, in order; a table takes the subset it names. */
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
      return row.models.length > 0
        ? `<span data-tip-text="${text(row.models.join(", "))}">${text(row.models.join(", "))}</span>`
        : "-";
    case "activity":
      // The shell's one age builder, in its freshness ink, as of the answer's time
      // (docs/design-system.md, "Age").
      return mb.ageLabelHtml(row.last_activity, { style: "relative", now }) || "-";
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
 * @param {{sort: string, order: "asc" | "desc"}} sorting
 */
function headerHtml(mb, column, sorting) {
  const label = mb.escapeHtml(column.label);
  const numeric = column.numeric ? " agents-numeric" : "";
  if (!column.sort) {
    return `<th scope="col" class="agents-col-${column.id}${numeric}">${label}</th>`;
  }
  const active = sorting.sort === column.sort;
  const aria = active ? (sorting.order === "asc" ? "ascending" : "descending") : "none";
  return (
    `<th scope="col" class="agents-col-${column.id}${numeric}" aria-sort="${aria}">` +
    `<button type="button" class="agents-sort" data-agents-sort="${column.sort}">${label}</button>` +
    "</th>"
  );
}

/**
 * The table, or a sentence when there are no rows.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {ReadonlyArray<SessionRow>} rows
 * @param {{columns: ReadonlyArray<string>, now: number, sorting: {sort: string, order: "asc" | "desc"}, caption: string, empty: string}} options
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

/**
 * @typedef {object} RowItem One line of a list of sessions, whichever route it came from.
 * @property {string} agent
 * @property {string} session_id
 * @property {string} title
 * @property {string | null} path The session's file, or `null` for a title with no link.
 * @property {number | null} at When the session was last active, in epoch seconds.
 * @property {string | null} project
 * @property {ReadonlyArray<string>} models
 * @property {string | null} status Shown as a badge at the second line's start, or `null`.
 */

/**
 * A session as a two-line row, as the home's Active sessions and Latest sessions list them.
 * The first line is the agent, the title link, and the age at its end, which never wraps;
 * the second, muted line is a status badge when there is one, the project, and the model,
 * each cut short with an ellipsis rather than wrapped, so a long path never pushes the age
 * onto a line of its own (docs/design-system.md, "Session Rows").
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {ReadonlyArray<RowItem>} items
 * @param {{label: string, now: number}} options `label` names the list for assistive
 *   technology; `now`, in epoch seconds, is the time its answer was given, which its ages
 *   are told as of.
 */
export function sessionRowsHtml(mb, items, options) {
  const text = (/** @type {string} */ value) => mb.escapeHtml(value);
  const rows = items
    .map((item) => {
      const models = item.models.join(", ");
      const project = item.project
        ? `<span class="agents-row-project" data-tip-text="${text(item.project)}">${text(item.project)}</span>`
        : "";
      const model = models
        ? `<span class="agents-row-model" data-tip-text="${text(models)}">${text(models)}</span>`
        : "";
      const badge = item.status
        ? `<span class="file-header-badge ${statusBadge(item.status)}">${text(item.status)}</span>`
        : "";
      const meta =
        badge + (project && model ? `${project}${separatorHtml(mb)}${model}` : project + model);
      return (
        `<li class="agents-session-row" data-agent="${text(item.agent)}" data-session="${text(item.session_id)}">` +
        '<div class="agents-row-line">' +
        `<span class="agents-agent">${text(agentLabel(item.agent))}</span>` +
        sessionLinkHtml(mb, item.title, item.path, "agents-session-link agents-row-title") +
        mb.ageLabelHtml(item.at, {
          style: "relative",
          now: options.now,
          className: "agents-row-age",
        }) +
        "</div>" +
        `<div class="agents-row-meta agents-muted">${meta}</div></li>`
      );
    })
    .join("");
  return `<ul class="agents-session-rows" aria-label="${text(options.label)}">${rows}</ul>`;
}
