// The Session view: one session's identity and its events, colored by kind.
//
// A view of an `agent-log` file (a Claude Code transcript or a plain Codex rollout) and of
// an `agent-thread` file (a compressed Codex rollout, which Metabrowser cannot decompress,
// so the thread's history store is its readable copy). The data is the `session` route for
// the header and the `records` route for the events, both asked by the file's own path, so
// a command line reaches the same answers with `metab --api` (tests/golden/cli-api-agents-views.tryscript.md).
//
// A file that is in no agent home (an exported transcript, or one from a Git revision) has
// no session in the catalog. The page then falls back to the plain Log the file always had.

import { ageText, durationText } from "./home-model.js";
import {
  agentLabel,
  ensureViewStyles,
  openSessionLink,
  refusal,
  sessionFile,
  sessionLinkHtml,
  titleOf,
} from "./support.js";

/** The event kinds, as kinds.py names them, for the filter and the badges. */
export const KINDS = Object.freeze([
  "prompt",
  "text",
  "thinking",
  "tool-call",
  "tool-result",
  "metering",
  "control",
  "context",
  "error",
  "unknown",
]);

/**
 * The events one request asks for. The route's own bounds are `RECORDS_DEFAULT` and
 * `RECORDS_MAX`; a page that adds rows on request needs no more than the default.
 */
export const EVENTS_PAGE = 200;

/** The route's refusals that mean the file is simply not a catalogued session. */
const NOT_A_SESSION = Object.freeze([
  "no_agent_homes",
  "session_not_found",
  "unsupported_source",
  "not_found",
]);

/**
 * @typedef {import("./session-rows.js").SessionRow & {
 *   git_branch: string | null, parent_id: string | null, replayed_records: number, records: number,
 *   child_ids: ReadonlyArray<string>, summarized: boolean, ended_at: number | null
 * }} SessionDetail
 */

/**
 * @typedef {object} EventRow
 * @property {string} locator
 * @property {number | null} timestamp
 * @property {string} kind
 * @property {string | null} tool_name
 * @property {string | null} tool_family
 * @property {string} summary
 * @property {boolean} replay
 */

/**
 * @param {MetabrowserPublicSdk} mb
 * @param {{withHeader: boolean}} options `false` for a Log view that shows the events alone.
 */
export function createSessionView(mb, options) {
  return Object.freeze({
    /** @param {HTMLElement} container @param {{path?: string, raw?: unknown, kind?: string}} ctx */
    render: (container, ctx) => mountSession(container, ctx, mb, options.withHeader),
  });
}

/**
 * One event: its kind's badge, the tool when it has one, and its summary.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {EventRow} event
 * @returns {string}
 */
export function eventHtml(mb, event) {
  const esc = (/** @type {string} */ value) => mb.escapeHtml(value);
  const kind = KINDS.includes(event.kind) ? event.kind : "unknown";
  const tool = event.tool_name
    ? `<span class="file-header-badge tool-${esc(event.tool_family ?? "other")}">${esc(event.tool_name)}</span>`
    : "";
  const when = event.timestamp === null ? "" : esc(mb.formatTimestamp(event.timestamp));
  return (
    `<li class="agents-event${event.replay ? " agents-event-replay" : ""}" data-kind="${esc(kind)}" data-locator="${esc(event.locator)}">` +
    `<span class="file-header-badge log-event-kind kind-${kind}">${esc(kind.replace("-", " "))}</span>` +
    tool +
    `<span class="agents-event-summary">${esc(event.summary)}</span>` +
    (event.replay ? '<span class="agents-muted">replayed</span>' : "") +
    `<span class="agents-event-time">${when}</span></li>`
  );
}

/**
 * @param {MetabrowserPublicSdk} mb
 * @param {SessionDetail} session
 * @param {{parent: SessionDetail | null, children: ReadonlyArray<SessionDetail>, children_total: number, now: number}} family
 */
