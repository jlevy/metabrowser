// The agents home: one page for the Claude Code and Codex homes under a served folder.
//
// A folder view of the `folder` kind that the plugin offers only where `holds_homes`
// accepts the folder (manifest.toml), and that is then the folder's default. Its data is
// the `catalog`, `sessions`, and `live` routes, each reached from a command line with
// `metab --api` (docs/project/architecture/arch-views-models-routes.md, "Agent Catalog").
//
// Two polls keep it current, both through `createPoller`, so neither runs while the page
// is hidden or its view is not the one in front:
//
// - Summary progress. The first answer of a large home is partial, since the summary pass
//   reads every transcript. While `progress.complete` is false the page asks `catalog`
//   again, and stops when the route says the pass is complete.
// - The live strip asks `live` for the sessions something vouches for.
//
// The code is loaded on demand: index.js registers a stub for the view and imports this
// module the first time a home is shown.

import { activityBars, ageText, progressView, sizeBars } from "./home-model.js";
import {
  browserClock,
  createPoller,
  isRetryable,
  LIVE_POLL_MS,
  PROGRESS_POLL_MS,
  progressRun,
} from "./poller.js";
import { sessionRowsHtml } from "./session-rows.js";
import {
  agentLabel,
  countHtml,
  ensureViewStyles,
  folderParam,
  joinGroups,
  openSessionLink,
  refusal,
  separatorHtml,
  sessionFile,
  titleOf,
} from "./support.js";

/** The most recent sessions the home lists before the full list. */
export const RECENT_ROWS = 8;

/** @typedef {import("./session-rows.js").SessionRow} SessionRow */

/**
 * @typedef {object} CatalogAnswer
 * @property {string} folder
 * @property {number} now
 * @property {ReadonlyArray<{agent: string, path: string, state: string, sessions: number, running: number, size_bytes: number, discover_limit_reached: boolean}>} homes
 * @property {{sessions: number, summarized: number, running: number, size_bytes: number, by_agent: Record<string, number>}} totals
 * @property {{buckets: ReadonlyArray<{lower: number, upper: number | null, count: number}>}} size_histogram
 * @property {ReadonlyArray<{day: string, sessions: number}>} per_day
 * @property {import("./home-model.js").Progress} progress
 * @property {{summary_pass_at: number | null}} freshness
 * @property {{state: string}} cache
 */

/**
 * @typedef {object} LiveRow
 * @property {string} agent
 * @property {string} session_id
 * @property {string | null} title
 * @property {string | null} name
 * @property {string | null} project
 * @property {ReadonlyArray<string>} models
 * @property {ReadonlyArray<string>} source_paths
 * @property {number | null} updated_at
 */

/** @param {MetabrowserPublicSdk} mb */
export function createHomeView(mb) {
  return Object.freeze({
    /** @param {HTMLElement} container @param {{path?: string}} ctx */
    render: (container, ctx) => mountHome(container, ctx, mb),
  });
}

/**
 * @param {HTMLElement} container
 * @param {{path?: string}} ctx
 * @param {MetabrowserPublicSdk} mb
 */
