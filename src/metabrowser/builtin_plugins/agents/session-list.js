// The session list: every session of a home's folder, filtered, sorted, and paged.
//
// A folder view the plugin offers beside the agents home (manifest.toml). The data is the
// `sessions` route, one page at a time, so a list of tens of thousands of sessions costs one
// page of rows. What a person can change is the state machine in `session-list-state.js`,
// which this file only paints and feeds; a row opens the session's file through the SDK's
// navigation.

import { progressView } from "./home-model.js";
import { browserClock, createPoller, PROGRESS_POLL_MS } from "./poller.js";
import {
  initialState,
  ORIGINS,
  pageOf,
  queryOf,
  STATUSES,
  toggleOrigin,
  toggleStatus,
  WINDOWS,
  withFilter,
  withPage,
  withSort,
} from "./session-list-state.js";
import { COLUMNS, sessionTableHtml } from "./session-rows.js";
import { agentLabel, ensureViewStyles, folderParam, openSessionLink, refusal } from "./support.js";

/** @typedef {import("./session-rows.js").SessionRow} SessionRow */
/** @typedef {import("./session-list-state.js").ListState} ListState */

/**
 * @typedef {object} ListAnswer
 * @property {number} now
 * @property {number} total
 * @property {number} available
 * @property {{size_bytes: number, running: number}} totals
 * @property {{agent: Record<string, number>, origin: Record<string, number>, status: Record<string, number>, project: ReadonlyArray<[string, number]>, model: ReadonlyArray<[string, number]>}} facets
 * @property {import("./home-model.js").Progress} progress
 * @property {ReadonlyArray<SessionRow>} sessions
 */

/** The date windows' labels, in order. */
const WINDOW_LABELS = Object.freeze({
  all: "Any time",
  day: "Last day",
  week: "Last week",
  month: "Last month",
});

/** @param {MetabrowserPublicSdk} mb */
export function createSessionListView(mb) {
  return Object.freeze({
    /** @param {HTMLElement} container @param {{path?: string}} ctx */
    render: (container, ctx) => mountSessionList(container, ctx, mb),
  });
}

/**
 * @param {HTMLElement} container
 * @param {{path?: string}} ctx
 * @param {MetabrowserPublicSdk} mb
 */