function headerHtml(mb, session, family) {
  const esc = (/** @type {string} */ value) => mb.escapeHtml(value);
  const fact = (/** @type {string} */ label, /** @type {string} */ value) =>
    `<div class="agents-stat"><span class="agents-stat-label">${esc(label)}</span><span class="agents-stat-value">${esc(value)}</span></div>`;
  const status = {
    running: "badge-running",
    finished: "badge-completed",
    failed: "badge-failed",
  }[/** @type {"running" | "finished" | "failed"} */ (session.status)];
  const link = (/** @type {SessionDetail} */ other) =>
    `<li>${sessionLinkHtml(mb, titleOf(other), sessionFile(other))} <span class="agents-muted">${esc(other.status)}, ${esc(durationText(other.duration_seconds))}, ${esc(mb.formatSize(other.size_bytes))}</span></li>`;
  const relatives =
    (family.parent
      ? `<p class="agents-relatives"><span class="agents-stat-label">Parent</span> ${sessionLinkHtml(mb, titleOf(family.parent), sessionFile(family.parent))}</p>`
      : "") +
    (family.children.length > 0
      ? '<div class="agents-relatives"><span class="agents-stat-label">Children</span>' +
        `<ul class="agents-children">${family.children.map(link).join("")}</ul>` +
        (family.children_total > family.children.length
          ? `<p class="agents-muted">and ${esc(mb.formatInteger(family.children_total - family.children.length))} more</p>`
          : "") +
        "</div>"
      : "");
  return (
    '<header class="agents-session-head">' +
    `<h2 class="agents-title">${esc(titleOf(session))}</h2>` +
    `<p class="agents-session-line"><span class="agents-agent">${esc(agentLabel(session.agent))}</span> ` +
    `<span class="file-header-badge ${status ?? "badge-pending"}">${esc(session.status)}</span> ` +
    `<span class="agents-muted">${esc(session.origin)}${session.project ? ` · ${esc(session.project)}` : ""}${session.git_branch ? ` · ${esc(session.git_branch)}` : ""}</span></p>` +
    '<div class="agents-stats">' +
    fact("Models", session.models.join(", ") || "-") +
    fact("Started", session.started_at === null ? "-" : mb.formatTimestamp(session.started_at)) +
    fact("Active", ageText(session.last_activity, family.now)) +
    fact("Duration", durationText(session.duration_seconds)) +
    fact("Turns", mb.formatInteger(session.turns)) +
    fact(
      "Records",
      mb.formatInteger(session.records) +
        (session.replayed_records > 0
          ? ` (${mb.formatInteger(session.replayed_records)} replayed)`
          : ""),
    ) +
    fact("Size", mb.formatSize(session.size_bytes)) +
    "</div>" +
    relatives +
    "</header>"
  );
}

/**
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown, kind?: string}} ctx
 * @param {MetabrowserPublicSdk} mb
 * @param {boolean} withHeader
 */