export function mountHome(container, ctx, mb) {
  const folder = folderParam(ctx.path);
  const clock = browserClock();
  const controller = new AbortController();
  let disposed = false;
  /** @type {CatalogAnswer | null} */
  let catalog = null;
  /** @type {ReadonlyArray<SessionRow>} */
  let recent = [];
  /** @type {ReadonlyArray<LiveRow>} */
  let live = [];
  /** @type {number | null} */
  let liveTotal = null;
  let liveKnown = false;
  let liveNow = Date.now() / 1000;

  container.replaceChildren();
  const root = document.createElement("div");
  root.className = "agents-home";
  root.innerHTML =
    '<div class="agents-loading mb-delayed-loading" aria-hidden="true"></div>' +
    '<div class="agents-sections" hidden></div>';
  container.append(root);
  const sections = /** @type {HTMLElement} */ (root.querySelector(".agents-sections"));

  const visible = () => clock.isVisible() && mb.viewState.isActive(container);
  const subscribe = (/** @type {() => void} */ listener) => {
    const stopPage = clock.subscribeVisibility(listener);
    const stopView = mb.viewState.subscribeActive(container, listener);
    return () => {
      stopPage();
      stopView();
    };
  };

  /** One section's slot, created on first paint so a repaint replaces its content only. */
  const slots = new Map();
  /** @param {string} name @param {string} className */
  function slot(name, className) {
    let element = slots.get(name);
    if (!element) {
      element = document.createElement("section");
      element.className = `agents-section ${className}`;
      sections.append(element);
      slots.set(name, element);
    }
    return element;
  }

  function paintCatalog() {
    if (!catalog) {
      return;
    }
    const answer = catalog;
    const esc = (/** @type {string} */ value) => mb.escapeHtml(value);
    const totals = answer.totals;
    // The served folder's own home has the path "", which names nothing to show.
    const homes = answer.homes
      .map((home) => {
        const where = home.path && home.path !== "." ? esc(home.path) : "";
        const counts = countHtml(mb, [
          { number: mb.formatInteger(home.sessions) },
          " sessions",
          { punctuation: "," },
          " ",
          { number: mb.formatSize(home.size_bytes) },
        ]);
        return `<li class="agents-home-item">${joinGroups(mb, [
          `<span class="agents-agent">${esc(agentLabel(home.agent))}</span>`,
          where ? `<span class="agents-home-path">${where}</span>` : "",
          `<span class="agents-muted">${counts}${home.discover_limit_reached ? " (the newest threads only)" : ""}</span>`,
        ])}</li>`;
      })
      .join("");
    slot("head", "agents-head").innerHTML =
      `<h2 class="agents-title page-heading">Agents</h2><ul class="agents-homes">${homes}</ul>`;

    const stat = (/** @type {string} */ label, /** @type {string} */ value) =>
      '<div class="agents-stat">' +
      `<span class="agents-stat-label">${esc(label)}</span>` +
      `<span class="agents-stat-value">${value}</span></div>`;
    const byAgent = Object.entries(totals.by_agent)
      .map(([agent, count]) => `${esc(agentLabel(agent))} ${esc(mb.formatInteger(count))}`)
      .join(separatorHtml(mb));
    slot("totals", "agents-totals").innerHTML =
      '<div class="agents-stats">' +
      stat("Sessions", esc(mb.formatInteger(totals.sessions))) +
      stat(
        "Active",
        `<span class="agents-active-count">${liveTotal === null ? "—" : esc(mb.formatInteger(liveTotal))}</span>`,
      ) +
      stat("Size on disk", esc(mb.formatSize(totals.size_bytes))) +
      (byAgent ? stat("By agent", byAgent) : "") +
      "</div>";

    paintProgress(answer);

    const activity = activityBars(answer.per_day, answer.now);
    const bars = activity.bars
      .map(
        (bar) =>
          `<li class="agents-bar" style="--agents-bar-size: ${(bar.height * 100).toFixed(1)}%" ` +
          `data-tip-text="${esc(bar.day)}: ${esc(mb.formatInteger(bar.sessions))} sessions"></li>`,
      )
      .join("");
    slot("activity", "agents-activity").innerHTML =
      '<h3 class="section-heading agents-heading">Sessions per day</h3>' +
      (activity.total === 0
        ? '<p class="agents-empty">No sessions started in the last 90 days.</p>'
        : `<ol class="agents-bars" aria-label="Sessions started per day, oldest first">${bars}</ol>` +
          `<p class="agents-muted">${esc(activity.bars[0].day)} to ${esc(activity.bars[activity.bars.length - 1].day)}; the busiest day started ${esc(mb.formatInteger(activity.peak))}.</p>`);

    const sizes = sizeBars(answer.size_histogram.buckets, mb.formatSize);
    slot("sizes", "agents-sizes").innerHTML =
      '<h3 class="section-heading agents-heading">Session sizes</h3>' +
      (sizes.bars.length === 0
        ? '<p class="agents-empty">No sessions yet.</p>'
        : '<ol class="agents-histogram" aria-label="Sessions by size on disk">' +
          sizes.bars
            .map(
              (bar) =>
                '<li class="agents-histogram-row">' +
                `<span class="agents-histogram-label">${esc(bar.label)}</span>` +
                `<span class="agents-histogram-track"><span class="agents-histogram-fill" style="--agents-bar-size: ${(bar.height * 100).toFixed(1)}%"></span></span>` +
                `<span class="agents-histogram-count">${esc(mb.formatInteger(bar.count))}</span></li>`,
            )
            .join("") +
          "</ol>");
    paintRecent();
    reveal();
  }

  function paintProgress(/** @type {CatalogAnswer} */ answer) {
    const view = progressView(answer.progress, mb.formatInteger);
    const esc = (/** @type {string} */ value) => mb.escapeHtml(value);
    const fresh = answer.freshness.summary_pass_at;
    const busy = view.phase === "scanning" || view.phase === "summarizing";
    const freshness =
      view.phase === "complete" && fresh ? ` Checked ${ageText(fresh, answer.now)}.` : "";
    const parts = [
      busy ? '<span class="index-progress-spinner" aria-hidden="true"></span>' : "",
      `<span>${esc(view.text + freshness)}</span>`,
    ];
    if (answer.cache.state === "unavailable") {
      parts.push(
        '<span class="agents-muted">No private cache folder is available, so summaries are kept in memory and read again after a restart.</span>',
      );
    }
    const element = slot("progress", "agents-progress");
    element.setAttribute("role", "status");
    element.setAttribute("data-phase", view.phase);
    element.innerHTML = parts.join(" ");
  }

  function paintRecent() {
    const element = slot("recent", "agents-recent");
    const now = catalog?.now ?? liveNow;
    const rows =
      recent.length === 0
        ? '<p class="agents-empty">No sessions yet.</p>'
        : sessionRowsHtml(
            mb,
            recent.map((row) => ({
              agent: row.agent,
              session_id: row.session_id,
              title: titleOf(row),
              path: sessionFile(row),
              age: ageText(row.last_activity, now),
              project: row.project,
              models: row.models,
              status: row.status,
            })),
            { label: "Latest sessions" },
          );
    element.innerHTML =
      '<div class="agents-heading-row"><h3 class="section-heading agents-heading">Latest sessions</h3>' +
      `<button type="button" class="btn" data-agents-all-sessions>All sessions</button></div>${rows}`;
  }

  function paintLive() {
    const element = slot("live", "agents-live");
    element.setAttribute("aria-label", "Active sessions");
    const rows = sessionRowsHtml(
      mb,
      live.map((row) => ({
        agent: row.agent,
        session_id: row.session_id,
        title: row.name || titleOf(row),
        path: sessionFile(row),
        age: ageText(row.updated_at, liveNow),
        project: row.project,
        models: row.models,
        status: null,
      })),
      { label: "Active sessions" },
    );
    const emptyText =
      liveTotal === 0
        ? "No active sessions detected."
        : liveKnown
          ? "Activity unavailable."
          : "Checking…";
    element.innerHTML =
      '<h3 class="section-heading agents-heading">Active sessions</h3>' +
      '<p class="agents-muted agents-live-note">Claude Code processes and recent Codex activity.</p>' +
      (live.length === 0 ? `<p class="agents-empty">${emptyText}</p>` : rows);
    reorder();
  }

  /** The sections' order is fixed, whichever answer arrived first. */
  function reorder() {
    for (const name of ["head", "totals", "progress", "live", "activity", "sizes", "recent"]) {
      const element = slots.get(name);
      if (element) {
        sections.append(element);
      }
    }
  }

  function reveal() {
    reorder();
    sections.hidden = false;
    root.querySelector(".agents-loading")?.remove();
  }

  /** @param {unknown} error */
  function paintError(error) {
    if (disposed || controller.signal.aborted) {
      return;
    }
    const { message } = refusal(error);
    sections.hidden = false;
    root.querySelector(".agents-loading")?.remove();
    slot("error", "agents-error").innerHTML =
      `<div class="notice" data-severity="error" role="alert">${mb.escapeHtml(message)}</div>`;
  }

  /** @param {AbortSignal} signal */
  async function loadCatalog(signal) {
    const [answer, listing] = await Promise.all([
      mb.fetchPluginData("agents", "catalog", { folder }, { signal }),
      mb.fetchPluginData(
        "agents",
        "sessions",
        { folder, sort: "activity", limit: RECENT_ROWS },
        { signal },
      ),
    ]);
    if (signal.aborted || disposed) {
      return null;
    }
    catalog = /** @type {CatalogAnswer} */ (/** @type {unknown} */ (answer));
    recent = /** @type {ReadonlyArray<SessionRow>} */ (listing.sessions ?? []);
    liveNow = catalog.now;
    slots.get("error")?.remove();
    slots.delete("error");
    paintCatalog();
    return catalog;
  }

  /** @param {AbortSignal} signal */
  async function loadLive(signal) {
    const answer = await mb.fetchPluginData("agents", "live", { folder }, { signal });
    if (signal.aborted || disposed) {
      return;
    }
    live = /** @type {ReadonlyArray<LiveRow>} */ (answer.sessions ?? []);
    liveTotal = typeof answer.total === "number" ? answer.total : live.length;
    const activeCount = slots.get("totals")?.querySelector(".agents-active-count");
    if (activeCount) {
      activeCount.textContent = mb.formatInteger(liveTotal);
    }
    liveKnown = true;
    liveNow = typeof answer.now === "number" ? answer.now : Date.now() / 1000;
    paintLive();
    // The recent table's ages and the progress line's follow the same clock.
    if (catalog) {
      paintRecent();
    }
  }

  const progressPoll = createPoller({
    ...clock,
    isVisible: visible,
    subscribeVisibility: subscribe,
    intervalMs: PROGRESS_POLL_MS,
    // Also the retry of a first load that failed: a failed tick backs off, and the first
    // answer to arrive starts the live strip the failure held back.
    run: progressRun(async (signal) => {
      const answer = await loadCatalog(signal);
      if (answer) {
        startLiveOnce();
      }
      return answer;
    }),
  });
  const livePoll = createPoller({
    ...clock,
    isVisible: visible,
    subscribeVisibility: subscribe,
    intervalMs: LIVE_POLL_MS,
    run: (signal) => loadLive(signal),
  });

  // The page is ready when the catalog has painted; the live strip fills in after, and its
  // poll starts once its first answer, or its failure, is in.
  async function startLive() {
    paintLive();
    try {
      await loadLive(controller.signal);
    } catch (_error) {
      // The strip is a convenience: the page already shows the catalog.
      liveKnown = true;
      paintLive();
    }
    if (!disposed) {
      livePoll.start();
    }
  }

  let liveStarted = false;
  function startLiveOnce() {
    if (!liveStarted && !disposed) {
      liveStarted = true;
      void startLive();
    }
  }

  const ready = (async () => {
    await ensureViewStyles();
    try {
      const answer = await loadCatalog(controller.signal);
      if (answer && !answer.progress.complete) {
        progressPoll.start();
      }
    } catch (error) {
      paintError(error);
      if (isRetryable(error)) {
        progressPoll.start();
      }
      return;
    }
    startLiveOnce();
  })();

  /** @param {MouseEvent} event */
  function onClick(event) {
    if (openSessionLink(mb, event, container)) {
      return;
    }
    const target = /** @type {Element | null} */ (event.target);
    if (target?.closest?.("[data-agents-all-sessions]")) {
      void mb.navigation.open({ path: folder }, { viewId: "agent-sessions" });
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
      progressPoll.dispose();
      livePoll.dispose();
      container.removeEventListener("click", onClick);
      slots.clear();
      container.replaceChildren();
    },
  });
}