export function mountSessionList(container, ctx, mb) {
  const folder = folderParam(ctx.path);
  const clock = browserClock();
  const fc = mb.filterControls;
  /** @type {ListState} */
  let state = initialState();
  /** @type {ListAnswer | null} */
  let answer = null;
  /** @type {AbortController | null} */
  let flight = null;
  let generation = 0;
  let disposed = false;
  /** @type {string | null} */
  let openMenu = null;
  /** @type {string | null} */
  let failure = null;
  /** @type {(() => void) | null} */
  let unbindFilters = null;

  container.replaceChildren();
  const root = document.createElement("div");
  root.className = "agents-list";
  root.innerHTML =
    '<div class="agents-filters"></div>' +
    '<div class="notice" data-severity="error" role="alert" hidden></div>' +
    '<div class="agents-list-summary" role="status"></div>' +
    '<div class="agents-loading mb-delayed-loading" aria-hidden="true"></div>' +
    '<div class="agents-table-wrap" hidden></div>' +
    '<nav class="agents-pager" aria-label="Pages" hidden></nav>';
  container.append(root);
  const filtersEl = /** @type {HTMLElement} */ (root.querySelector(".agents-filters"));
  const failureEl = /** @type {HTMLElement} */ (root.querySelector(".notice"));
  const summaryEl = /** @type {HTMLElement} */ (root.querySelector(".agents-list-summary"));
  const tableEl = /** @type {HTMLElement} */ (root.querySelector(".agents-table-wrap"));
  const pagerEl = /** @type {HTMLElement} */ (root.querySelector(".agents-pager"));

  /** @param {Record<string, number> | undefined} counts @param {string} value */
  const countOf = (counts, value) => counts?.[value];

  function paintFilters() {
    if (!fc) {
      return;
    }
    const facets = answer?.facets;
    const agentOptions = [
      { value: "all", label: "Any agent" },
      ...["claude", "codex"].map((agent) => ({
        value: agent,
        label: agentLabel(agent),
        count: countOf(facets?.agent, agent),
      })),
    ];
    const originOptions = ORIGINS.map((origin) => ({
      value: origin,
      label: origin,
      count: countOf(facets?.origin, origin),
    }));
    const statusOptions = STATUSES.map((status) => ({
      value: status,
      label: status,
      count: countOf(facets?.status, status),
    }));
    const windowOptions = Object.keys(WINDOWS).map((key) => ({
      value: key,
      label: /** @type {Record<string, string>} */ (WINDOW_LABELS)[key],
    }));
    const named = (/** @type {ReadonlyArray<[string, number]> | undefined} */ pairs) =>
      (pairs ?? []).map(([name, count]) => ({ value: name, label: name, count }));
    const restore = fc.keepFocus(filtersEl);
    unbindFilters?.();
    filtersEl.innerHTML =
      fc.groupHtml({
        key: "agent",
        select: "one",
        layout: "joined",
        label: "Agent",
        options: agentOptions,
        value: state.agent ?? "all",
      }) +
      fc.groupHtml({
        key: "origin",
        select: "many",
        layout: "wrap",
        label: "Origin",
        options: originOptions,
        value: [...state.origins],
      }) +
      fc.groupHtml({
        key: "status",
        select: "many",
        layout: "wrap",
        label: "Status",
        options: statusOptions,
        value: [...state.statuses],
      }) +
      fc.groupHtml({
        key: "window",
        select: "one",
        layout: "joined",
        label: "Started",
        options: windowOptions,
        value: state.window,
      }) +
      fc.menuGroupHtml({
        key: "project",
        select: "one",
        label: "Project",
        options: named(facets?.project),
        value: state.project ?? "all",
        anyLabel: "Any project",
        anyValue: "all",
        open: openMenu === "project",
        menuId: "agents-project-menu",
      }) +
      fc.menuGroupHtml({
        key: "model",
        select: "one",
        label: "Model",
        options: named(facets?.model),
        value: state.model ?? "all",
        anyLabel: "Any model",
        anyValue: "all",
        open: openMenu === "model",
        menuId: "agents-model-menu",
      });
    unbindFilters = fc.bind(filtersEl, {
      onChange(key, value) {
        if (key === "agent") {
          change(withFilter(state, { agent: value === "all" ? null : value }));
        } else if (key === "origin") {
          change(toggleOrigin(state, value));
        } else if (key === "status") {
          change(toggleStatus(state, value));
        } else if (key === "window") {
          change(withFilter(state, { window: /** @type {keyof typeof WINDOWS} */ (value) }));
        }
      },
      onMenuToggle(key, open) {
        openMenu = open ? key : null;
        paintFilters();
      },
      onMenuPick(key, value) {
        openMenu = null;
        const picked = value === null || value === "all" ? null : value;
        change(withFilter(state, key === "project" ? { project: picked } : { model: picked }));
      },
    });
    restore();
  }

  function paintRows() {
    if (!answer) {
      return;
    }
    const page = pageOf(state, answer);
    const progress = progressView(answer.progress, mb.formatInteger);
    summaryEl.textContent =
      answer.total === 0
        ? answer.available === 0 && !answer.progress.complete
          ? progress.text
          : "No sessions match."
        : `${mb.formatInteger(page.first)} to ${mb.formatInteger(page.last)} of ${mb.formatInteger(page.total)} sessions` +
          (answer.totals.running > 0
            ? `, ${mb.formatInteger(answer.totals.running)} running`
            : "") +
          `, ${mb.formatSize(answer.totals.size_bytes)}` +
          (answer.progress.complete ? "" : `. ${progress.text}`);
    tableEl.innerHTML = sessionTableHtml(mb, answer.sessions, {
      columns: COLUMNS.map((column) => column.id),
      now: answer.now,
      sorting: { sort: state.sort, order: state.order },
      caption: "Sessions",
      empty: "No sessions match these filters.",
    });
    pagerEl.hidden = !(page.hasPrevious || page.hasNext);
    pagerEl.innerHTML =
      `<button type="button" class="btn" data-agents-page="previous"${page.hasPrevious ? "" : " disabled"}>Previous</button>` +
      `<button type="button" class="btn" data-agents-page="next"${page.hasNext ? "" : " disabled"}>Next</button>`;
    tableEl.hidden = false;
    root.querySelector(".agents-loading")?.remove();
  }

  function paintFailure() {
    failureEl.hidden = failure === null;
    failureEl.textContent = failure ?? "";
    root.querySelector(".agents-loading")?.remove();
  }

  /** Load the page `state` names; a newer request replaces one still in flight. */
  async function load() {
    flight?.abort();
    const mine = new AbortController();
    flight = mine;
    const token = ++generation;
    try {
      const fetched = await mb.fetchPluginData(
        "agents",
        "sessions",
        queryOf(state, folder, Date.now() / 1000),
        { signal: mine.signal },
      );
      if (disposed || token !== generation) {
        return null;
      }
      answer = /** @type {ListAnswer} */ (/** @type {unknown} */ (fetched));
      failure = null;
      paintFilters();
      paintRows();
      return answer;
    } catch (error) {
      if (disposed || mine.signal.aborted || token !== generation) {
        return null;
      }
      failure = refusal(error).message;
      paintFailure();
      return null;
    }
  }

  /** @param {ListState} next */
  function change(next) {
    if (next === state) {
      return;
    }
    state = next;
    void load();
  }

  const progressPoll = createPoller({
    ...clock,
    isVisible: () => clock.isVisible() && mb.viewState.isActive(container),
    subscribeVisibility(listener) {
      const stopPage = clock.subscribeVisibility(listener);
      const stopView = mb.viewState.subscribeActive(container, listener);
      return () => {
        stopPage();
        stopView();
      };
    },
    intervalMs: PROGRESS_POLL_MS,
    run: async () => {
      const latest = await load();
      return latest ? !latest.progress.complete : true;
    },
  });

  /** @param {MouseEvent} event */
  function onClick(event) {
    if (openSessionLink(mb, event, container)) {
      return;
    }
    const target = /** @type {Element | null} */ (event.target);
    const sort = target?.closest?.("[data-agents-sort]")?.getAttribute("data-agents-sort");
    if (sort) {
      change(withSort(state, sort));
      return;
    }
    const direction = target?.closest?.("[data-agents-page]")?.getAttribute("data-agents-page");
    if (direction === "previous" || direction === "next") {
      change(withPage(state, direction, answer ?? undefined));
      root.scrollIntoView?.({ block: "start" });
    }
  }
  container.addEventListener("click", onClick);

  const ready = (async () => {
    await ensureViewStyles();
    paintFilters();
    const first = await load();
    if (first && !first.progress.complete) {
      progressPoll.start();
    }
  })();

  return Object.freeze({
    ready,
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      flight?.abort();
      progressPoll.dispose();
      unbindFilters?.();
      container.removeEventListener("click", onClick);
      container.replaceChildren();
    },
  });
}
