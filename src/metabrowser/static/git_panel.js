// The Git nav panel: commit graph, ref badges, paging, hover cards, and
// the commit-detail view.
//
// Layering, and why it is split this way:
//
//   git_graph.js  pure lane assignment and SVG, ported from VS Code
//   git_panel.js  everything that talks to the network or owns DOM
//
// The row layout mirrors VS Code's `.history-item`: a fixed-width graph
// gutter, then ref badges, subject, author, and relative date. The
// gutter is one width for the whole panel — taken as the max over the
// rows loaded so far — so subjects line up in a column instead of
// stepping in and out as lanes open and close.
//
// Paging is append-only. Lane state at the end of one page is fed back
// in as the start of the next (`trailingSwimlanes`), which is what keeps
// a branch's color and column continuous across a page boundary.

(() => {
  const settings = (typeof window !== "undefined" && window.METABROWSER_SETTINGS) || {};
  const LOG_LIMIT = settings.GIT_LOG_LIMIT || 250;
  const HISTORY_MAX_ROWS = settings.GIT_HISTORY_MAX_ROWS || 500;
  const HOVER_DEBOUNCE_MS = settings.GIT_HOVER_DEBOUNCE_MS || 300;
  const DETAIL_CACHE_SIZE = settings.GIT_DETAIL_CACHE_SIZE || 200;

  // Distance from the bottom at which the next page is requested. One
  // row height would fetch too late to feel seamless; three viewport
  // rows is enough that the page usually lands before the user reaches
  // the end.
  const PAGE_AHEAD_PX = 240;

  /**
   * The panel's whole mutable state. Kept in one object so a reload can
   * reset it with a single assignment and no field can be missed.
   *
   * @typedef {object} PanelState
   * @property {MetabrowserGitCommit[]} commits Every commit loaded so far, in order.
   * @property {MetabrowserGitGraphRow[]} rows Laid-out rows, index-aligned with commits.
   * @property {MetabrowserGitGraphLane[]} trailingSwimlanes Lane state after the last row.
   * @property {number} colorIndex Palette cursor after the last row.
   * @property {string | null} cursor Next-page cursor, null at the end.
   * @property {boolean} loading A page request is in flight.
   * @property {boolean} failed The last page request failed.
   * @property {boolean} capped Older commits were omitted at the client row cap.
   * @property {string | null} headRevision
   * @property {string | null} selectedId
   * @property {number} gutterWidth
   */

  /** @returns {PanelState} */
  function emptyState() {
    return {
      commits: [],
      rows: [],
      trailingSwimlanes: [],
      colorIndex: -1,
      cursor: null,
      loading: false,
      failed: false,
      capped: false,
      headRevision: null,
      selectedId: null,
      gutterWidth: 0,
    };
  }

  /** @type {PanelState} */
  let state = emptyState();
  /** @type {Map<string, string>} */
  let refColors = new Map();
  /** @type {Map<string, MetabrowserGitCommitDetail>} */
  const detailCache = new Map();
  /** @type {ReturnType<typeof setTimeout> | null} */
  let hoverTimer = null;
  let started = false;
  let refreshing = false;

  function graphModule() {
    return window.MetabrowserGitGraph;
  }

  function shell() {
    return window.MetabrowserShell;
  }

  /**
   * @param {string} value
   * @returns {string}
   */
  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /**
   * Compact relative age, matching the tree's convention.
   *
   * @param {number} epochSeconds
   * @returns {string}
   */
  function relativeAge(epochSeconds) {
    if (!Number.isFinite(epochSeconds) || epochSeconds <= 0) {
      return "";
    }
    const seconds = Math.max(0, Date.now() / 1000 - epochSeconds);
    if (seconds < 60) {
      return "just now";
    }
    /** @type {Array<[number, string]>} */
    const units = [
      [60, "m"],
      [3600, "h"],
      [86400, "d"],
      [604800, "w"],
      [2629800, "mo"],
      [31557600, "y"],
    ];
    let label = "";
    for (const [size, suffix] of units) {
      if (seconds >= size) {
        label = `${Math.floor(seconds / size)}${suffix}`;
      }
    }
    return label ? `${label} ago` : "just now";
  }

  /**
   * @param {string} path
   * @param {Record<string, string>} [params]
   * @returns {Promise<Response>}
   */
  function apiFetch(path, params) {
    const query = params ? `?${new URLSearchParams(params).toString()}` : "";
    return fetch(`${path}${query}`);
  }

  // ── Data ───────────────────────────────────────────────────

  /**
   * Fetch the repository gate. A failed request returns null so init or
   * the visible panel can retry without registering a broken surface.
   *
   * @returns {Promise<MetabrowserGitRepoInfo | null>}
   */
  async function fetchRepoInfo() {
    try {
      const response = await apiFetch("/api/git/repo");
      if (!response.ok) {
        return null;
      }
      const info = await response.json();
      return info?.is_repo ? info : null;
    } catch {
      return null;
    }
  }

  /** @returns {Promise<void>} */
  async function loadRefColors() {
    try {
      const response = await apiFetch("/api/git/refs");
      if (!response.ok) {
        refColors = graphModule().buildRefColors(null);
        return;
      }
      const payload = await response.json();
      /** @type {MetabrowserGitRef[]} */
      const refs = payload.refs || [];
      const headRef = refs.find((ref) => ref.is_head);
      refColors = graphModule().buildRefColors(headRef ? headRef.id : null);
    } catch {
      refColors = graphModule().buildRefColors(null);
    }
  }

  /**
   * Load the next page and append it to the panel.
   *
   * Re-entrancy is guarded on `state.loading` rather than by cancelling:
   * pages are append-only and ordered, so a second concurrent request
   * would append out of order and corrupt lane continuity.
   *
   * @param {boolean} initial
   * @returns {Promise<void>}
   */
  async function loadNextPage(initial) {
    if (state.loading) {
      return;
    }
    if (!initial && !state.cursor) {
      return;
    }
    state.loading = true;
    state.failed = false;
    renderPanel();

    try {
      /** @type {Record<string, string>} */
      const params = { limit: String(LOG_LIMIT) };
      if (!initial && state.cursor) {
        params.cursor = state.cursor;
      }
      const response = await apiFetch("/api/git/log", params);
      if (!response.ok) {
        if (!initial && response.status === 400) {
          // A rejected opaque cursor means the append-only paging state is
          // no longer usable. Drop the partial graph so the normal refresh
          // state can restart at page one instead of retrying the same bad
          // cursor every time the tab is shown.
          const headRevision = state.headRevision;
          state = emptyState();
          state.headRevision = headRevision;
        }
        throw new Error(`HTTP ${response.status}`);
      }
      const page = await response.json();
      if (!page.is_repo) {
        teardown();
        return;
      }
      appendPage(page.commits || [], page.cursor ?? null);
    } catch {
      state.failed = true;
    } finally {
      state.loading = false;
      renderPanel();
    }
  }

  /**
   * @param {MetabrowserGitCommit[]} commits
   * @param {string | null} cursor
   */
  function appendPage(commits, cursor) {
    const remaining = Math.max(0, HISTORY_MAX_ROWS - state.rows.length);
    const accepted = commits.slice(0, remaining);
    const reachesCap = state.rows.length + accepted.length >= HISTORY_MAX_ROWS;
    const omitted = commits.length > accepted.length || (reachesCap && cursor !== null);
    if (accepted.length === 0) {
      state.capped = state.capped || omitted;
      state.cursor = null;
      return;
    }

    const graph = graphModule();
    const result = graph.computeSwimlanes(accepted, {
      priorSwimlanes: state.trailingSwimlanes,
      colorIndex: state.colorIndex,
      headRevision: state.headRevision,
      refColors,
    });

    state.commits = state.commits.concat(accepted);
    state.rows = state.rows.concat(result.rows);
    state.trailingSwimlanes = result.trailingSwimlanes;
    state.colorIndex = result.colorIndex;
    state.capped = state.capped || omitted;
    state.cursor = state.capped ? null : cursor;
    for (const row of result.rows) {
      state.gutterWidth = Math.max(state.gutterWidth, graph.graphWidth(row));
    }
  }

  /**
   * Fetch one commit's detail, through a bounded cache.
   *
   * The cache is what makes hovering a row and then clicking it a single
   * request: both surfaces read the same payload.
   *
   * @param {string} revision
   * @returns {Promise<MetabrowserGitCommitDetail | null>}
   */
  async function fetchCommitDetail(revision) {
    const cached = detailCache.get(revision);
    if (cached) {
      return cached;
    }
    try {
      const response = await apiFetch(`/api/git/commit/${revision}`);
      if (!response.ok) {
        return null;
      }
      const detail = await response.json();
      if (!detail?.is_repo) {
        return null;
      }
      // Insertion-ordered eviction: Map preserves insertion order, so
      // the first key is the oldest entry.
      if (detailCache.size >= DETAIL_CACHE_SIZE) {
        const oldest = detailCache.keys().next();
        if (!oldest.done) {
          detailCache.delete(oldest.value);
        }
      }
      detailCache.set(revision, detail);
      return detail;
    } catch {
      return null;
    }
  }

  // ── Panel rendering ────────────────────────────────────────

  function panelElement() {
    return document.getElementById("tab-git");
  }

  /**
   * @param {HTMLElement} panel
   * @param {string} message
   */
  function renderRefreshState(panel, message) {
    const empty = document.createElement("div");
    empty.className = "git-panel-empty";
    const label = document.createElement("div");
    label.textContent = message;
    empty.appendChild(label);

    const refresh = document.createElement("button");
    refresh.type = "button";
    refresh.className = "btn git-panel-refresh";
    refresh.textContent = "Refresh";
    refresh.addEventListener("click", () => {
      void refreshHistory();
    });
    empty.appendChild(refresh);
    panel.replaceChildren(empty);
  }

  function renderPanel() {
    const panel = panelElement();
    if (!panel) {
      return;
    }

    if (state.rows.length === 0 && state.loading) {
      panel.innerHTML = '<div class="loading"><div class="spinner"></div>Loading history…</div>';
      return;
    }
    if (state.rows.length === 0 && state.failed) {
      renderRefreshState(panel, "Could not read repository history.");
      return;
    }
    if (state.rows.length === 0) {
      // A repository with no commits yet. Distinct from a failure, and
      // it should read that way.
      renderRefreshState(panel, "No commits yet.");
      return;
    }

    const list = document.createElement("div");
    list.className = "git-graph-list";
    for (const row of state.rows) {
      list.appendChild(renderRow(row));
    }
    if (state.loading) {
      const more = document.createElement("div");
      more.className = "git-graph-more";
      more.textContent = "Loading…";
      list.appendChild(more);
    } else if (state.failed) {
      const failed = document.createElement("div");
      failed.className = "git-graph-more git-graph-more-failed";
      failed.textContent = "Could not load more history.";
      list.appendChild(failed);
    } else if (state.capped) {
      const capped = document.createElement("div");
      capped.className = "git-graph-more";
      capped.textContent = `Showing the newest ${HISTORY_MAX_ROWS} commits.`;
      list.appendChild(capped);
    }

    panel.replaceChildren(list);
  }

  /**
   * @param {MetabrowserGitGraphRow} row
   * @returns {HTMLElement}
   */
  function renderRow(row) {
    const commit = row.commit;
    const element = document.createElement("div");
    element.className = "git-graph-row";
    element.dataset.revision = commit.id;
    element.setAttribute("role", "button");
    element.setAttribute("tabindex", "0");
    if (commit.id === state.selectedId) {
      element.classList.add("selected");
    }

    const gutter = document.createElement("div");
    gutter.className = "git-graph-gutter";
    // One width for every row so the subject column does not step in and
    // out as lanes open and close.
    gutter.style.width = `${state.gutterWidth}px`;
    gutter.appendChild(graphModule().renderCommitGraph(row));
    element.appendChild(gutter);

    const body = document.createElement("div");
    body.className = "git-graph-body";
    body.innerHTML =
      renderRefBadges(commit.refs || []) +
      `<span class="git-graph-subject">${escapeHtml(commit.subject)}</span>` +
      `<span class="git-graph-meta">${escapeHtml(commit.author?.name || "")}` +
      `<span class="git-graph-age">${escapeHtml(relativeAge(commit.committed_at))}</span></span>`;
    element.appendChild(body);

    element.addEventListener("click", () => selectCommit(commit.id));
    element.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectCommit(commit.id);
      }
    });
    element.addEventListener("mouseenter", () => scheduleHover(element, commit.id));
    element.addEventListener("mouseleave", cancelHover);
    return element;
  }

  /**
   * @param {MetabrowserGitRef[]} refs
   * @returns {string}
   */
  function renderRefBadges(refs) {
    if (!refs.length) {
      return "";
    }
    return refs
      .map((ref) => {
        const classes = ["git-ref", `git-ref-${escapeHtml(ref.kind)}`];
        if (ref.is_head) {
          classes.push("git-ref-head");
        }
        return `<span class="${classes.join(" ")}">${escapeHtml(ref.name)}</span>`;
      })
      .join("");
  }

  // ── Hover card ─────────────────────────────────────────────

  /**
   * @param {HTMLElement} rowElement
   * @param {string} revision
   */
  function scheduleHover(rowElement, revision) {
    cancelHover();
    // Debounced because the hover is backed by a real request: dragging
    // the pointer down the graph must not fire one per row.
    hoverTimer = setTimeout(async () => {
      const detail = await fetchCommitDetail(revision);
      if (!detail) {
        return;
      }
      // The pointer may have left during the request.
      if (!rowElement.matches(":hover")) {
        return;
      }
      rowElement.title = hoverText(detail);
    }, HOVER_DEBOUNCE_MS);
  }

  function cancelHover() {
    if (hoverTimer !== null) {
      clearTimeout(hoverTimer);
      hoverTimer = null;
    }
  }

  /**
   * The hover card body: full message plus this commit's line counts.
   *
   * A native title attribute rather than a custom popover — it needs no
   * positioning logic, no dismissal handling, and no z-index against the
   * resize handle, and the content is plain text.
   *
   * @param {MetabrowserGitCommitDetail} detail
   * @returns {string}
   */
  function hoverText(detail) {
    const commit = detail.commit;
    const stats = detail.stats || {};
    const parts = [commit.subject];
    if (detail.body) {
      parts.push("", detail.body);
    }
    parts.push("");
    parts.push(`${commit.author?.name || ""} · ${commit.short_id}`);
    parts.push(
      `${stats.files_changed || 0} file(s) changed, ` +
        `+${stats.additions || 0} −${stats.deletions || 0}`,
    );
    return parts.join("\n");
  }

  // ── Commit detail view ─────────────────────────────────────

  /**
   * @param {string} revision
   * @returns {Promise<void>}
   */
  async function selectCommit(revision) {
    const bridge = shell();
    if (!bridge) {
      return;
    }
    const previewClaim = bridge.claimPreview("git");
    state.selectedId = revision;
    for (const element of document.querySelectorAll(".git-graph-row")) {
      element.classList.toggle(
        "selected",
        element instanceof HTMLElement && element.dataset.revision === revision,
      );
    }

    const preview = bridge.renderPreviewHtml(
      '<div class="loading"><div class="spinner"></div>Loading commit…</div>',
      previewClaim,
    );
    if (!preview) {
      return;
    }

    const detail = await fetchCommitDetail(revision);
    // A different commit or another preview owner won while this request
    // was in flight.
    if (state.selectedId !== revision || !bridge.isPreviewClaimCurrent(previewClaim)) {
      return;
    }
    if (!detail) {
      bridge.renderPreviewHtml(
        '<div class="preview-empty">Could not load this commit.</div>',
        previewClaim,
      );
      return;
    }
    renderCommitDetail(detail, previewClaim);
  }

  /**
   * @param {MetabrowserGitCommitDetail} detail
   * @param {number} [claim]
   */
  function renderCommitDetail(detail, claim) {
    const bridge = shell();
    if (!bridge) {
      return;
    }
    const previewClaim = claim ?? bridge.claimPreview("git");
    const commit = detail.commit;
    const stats = detail.stats || {};
    const files = detail.files || [];

    let html = '<div class="git-commit-view">';
    html += '<div class="git-commit-header">';
    html += `<h1 class="git-commit-subject">${escapeHtml(commit.subject)}</h1>`;
    html += '<div class="git-commit-meta">';
    html += `<span class="git-commit-sha">${escapeHtml(commit.short_id)}</span>`;
    html += `<span>${escapeHtml(commit.author?.name || "")}</span>`;
    html += `<span>${escapeHtml(relativeAge(commit.committed_at))}</span>`;
    html += "</div>";
    if (commit.refs?.length) {
      html += `<div class="git-commit-refs">${renderRefBadges(commit.refs)}</div>`;
    }
    html += "</div>";

    if (detail.body) {
      html += `<pre class="git-commit-body">${escapeHtml(detail.body)}</pre>`;
    }

    html += '<div class="git-commit-files">';
    html += '<div class="git-commit-files-summary">';
    html += `${stats.files_changed || 0} file${stats.files_changed === 1 ? "" : "s"} changed`;
    html += `<span class="git-stat-add">+${stats.additions || 0}</span>`;
    html += `<span class="git-stat-del">−${stats.deletions || 0}</span>`;
    html += "</div>";
    html += files.map(renderFileRow).join("");
    if (detail.files_truncated) {
      // Say what was cut. A silently shortened list reads as a complete
      // one, which is the worse failure.
      html += `<div class="git-commit-file git-commit-file-note">Showing the first ${
        files.length
      } of ${stats.files_changed || files.length} changed files.</div>`;
    }
    html += "</div></div>";

    const preview = bridge.renderPreviewHtml(html, previewClaim);
    if (!preview) {
      return;
    }

    for (const element of preview.querySelectorAll(".git-commit-file[data-path]")) {
      element.addEventListener("click", () => {
        const path = element instanceof HTMLElement ? element.dataset.path : null;
        if (path) {
          // The documented navigation namespace. The `metabrowser:open-path`
          // event this used to dispatch was removed with the SDK 0.2 break,
          // with no shim, so dispatching it now navigates nowhere.
          void window.MetabrowserNavigationRoute.navigation.open({ path });
        }
      });
    }
  }

  /**
   * @param {MetabrowserGitFileChange} file
   * @returns {string}
   */
  function renderFileRow(file) {
    const classes = ["git-commit-file", `git-file-${escapeHtml(file.status)}`];
    // Files outside the served root are shown — hiding them would
    // misreport what the commit changed — but are not navigable, since
    // the safe-path layer would refuse to open them.
    const navigable = !file.outside_root && file.status !== "deleted";
    if (!navigable) {
      classes.push("git-commit-file-inert");
    }
    const tag = navigable ? "button" : "div";
    const attrs = navigable ? ` type="button" data-path="${escapeHtml(file.path)}"` : "";

    let counts = "";
    if (file.binary) {
      counts = '<span class="git-stat-binary">binary</span>';
    } else {
      counts =
        `<span class="git-stat-add">+${file.additions ?? 0}</span>` +
        `<span class="git-stat-del">−${file.deletions ?? 0}</span>`;
    }

    let name = escapeHtml(file.path);
    if (file.old_path) {
      name = `${escapeHtml(file.old_path)} → ${name}`;
    }

    return (
      `<${tag} class="${classes.join(" ")}"${attrs}>` +
      `<span class="git-file-status" title="${escapeHtml(file.status)}">` +
      `${escapeHtml(file.status.charAt(0).toUpperCase())}</span>` +
      `<span class="git-file-path">${name}</span>${counts}</${tag}>`
    );
  }

  // ── Paging on scroll ───────────────────────────────────────

  function onTreeScroll() {
    const content = document.getElementById("tree-content");
    const panel = panelElement();
    if (!content || !panel || panel.style.display === "none") {
      return;
    }
    if (state.loading || !state.cursor) {
      return;
    }
    const remaining = content.scrollHeight - content.scrollTop - content.clientHeight;
    if (remaining < PAGE_AHEAD_PX) {
      void loadNextPage(false);
    }
  }

  // ── Lifecycle ──────────────────────────────────────────────

  /** @returns {Promise<void>} */
  async function refreshHistory() {
    if (state.loading || refreshing) {
      return;
    }

    refreshing = true;
    state = emptyState();
    // The detail cache is keyed by object id, but a commit's *payload*
    // is not immutable: its refs move as branches and tags do. Keeping
    // the cache across a refresh would let the hover card and detail
    // view serve pre-refresh refs for a row the graph just redrew.
    detailCache.clear();
    state.loading = true;
    renderPanel();
    try {
      const info = await fetchRepoInfo();
      if (!info) {
        state.loading = false;
        state.failed = true;
        renderPanel();
        return;
      }
      state.headRevision = info.head?.revision ?? null;

      // Ref colors are an input to lane assignment, so they must settle
      // before the first page is laid out.
      await loadRefColors();
      state.loading = false;
      await loadNextPage(true);
    } finally {
      refreshing = false;
    }
  }

  /** @returns {Promise<void>} */
  async function ensureHistory() {
    if (state.loading) {
      return;
    }
    if (state.rows.length === 0) {
      await refreshHistory();
      return;
    }

    // HEAD is an input to lane layout, baked into each row when the page
    // was laid out — so a checkout made while another tab was showing
    // cannot be repainted, only recomputed. Re-reading identity on every
    // activation is what catches that; the response is TTL-cached
    // server-side, so a tab switch that changes nothing costs nothing.
    const info = await fetchRepoInfo();
    if (!info) {
      // The served root stopped being a repository under us.
      teardown();
      return;
    }
    if ((info.head?.revision ?? null) !== state.headRevision) {
      await refreshHistory();
      return;
    }

    if (state.failed && state.cursor) {
      await loadNextPage(false);
    }
  }

  function teardown() {
    state = emptyState();
    detailCache.clear();
    refColors = new Map();
    started = false;
    shell()?.removeNavPanel("git");
  }

  /**
   * Register the Git tab if the served root is a repository.
   *
   * Called once at startup and never awaited by the shell: whether this
   * is a repository has no bearing on first paint, and a directory that
   * is not one should not pay for the feature at all.
   *
   * @returns {Promise<void>}
   */
  async function init() {
    const bridge = shell();
    if (started || !graphModule() || !bridge) {
      return;
    }
    started = true;

    const info = await fetchRepoInfo();
    if (!info) {
      started = false;
      return;
    }
    state.headRevision = info.head?.revision ?? null;

    bridge.registerNavPanel({
      id: "git",
      label: "Git",
      onFirstShow: null,
      onShow: () => {
        void ensureHistory();
      },
    });

    document
      .getElementById("tree-content")
      ?.addEventListener("scroll", onTreeScroll, { passive: true });
  }

  window.MetabrowserGitPanel = Object.freeze({
    init,
    // Exposed for tests, which drive the panel without a network.
    _internals: {
      appendPage,
      emptyState,
      hoverText,
      relativeAge,
      renderCommitDetail,
      renderFileRow,
      renderPanel,
      renderRefBadges,
      selectCommit,
      setStateForTests: (/** @type {PanelState} */ next) => {
        state = next;
      },
      stateForTests: () => state,
    },
  });
})();
