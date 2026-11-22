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
// While a home's first pass has not listed its sessions, the routes answer
// `catalog_incomplete` instead, since the file may only be unlisted so far: the page then
// shows the catalog's progress and asks again, through `createPoller`, until the answer is
// a session or a refusal that says the file is none.

import { ageText, durationText, progressView } from "./home-model.js";
import { browserClock, createPoller, PROGRESS_POLL_MS, retrying } from "./poller.js";
import {
  agentLabel,
  ensureViewStyles,
  joinGroups,
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

/** The route's refusal that means the catalog has not listed its sessions yet: ask again. */
export const CATALOG_INCOMPLETE = "catalog_incomplete";

/**
 * What the page says while it waits for the catalog's first pass.
 *
 * @param {import("./home-model.js").Progress | null} progress
 * @param {(value: number) => string} formatInteger
 * @returns {string}
 */
export function waitingText(progress, formatInteger) {
  return progress ? progressView(progress, formatInteger).text : "Reading the session catalog…";
}

/**
 * What the page says about the events it showed, which is a sentence only when there is
 * something to say: that none match (said only when the scan reached the session's end),
 * that none matched yet, or that the scan's bound stopped it. An empty string says
 * nothing.
 *
 * @param {{shown: number, nextCursor: number | null, truncated: boolean}} page
 * @returns {{notice: string, note: string}} `notice` stands for an empty list; `note`
 *   follows a list that has rows.
 */
export function eventsSaid(page) {
  if (page.shown === 0) {
    if (page.truncated) {
      return {
        notice: "No events matched in the part of the session that could be searched.",
        note: "",
      };
    }
    return {
      notice: page.nextCursor === null ? "No events match." : "No events matched yet.",
      note: "",
    };
  }
  return {
    notice: "",
    note: page.truncated
      ? "Showing the first events the scan reached; the rest of this session is not searched."
      : "",
  };
}

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
    '<header class="agents-session-head page-header">' +
    `<h2 class="agents-title page-heading">${esc(titleOf(session))}</h2>` +
    `<p class="agents-session-line page-header-line"><span class="agents-agent">${esc(agentLabel(session.agent))}</span> ` +
    `<span class="file-header-badge ${status ?? "badge-pending"}">${esc(session.status)}</span> ` +
    `<span class="agents-muted">${joinGroups(mb, [
      esc(session.origin),
      session.project ? esc(session.project) : "",
      session.git_branch ? esc(session.git_branch) : "",
    ])}</span></p>` +
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
    '<p class="agents-muted agents-events-note" role="status" hidden></p>' +
    '<div class="agents-more" hidden><button type="button" class="btn" data-agents-more>Load more events</button></div>';
  container.append(root);
  const headerEl = /** @type {HTMLElement} */ (root.querySelector(".agents-session-header"));
  const filterEl = /** @type {HTMLElement} */ (root.querySelector(".agents-event-filter"));
  const notice = /** @type {HTMLElement} */ (root.querySelector(".agents-empty"));
  const list = /** @type {HTMLElement} */ (root.querySelector(".agents-events"));
  const more = /** @type {HTMLElement} */ (root.querySelector(".agents-more"));

  const noteEl = /** @type {HTMLElement} */ (root.querySelector(".agents-events-note"));

  /** A failed read, as the shell shows one: a notice with a severity, announced. @param {string} message */
  function showFailure(message) {
    root.querySelector(".agents-loading")?.remove();
    notice.hidden = false;
    notice.className = "notice";
    notice.setAttribute("data-severity", "error");
    notice.setAttribute("role", "alert");
    notice.textContent = message;
  }

  /**
   * A plain sentence in the same element a failure uses, which it must leave as it
   * found it: no severity and no alert role, or "No events match." would be announced as
   * an error.
   *
   * @param {string} message
   */
  function showMessage(message) {
    root.querySelector(".agents-loading")?.remove();
    notice.hidden = message === "";
    notice.className = "agents-empty";
    notice.removeAttribute("data-severity");
    notice.setAttribute("role", "status");
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

  /**
   * Load the events from `cursor` on, adding them to the list.
   *
   * @returns {Promise<boolean>} True when the catalog has not listed the session yet, so
   *   the caller asks again.
   */
  async function loadEvents() {
    const token = ++generation;
    const mine = controller.signal;
    try {
      const answer =
        /** @type {{events: ReadonlyArray<EventRow>, next_cursor: number | null, truncated: boolean}} */ (
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
        return false;
      }
      root.querySelector(".agents-loading")?.remove();
      list.insertAdjacentHTML("beforeend", answer.events.map((e) => eventHtml(mb, e)).join(""));
      cursor = answer.next_cursor ?? cursor;
      // A scan the route's bound stopped has no next cursor: no button, and a sentence.
      more.hidden = answer.next_cursor === null;
      const said = eventsSaid({
        shown: list.childElementCount,
        nextCursor: answer.next_cursor,
        truncated: answer.truncated === true,
      });
      showMessage(said.notice);
      noteEl.hidden = said.note === "";
      noteEl.textContent = said.note;
      return false;
    } catch (error) {
      if (disposed || mine.aborted || token !== generation) {
        return false;
      }
      const failed = refusal(error);
      if (failed.code === CATALOG_INCOMPLETE) {
        showMessage(waitingText(failed.progress, mb.formatInteger));
        return true;
      }
      root.querySelector(".agents-loading")?.remove();
      showFailure(failed.message);
      return false;
    }
  }

  /**
   * The file is no session of a catalog: show the plain Log an agent-log file has, or say so.
   *
   * @param {string} message
   */
  async function fallback(message) {
    const view = ctx.kind === "agent-log" ? mb.getRegisteredView("agent-log", "log") : null;
    if (view) {
      container.replaceChildren();
      fallbackDispose = () => view.dispose?.(container);
      await view.render(container, ctx);
      return;
    }
    showMessage(message);
  }

  let headerShown = false;

  /**
   * One attempt to show the session: its header, then its first events.
   *
   * @returns {Promise<boolean>} True while the catalog has not listed the file's session,
   *   so the poll below asks again.
   */
  async function begin() {
    if (withHeader && !headerShown) {
      try {
        const answer =
          /** @type {{session: SessionDetail, parent: SessionDetail | null, children: ReadonlyArray<SessionDetail>, children_total: number, now: number}} */ (
            /** @type {unknown} */ (
              await mb.fetchPluginData("agents", "session", { path }, { signal: controller.signal })
            )
          );
        if (disposed) {
          return false;
        }
        headerEl.innerHTML = headerHtml(mb, answer.session, answer);
        headerShown = true;
      } catch (error) {
        if (disposed || controller.signal.aborted) {
          return false;
        }
        const failed = refusal(error);
        if (failed.code === CATALOG_INCOMPLETE) {
          showMessage(waitingText(failed.progress, mb.formatInteger));
          return true;
        }
        if (failed.code && NOT_A_SESSION.includes(failed.code)) {
          await fallback(
            "This file is not in a Claude Code or Codex home, so there is no session to show.",
          );
        } else {
          showFailure(failed.message);
        }
        return false;
      }
    }
    if (!filterPainted) {
      filterPainted = true;
      paintFilter();
    }
    return loadEvents();
  }

  let filterPainted = false;
  // The catalog's first pass has not listed the file's session yet: ask again, backing off
  // on a failure, until the answer is a session or a refusal that says there is none.
  const catalogWait = createPoller({
    ...browserClock(),
    intervalMs: PROGRESS_POLL_MS,
    run: retrying(begin),
  });

  const ready = (async () => {
    await ensureViewStyles();
    if (await begin()) {
      catalogWait.start();
    }
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
      catalogWait.dispose();
      unbindFilter?.();
      fallbackDispose?.();
      container.removeEventListener("click", onClick);
      container.replaceChildren();
    },
  });
}