export function mountSession(container, ctx, mb, withHeader) {
  const path = ctx.path ?? "";
  const controller = new AbortController();
  const fc = mb.filterControls;
  let disposed = false;
  /** @type {(() => void) | null} */
  let fallbackDispose = null;
  /** @type {string | null} */
  let kind = null;
  let menuOpen = false;
  let cursor = 0;
  let generation = 0;
  /** @type {(() => void) | null} */
  let unbindFilter = null;

  container.replaceChildren();
  const root = document.createElement("div");
  root.className = "agents-session";
  root.innerHTML =
    '<div class="agents-session-header"></div>' +
    '<div class="agents-event-filter"></div>' +
    '<div class="agents-loading mb-delayed-loading" aria-hidden="true"></div>' +
    '<p class="agents-empty" role="status" hidden></p>' +
    '<ol class="agents-events"></ol>' +
    '<div class="agents-more" hidden><button type="button" class="btn" data-agents-more>Load more events</button></div>';
  container.append(root);
  const headerEl = /** @type {HTMLElement} */ (root.querySelector(".agents-session-header"));
  const filterEl = /** @type {HTMLElement} */ (root.querySelector(".agents-event-filter"));
  const notice = /** @type {HTMLElement} */ (root.querySelector(".agents-empty"));
  const list = /** @type {HTMLElement} */ (root.querySelector(".agents-events"));
  const more = /** @type {HTMLElement} */ (root.querySelector(".agents-more"));

  /** A failed read, as the shell shows one: a notice with a severity, announced. @param {string} message */
  function showFailure(message) {
    root.querySelector(".agents-loading")?.remove();
    notice.hidden = false;
    notice.className = "notice";
    notice.setAttribute("data-severity", "error");
    notice.setAttribute("role", "alert");
    notice.textContent = message;
  }

  function paintFilter() {
    if (!fc) {
      return;
    }
    const restore = fc.keepFocus(filterEl);
    unbindFilter?.();
    filterEl.innerHTML = fc.menuGroupHtml({
      key: "kind",
      select: "one",
      label: "Event kind",
      options: KINDS.map((value) => ({ value, label: value.replace("-", " ") })),
      value: kind ?? "all",
      anyLabel: "Any kind",
      anyValue: "all",
      open: menuOpen,
      menuId: "agents-kind-menu",
    });
    unbindFilter = fc.bind(filterEl, {
      onMenuToggle(_key, open) {
        menuOpen = open;
        paintFilter();
      },
      onMenuPick(_key, value) {
        menuOpen = false;
        kind = value === null || value === "all" ? null : value;
        cursor = 0;
        list.replaceChildren();
        void loadEvents();
        paintFilter();
      },
    });
    restore();
  }

  /** Load the events from `cursor` on, adding them to the list. */
  async function loadEvents() {
    const token = ++generation;
    const mine = controller.signal;
    try {
      const answer = /** @type {{events: ReadonlyArray<EventRow>, next_cursor: number | null}} */ (
        /** @type {unknown} */ (
          await mb.fetchPluginData(
            "agents",
            "records",
            { path, limit: EVENTS_PAGE, cursor, ...(kind ? { kind } : {}) },
            { signal: mine },
          )
        )
      );
      if (disposed || token !== generation) {
        return;
      }
      root.querySelector(".agents-loading")?.remove();
      list.insertAdjacentHTML("beforeend", answer.events.map((e) => eventHtml(mb, e)).join(""));
      cursor = answer.next_cursor ?? cursor;
      more.hidden = answer.next_cursor === null;
      const none = list.childElementCount === 0;
      notice.hidden = !none;
      notice.textContent = none ? "No events match." : "";
    } catch (error) {
      if (disposed || mine.aborted || token !== generation) {
        return;
      }
      root.querySelector(".agents-loading")?.remove();
      showFailure(refusal(error).message);
    }
  }

  /**
   * The file is no session of a catalog: show the plain Log an agent-log file has, or say so.
   *
   * @param {string} message
   */
  function fallback(message) {
    const builtin = /** @type {any} */ (mb.builtins)?.agentLog;
    if (ctx.kind === "agent-log" && builtin?.renderLog) {
      container.replaceChildren();
      builtin.renderLog(container, ctx);
      fallbackDispose = () => builtin.disposeLog?.(container);
      return;
    }
    root.querySelector(".agents-loading")?.remove();
    notice.hidden = false;
    notice.textContent = message;
  }

  const ready = (async () => {
    await ensureViewStyles();
    if (withHeader) {
      try {
        const answer =
          /** @type {{session: SessionDetail, parent: SessionDetail | null, children: ReadonlyArray<SessionDetail>, children_total: number, now: number}} */ (
            /** @type {unknown} */ (
              await mb.fetchPluginData("agents", "session", { path }, { signal: controller.signal })
            )
          );
        if (disposed) {
          return;
        }
        headerEl.innerHTML = headerHtml(mb, answer.session, answer);
      } catch (error) {
        if (disposed || controller.signal.aborted) {
          return;
        }
        const failed = refusal(error);
        if (failed.code && NOT_A_SESSION.includes(failed.code)) {
          fallback(
            "This file is not in a Claude Code or Codex home, so there is no session to show.",
          );
        } else {
          showFailure(failed.message);
        }
        return;
      }
    }
    paintFilter();
    await loadEvents();
  })();

  /** @param {MouseEvent} event */
  function onClick(event) {
    if (openSessionLink(mb, event, container)) {
      return;
    }
    const target = /** @type {Element | null} */ (event.target);
    if (target?.closest?.("[data-agents-more]")) {
      void loadEvents();
    }
  }
  container.addEventListener("click", onClick);

  return Object.freeze({
    ready,
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      controller.abort();
      unbindFilter?.();
      fallbackDispose?.();
      container.removeEventListener("click", onClick);
      container.replaceChildren();
    },
  });
}
