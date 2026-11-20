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
import { browserClock, createPoller, LIVE_POLL_MS, PROGRESS_POLL_MS } from "./poller.js";
import { sessionTableHtml } from "./session-rows.js";
import {
  agentLabel,
  ensureViewStyles,
  folderParam,
  openSessionLink,
  refusal,
  sessionFile,
  sessionLinkHtml,
  titleOf,
} from "./support.js";

/** The most recent sessions the home lists before the full list. */
export const RECENT_ROWS = 8;

/** The columns of the home's table of recent sessions. */
const RECENT_COLUMNS = Object.freeze(["agent", "title", "project", "activity", "status"]);

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
    const homes = answer.homes
      .map(
        (home) =>
          `<li class="agents-home-item"><span class="agents-agent">${esc(agentLabel(home.agent))}</span> ` +
          `<span class="agents-home-path">${esc(home.path || ".")}</span> ` +
          `<span class="agents-muted">${esc(mb.formatInteger(home.sessions))} sessions, ${esc(mb.formatSize(home.size_bytes))}</span>` +
          (home.discover_limit_reached
            ? ' <span class="agents-muted">(the newest threads only)</span>'
            : "") +
          "</li>",
      )
      .join("");
    slot("head", "agents-head").innerHTML =
      `<h2 class="agents-title">Agents</h2><ul class="agents-homes">${homes}</ul>`;

    const stat = (/** @type {string} */ label, /** @type {string} */ value) =>
      '<div class="agents-stat">' +
      `<span class="agents-stat-label">${esc(label)}</span>` +
      `<span class="agents-stat-value">${esc(value)}</span></div>`;
    const byAgent = Object.entries(totals.by_agent)
      .map(([agent, count]) => `${agentLabel(agent)} ${mb.formatInteger(count)}`)
      .join(" · ");
    slot("totals", "agents-totals").innerHTML =
      '<div class="agents-stats">' +
      stat("Sessions", mb.formatInteger(totals.sessions)) +
      stat("Running now", mb.formatInteger(totals.running)) +
      stat("Size on disk", mb.formatSize(totals.size_bytes)) +
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
      '<h3 class="agents-heading">Sessions per day</h3>' +
      (activity.total === 0
        ? '<p class="agents-empty">No sessions started in the last 90 days.</p>'
        : `<ol class="agents-bars" aria-label="Sessions started per day, oldest first">${bars}</ol>` +
          `<p class="agents-muted">${esc(activity.bars[0].day)} to ${esc(activity.bars[activity.bars.length - 1].day)}; the busiest day started ${esc(mb.formatInteger(activity.peak))}.</p>`);

    const sizes = sizeBars(answer.size_histogram.buckets, mb.formatSize);
    slot("sizes", "agents-sizes").innerHTML =
      '<h3 class="agents-heading">Session sizes</h3>' +
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
    const parts = [
      view.phase === "complete"
        ? `<span>${esc(view.text)}${fresh ? ` Checked ${esc(ageText(fresh, answer.now))}.` : ""}</span>`
        : `<span>${esc(view.text)}</span>`,
    ];
    if (view.fraction !== null && view.phase === "summarizing") {
      parts.push(
        `<progress class="agents-progress-bar" max="1" value="${view.fraction.toFixed(3)}">${esc(view.text)}</progress>`,
      );
    }
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
    const table = sessionTableHtml(mb, recent, {
      columns: RECENT_COLUMNS,
      now: catalog?.now ?? liveNow,
      sorting: null,
      caption: "Most recent sessions",
      empty: "No sessions yet.",
    });
    element.innerHTML =
      '<div class="agents-heading-row"><h3 class="agents-heading">Recent sessions</h3>' +
      '<button type="button" class="btn" data-agents-all-sessions>All sessions</button></div>' +
      table;
  }

  function paintLive() {
    const element = slot("live", "agents-live");
    const esc = (/** @type {string} */ value) => mb.escapeHtml(value);
    element.setAttribute("aria-label", "Running now");
    const rows = live
      .map((row) => {
        const title = row.name || titleOf(row);
        return (
          '<li class="agents-live-row">' +
          `<span class="agents-agent">${esc(agentLabel(row.agent))}</span> ` +
          sessionLinkHtml(mb, title, sessionFile(row)) +
          ` <span class="agents-muted">${esc(row.project ?? "")}${row.models.length ? ` · ${esc(row.models.join(", "))}` : ""}</span>` +
          ` <span class="agents-live-age">${esc(ageText(row.updated_at, liveNow))}</span></li>`
        );
      })
      .join("");
    element.innerHTML =
      '<h3 class="agents-heading">Running now</h3>' +
      (live.length === 0
        ? `<p class="agents-empty">${liveKnown ? "No session is running." : "Checking…"}</p>`
        : `<ul class="agents-live-list">${rows}</ul>`);
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
    run: async (signal) => {
      const answer = await loadCatalog(signal);
      return answer ? !answer.progress.complete : false;
    },
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

  const ready = (async () => {
    await ensureViewStyles();
    try {
      const answer = await loadCatalog(controller.signal);
      if (answer && !answer.progress.complete) {
        progressPoll.start();
      }
    } catch (error) {
      paintError(error);
      return;
    }
    void startLive();
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
