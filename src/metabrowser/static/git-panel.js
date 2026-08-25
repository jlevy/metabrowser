// The Git nav panel: commit graph, ref badges, paging, hover cards, and
// the commit-detail view.
//
// Layering, and why it is split this way:
//
//   git-graph.js  pure lane assignment and SVG, ported from VS Code
//   git-panel.js  everything that talks to the network or owns DOM
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
  const HOVER_DEBOUNCE_MS = settings.GIT_HOVER_DEBOUNCE_MS ?? 300;
  const DETAIL_CACHE_SIZE = settings.GIT_DETAIL_CACHE_SIZE || 200;
  // Initial empty loads keep the measured quiet period. Retained content uses
  // the shell's immediate preview-navigation state instead.
  const PENDING_DELAY_MS = 120;

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
    };
  }

  /** @type {PanelState} */
  let state = emptyState();
  /** @type {{cancelPending?: () => void, dispose?: () => void} | null} The mounted commit diff. */
  let commitDiffHandle = null;
  /**
   * The commit named by the URL this page was opened with, if any. Read
   * once: later selections rewrite the URL, so re-reading it would make
   * the restore chase its own writes.
   *
   * @type {{revision: string, file: string} | null}
   */
  const routeSelection =
    window.MetabrowserNavigationRoute?.parseCommit?.(window.location?.pathname ?? "") ?? null;
  /** @type {Map<string, string>} */
  let refColors = new Map();
  /** @type {Map<string, MetabrowserGitCommitDetail>} */
  const detailCache = new Map();
  /** @type {Map<string, Promise<MetabrowserGitCommitDetail | null>>} */
  const detailInFlight = new Map();
  /**
   * @typedef {object} RevisionPreparation
   * @property {string} revision
   * @property {Promise<MetabrowserGitCommitDetail | null>} detail
   * @property {Promise<void>} assets
   * @property {Promise<unknown> | undefined} comparison
   * @property {AbortController | null} controller
   * @property {boolean} speculative
   */
  /** @type {RevisionPreparation | null} */
  let preparationSlot = null;
  /** @type {ReturnType<typeof setTimeout> | null} */
  let hoverTimer = null;
  /** @type {string | null} */
  let hoverRevision = null;
  /** @type {ReturnType<typeof setTimeout> | null} */
  let pendingTimer = null;
  /** @type {number | null} */
  let pendingPreviewClaim = null;
  let started = false;
  let refreshing = false;

  function graphModule() {
    return window.MetabrowserGitGraph;
  }

  function shell() {
    return window.MetabrowserShell;
  }

  /** The plugin SDK, which owns the view registry this panel composes. */
  function sdk() {
    return window.metabrowser;
  }

  /** @returns {string} */
  function copyIcon() {
    return sdk()?.icons?.copy || "⧉";
  }

  function perf() {
    return window.metabrowser?.perf;
  }

  /**
   * @template T
   * @param {string} label
   * @param {() => T} work
   * @param {Record<string, unknown>} [meta]
   * @returns {T}
   */
  function measure(label, work, meta) {
    return perf()?.measure?.(label, work, meta) ?? work();
  }

  /**
   * @template T
   * @param {string} label
   * @param {() => Promise<T>} work
   * @param {Record<string, unknown>} [meta]
   * @returns {Promise<T>}
   */
  function measureAsync(label, work, meta) {
    return perf()?.measureAsync?.(label, work, meta) ?? work();
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
   * @param {Record<string, unknown>} stats
   * @param {number} fallbackFiles
   * @param {boolean} filesTruncated
   * @returns {string}
   */
  function renderCommitChangeStats(stats, fallbackFiles, filesTruncated) {
    const fileCount = stats.files_changed ?? (filesTruncated ? "?" : fallbackFiles);
    const additions = stats.additions ?? "?";
    const deletions = stats.deletions ?? "?";
    const fileLabel = Number(fileCount) === 1 ? "file" : "files";
    return (
      '<span class="git-commit-change-stats">' +
      `<span class="git-commit-change-files">${escapeHtml(String(fileCount))} changed ${fileLabel}</span>` +
      `<span class="git-stat-add">+${escapeHtml(String(additions))}</span>` +
      `<span class="git-stat-del">−${escapeHtml(String(deletions))}</span>` +
      "</span>"
    );
  }

  /**
   * Render the complete commit summary as one component. The comparison,
   * out-of-root files, and bounds remain siblings because they describe the
   * rendered change rather than the commit's identity and message.
   *
   * @param {MetabrowserGitCommitDetail} detail
   * @param {{compact?: boolean}} [options]
   * @returns {string}
   */
  function renderCommitSummary(detail, options = {}) {
    const commit = detail.commit;
    const stats = detail.stats || {};
    const files = detail.files || [];
    const compact = options.compact === true;
    const summaryClass = compact
      ? "git-commit-summary git-commit-summary-compact"
      : "git-commit-summary";
    const subjectTag = compact ? "div" : "h1";
    let html = `<section class="${summaryClass}" aria-label="Commit summary">`;
    html += '<div class="git-commit-header">';
    html += `<${subjectTag} class="git-commit-subject">${escapeHtml(commit.subject)}</${subjectTag}>`;
    html += '<div class="git-commit-meta">';
    html += '<span class="git-commit-revision">';
    html += `<span class="git-commit-sha">${escapeHtml(commit.short_id)}</span>`;
    if (compact) {
      html +=
        '<span class="git-commit-revision-copy-preview" aria-hidden="true">' +
        `${copyIcon()}</span>`;
    } else {
      html +=
        '<button class="icon-btn icon-btn-reveal git-commit-revision-copy" type="button"' +
        ` data-mb-copy="text" data-mb-copy-text="${escapeHtml(commit.id)}"` +
        ' data-mb-copy-label="Copy revision" data-tip-text="Copy revision"' +
        ` aria-label="Copy revision">${copyIcon()}</button>`;
    }
    html += "</span>";
    html += `<span>${escapeHtml(commit.author?.name || "")}</span>`;
    html += `<span class="${escapeHtml(ageClass(commit.committed_at))}">`;
    html += `${escapeHtml(relativeAge(commit.committed_at))}</span>`;
    html += renderCommitChangeStats(stats, files.length, detail.files_truncated);
    html += "</div>";
    if (!compact && commit.refs?.length) {
      html += `<div class="git-commit-refs">${renderRefBadges(commit.refs)}</div>`;
    }
    html += "</div>";
    if (!compact && detail.body) {
      html += `<pre class="git-commit-body">${escapeHtml(detail.body)}</pre>`;
    }
    html += "</section>";
    return html;
  }

  /**
   * @param {MetabrowserGitCommitDetail} detail
   * @returns {string}
   */
  function renderCommitTooltip(detail) {
    return renderCommitSummary(detail, { compact: true });
  }

  /**
   * Compact relative age, matching the tree's convention.
   *
   * @param {number} epochSeconds
   * @returns {string}
   */
  function relativeAge(epochSeconds) {
    // The shared age primitive, so a commit's age reads exactly like a
    // file's: same abbreviations, same freshness tiers.
    return window.MetabrowserFormatters?.age(epochSeconds)?.label ?? "";
  }

  /**
   * The age's freshness class, so the colour convention holds here too.
   *
   * @param {number} epochSeconds
   * @returns {string}
   */
  function ageClass(epochSeconds) {
    return window.MetabrowserFormatters?.ageClass(epochSeconds) ?? "";
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
    /** @type {MetabrowserGitGraphRow[] | null} */
    let addedRows = null;
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
      addedRows = appendPage(page.commits || [], page.cursor ?? null);
    } catch {
      state.failed = true;
      addedRows = null;
    } finally {
      state.loading = false;
      // A page that only adds rows appends them; anything else — the
      // first page, a failure, a reset — repaints.
      const appended = addedRows !== null && !initial && appendRenderedRows(addedRows);
      if (appended) {
        renderTrailingState();
      } else {
        renderPanel();
      }
    }
  }

  /**
   * @param {MetabrowserGitCommit[]} commits
   * @param {string | null} cursor
   * @returns {MetabrowserGitGraphRow[]} The rows this page added.
   */
  function appendPage(commits, cursor) {
    const remaining = Math.max(0, HISTORY_MAX_ROWS - state.rows.length);
    const accepted = commits.slice(0, remaining);
    const reachesCap = state.rows.length + accepted.length >= HISTORY_MAX_ROWS;
    const omitted = commits.length > accepted.length || (reachesCap && cursor !== null);
    if (accepted.length === 0) {
      state.capped = state.capped || omitted;
      state.cursor = null;
      return [];
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
    return result.rows;
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
    const existing = detailInFlight.get(revision);
    if (existing) {
      return existing;
    }
    const request = measureAsync(
      "gitRevision:detailData",
      async () => {
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
      },
      { revision },
    );
    detailInFlight.set(revision, request);
    try {
      return await request;
    } finally {
      if (detailInFlight.get(revision) === request) {
        detailInFlight.delete(revision);
      }
    }
  }

  /**
   * Start the independent diff work for one revision.
   *
   * @param {string} revision
   * @param {AbortController | null} controller
   */
  function beginDiffPreparation(revision, controller) {
    const pluginSdk = sdk();
    const assets = pluginSdk
      ? measureAsync("gitRevision:diffAssets", () => pluginSdk.ensureKindAssets("diff"), {
          revision,
        })
      : Promise.resolve();
    const comparison = pluginSdk?.fetchPluginData
      ? measureAsync(
          "gitRevision:comparisonData",
          () =>
            pluginSdk.fetchPluginData(
              "diff",
              "comparison",
              { revision },
              { signal: controller?.signal },
            ),
          { revision },
        )
      : undefined;
    // Speculative work may be replaced before the diff view awaits it. Attach
    // a rejection handler immediately while preserving the original promise
    // for the view's existing error path.
    void comparison?.catch(() => {});
    return { assets, comparison };
  }

  /**
   * Prepare at most one revision. Pointer/focus work cannot displace an active
   * selected revision, while a new selection may replace stale work.
   *
   * @param {string} revision
   * @param {boolean} speculative
   * @returns {RevisionPreparation | null}
   */
  function prepareRevision(revision, speculative) {
    if (preparationSlot?.revision === revision) {
      if (!speculative) {
        preparationSlot.speculative = false;
      }
      return preparationSlot;
    }
    if (speculative && preparationSlot && !preparationSlot.speculative) {
      return null;
    }
    preparationSlot?.controller?.abort();
    const controller = typeof AbortController === "undefined" ? null : new AbortController();
    const diff = beginDiffPreparation(revision, controller);
    preparationSlot = {
      revision,
      detail: fetchCommitDetail(revision),
      assets: diff.assets,
      comparison: diff.comparison,
      controller,
      speculative,
    };
    return preparationSlot;
  }

  /** @param {string | null} [revision] */
  function cancelSpeculativePreparation(revision = null) {
    if (
      !preparationSlot?.speculative ||
      (revision !== null && preparationSlot.revision !== revision)
    ) {
      return;
    }
    preparationSlot.controller?.abort();
    preparationSlot = null;
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

  /**
   * Append rows to a list in one fragment.
   *
   * @param {HTMLElement} list
   * @param {MetabrowserGitGraphRow[]} rows
   */
  function appendRows(list, rows) {
    const fragment = document.createDocumentFragment();
    for (const row of rows) {
      fragment.appendChild(renderRow(row));
    }
    list.appendChild(fragment);
    synchronizeCommitRowFocus(list);
  }

  /**
   * @param {HTMLElement} list
   * @returns {HTMLElement[]}
   */
  function commitRows(list) {
    return Array.from(list.querySelectorAll(".git-graph-row")).filter(
      (element) => element instanceof HTMLElement,
    );
  }

  /**
   * Make a row collection one Tab stop while keeping every row
   * programmatically focusable for vertical navigation.
   *
   * @param {HTMLElement} list
   * @param {HTMLElement} anchor
   */
  function setCommitRowAnchor(list, anchor) {
    for (const row of commitRows(list)) {
      row.setAttribute("tabindex", row === anchor ? "0" : "-1");
    }
  }

  /** @param {HTMLElement} list */
  function synchronizeCommitRowFocus(list) {
    const rows = commitRows(list);
    const selected = rows.find((row) => row.dataset.revision === state.selectedId);
    const existing = rows.find((row) => row.getAttribute("tabindex") === "0");
    const anchor = selected ?? existing ?? rows[0];
    if (anchor) {
      setCommitRowAnchor(list, anchor);
    }
  }

  /**
   * @param {HTMLElement} row
   * @param {-1 | 1} delta
   * @returns {boolean} Whether the row belongs to a mounted commit list.
   */
  function moveCommitRowFocus(row, delta) {
    const list = row.parentElement;
    if (!(list instanceof HTMLElement)) {
      return false;
    }
    const rows = commitRows(list);
    const currentIndex = rows.indexOf(row);
    if (currentIndex < 0) {
      return false;
    }
    const nextIndex = Math.max(0, Math.min(rows.length - 1, currentIndex + delta));
    const next = rows[nextIndex];
    if (!next || next === row) {
      return true;
    }
    setCommitRowAnchor(list, next);
    next.focus({ preventScroll: true });
    next.scrollIntoView({ block: "nearest" });
    const revision = next.dataset.revision;
    if (revision) {
      void selectCommit(revision);
    }
    return true;
  }

  /**
   * @param {KeyboardEvent} event
   * @param {HTMLElement} row
   * @param {string} revision
   */
  function handleCommitRowKeydown(event, row, revision) {
    if (
      !event.defaultPrevented &&
      !event.isComposing &&
      !event.altKey &&
      !event.ctrlKey &&
      !event.metaKey &&
      !event.shiftKey
    ) {
      switch (event.key) {
        case "ArrowUp":
          if (moveCommitRowFocus(row, -1)) {
            event.preventDefault();
          }
          return;
        case "ArrowDown":
          if (moveCommitRowFocus(row, 1)) {
            event.preventDefault();
          }
          return;
      }
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      void selectCommit(revision);
    }
  }

  /**
   * Add one page's rows to the rendered list without touching the rows
   * already on screen.
   *
   * Rows are independent — each carries its own graph width — so a new
   * page cannot change how an earlier row lays out, and a full rebuild
   * would cost the whole history on every "load more". Measured in this
   * browser at ~22us per row (500 rows in 11ms), so a rebuild at two
   * thousand rows costs ~44ms to show one more page, while appending
   * that page costs only its own rows. Returns false when there is no
   * rendered list to append to, in which case the caller falls back to
   * a full render.
   *
   * @param {MetabrowserGitGraphRow[]} rows
   * @returns {boolean}
   */
  function appendRenderedRows(rows) {
    const panel = panelElement();
    const list = panel?.querySelector(".git-graph-list");
    if (!(list instanceof HTMLElement) || rows.length === 0) {
      return false;
    }
    appendRows(list, rows);
    return true;
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
    appendRows(list, state.rows);
    panel.replaceChildren(list);
    renderTrailingState();
  }

  /**
   * Put the one trailing row — loading, failed, or capped — at the end
   * of the list, replacing whatever was there.
   *
   * Separate from the row rendering because it changes on its own
   * schedule: a page append leaves every row alone and only moves this.
   */
  function renderTrailingState() {
    const list = panelElement()?.querySelector(".git-graph-list");
    if (!(list instanceof HTMLElement)) {
      return;
    }
    for (const previous of list.querySelectorAll(".git-graph-more")) {
      previous.remove();
    }
    let trailing = null;
    if (state.loading) {
      trailing = document.createElement("div");
      trailing.className = "git-graph-more";
      trailing.textContent = "Loading…";
    } else if (state.failed) {
      trailing = document.createElement("div");
      trailing.className = "git-graph-more git-graph-more-failed";
      trailing.textContent = "Could not load more history.";
    } else if (state.capped) {
      trailing = document.createElement("div");
      trailing.className = "git-graph-more";
      trailing.textContent = `Showing the newest ${HISTORY_MAX_ROWS} commits.`;
    }
    if (trailing) {
      list.appendChild(trailing);
    }
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
    element.setAttribute("tabindex", "-1");
    if (commit.id === state.selectedId) {
      element.classList.add("selected");
      element.setAttribute("aria-current", "true");
    }

    const gutter = document.createElement("div");
    gutter.className = "git-graph-gutter";
    // The gutter is exactly this row's graph: the svg carries its own
    // width, and the gutter shrink-wraps it. A shared column would
    // reserve the widest row's lanes on every row — most of a panel's
    // width spent on empty lanes — and would also make every appended
    // page able to invalidate the rows above it.
    gutter.appendChild(graphModule().renderCommitGraph(row));
    element.appendChild(gutter);

    const body = document.createElement("div");
    body.className = "git-graph-body";
    // Refs sit in their own group so they can yield space before the
    // subject does, and long before the age does: a row that cannot fit
    // everything should drop chip text, then ellipsize the subject, and
    // never push the age off the row.
    const refs = renderRefBadges(commit.refs || []);
    body.innerHTML =
      (refs ? `<span class="git-graph-refs">${refs}</span>` : "") +
      `<span class="git-graph-subject">${escapeHtml(commit.subject)}</span>` +
      `<span class="git-graph-meta">${escapeHtml(commit.author?.name || "")}` +
      `<span class="git-graph-age ${escapeHtml(ageClass(commit.committed_at))}">` +
      `${escapeHtml(relativeAge(commit.committed_at))}</span></span>`;
    element.appendChild(body);

    element.addEventListener("click", () => selectCommit(commit.id));
    element.addEventListener("keydown", (event) =>
      handleCommitRowKeydown(event, element, commit.id),
    );
    element.addEventListener("mouseenter", () => scheduleHover(element, commit.id));
    element.addEventListener("mouseleave", () => {
      if (document.activeElement !== element) {
        cancelHover(commit.id);
      }
    });
    element.addEventListener("focus", () => {
      const list = element.parentElement;
      if (list instanceof HTMLElement) {
        setCommitRowAnchor(list, element);
      }
      scheduleHover(element, commit.id);
    });
    element.addEventListener("blur", () => {
      if (!element.matches(":hover")) {
        cancelHover(commit.id);
      }
    });
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
        if (ref.is_trunk) {
          classes.push("git-ref-trunk");
        }
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
    if (hoverRevision !== revision) {
      cancelHover();
    } else if (hoverTimer !== null) {
      clearTimeout(hoverTimer);
    }
    hoverRevision = revision;
    const preparation = prepareRevision(revision, true);
    // Detail preparation begins on intent, while presentation waits for a
    // stable target so dragging down the graph does not flash one card per row.
    hoverTimer = setTimeout(async () => {
      hoverTimer = null;
      const detail = await (preparation?.detail ?? fetchCommitDetail(revision));
      if (!detail) {
        return;
      }
      // Either pointer or keyboard focus can own the same tooltip while data
      // loads. The other modality may have left without ending that ownership.
      if (!rowElement.matches(":hover") && document.activeElement !== rowElement) {
        return;
      }
      sdk()?.tooltip?.show(renderCommitTooltip(detail), rowElement);
    }, HOVER_DEBOUNCE_MS);
  }

  /** @param {string | null} [revision] */
  function cancelHover(revision = null) {
    if (revision !== null && hoverRevision !== revision) {
      return;
    }
    if (hoverTimer !== null) {
      clearTimeout(hoverTimer);
      hoverTimer = null;
    }
    sdk()?.tooltip?.hide();
    cancelSpeculativePreparation(revision);
    hoverRevision = null;
  }

  // ── Commit detail view ─────────────────────────────────────

  function clearPendingState() {
    if (pendingTimer !== null) {
      clearTimeout(pendingTimer);
      pendingTimer = null;
    }
    if (pendingPreviewClaim !== null) {
      shell()?.endPreviewNavigation(pendingPreviewClaim);
      pendingPreviewClaim = null;
    }
  }

  /** @returns {Promise<void>} */
  function afterNextPaint() {
    if (typeof requestAnimationFrame !== "function") {
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
    });
  }

  /**
   * @param {string} revision
   * @param {{fromRoute?: boolean}} [options] `fromRoute` when the URL is
   *   already this commit (restore on load), so the route is not rewritten.
   */
  async function selectCommit(revision, options = {}) {
    const bridge = shell();
    if (!bridge) {
      return;
    }
    /** @type {number | null} */
    let selectionClaim = null;
    return measureAsync(
      "gitRevision:selectToReady",
      async () => {
        clearPendingState();
        const previewClaim = bridge.claimPreview("git");
        selectionClaim = previewClaim;
        const retainedPreview = bridge.beginPreviewNavigation(previewClaim);
        pendingPreviewClaim = previewClaim;
        if (state.selectedId !== revision) {
          // Keep the prior DOM as the handoff surface, but stop its deferred
          // hydration and syntax work from competing with the selected diff.
          commitDiffHandle?.cancelPending?.();
        }
        // A commit is a selection like any other, so it owns the URL while
        // it is shown: /commit/<rev> (Browser URL Grammar). Replacing rather
        // than pushing matches the tree's skim rule — walking a history list
        // must not bury the reader's entry point.
        const routes = window.MetabrowserNavigationRoute;
        if (routes && !options.fromRoute && typeof window.history?.replaceState === "function") {
          window.history.replaceState(null, "", routes.commitHref(revision));
        }
        state.selectedId = revision;
        let selectedRow = null;
        for (const element of document.querySelectorAll(".git-graph-row")) {
          if (!(element instanceof HTMLElement)) {
            continue;
          }
          const selected = element.dataset.revision === revision;
          element.classList.toggle("selected", selected);
          if (selected) {
            element.setAttribute("aria-current", "true");
            selectedRow = element;
          } else {
            element.removeAttribute("aria-current");
          }
        }
        if (selectedRow?.parentElement instanceof HTMLElement) {
          setCommitRowAnchor(selectedRow.parentElement, selectedRow);
        }

        const preparation = prepareRevision(revision, false);
        if (!preparation) {
          clearPendingState();
          return;
        }
        if (!retainedPreview) {
          pendingTimer = setTimeout(() => {
            pendingTimer = null;
            if (state.selectedId !== revision || !bridge.isPreviewClaimCurrent(previewClaim)) {
              return;
            }
            const loading = bridge.renderPreviewHtml(
              '<div class="loading mb-delayed-loading"><div class="spinner"></div>' +
                '<span class="sr-only">Loading commit…</span></div>',
              previewClaim,
            );
            if (loading) {
              bridge.beginPreviewNavigation(previewClaim);
            }
          }, PENDING_DELAY_MS);
        }

        const detail = await preparation.detail;
        // A different commit or another preview owner won while this request
        // was in flight.
        if (state.selectedId !== revision || !bridge.isPreviewClaimCurrent(previewClaim)) {
          return;
        }
        if (!detail) {
          disposeCommitDiff();
          bridge.renderPreviewHtml(
            '<div class="preview-empty">Could not load this commit.</div>',
            previewClaim,
          );
          clearPendingState();
          return;
        }
        await renderCommitDetail(detail, previewClaim, preparation);
        if (state.selectedId === revision && bridge.isPreviewClaimCurrent(previewClaim)) {
          await afterNextPaint();
          clearPendingState();
        }
      },
      { revision },
    ).finally(() => {
      if (selectionClaim !== null && pendingPreviewClaim === selectionClaim) {
        clearPendingState();
      }
      if (preparationSlot?.revision === revision && !preparationSlot.speculative) {
        preparationSlot = null;
      }
    });
  }

  /**
   * @param {MetabrowserGitCommitDetail} detail
   * @param {number} [claim]
   * @param {RevisionPreparation | null} [preparation]
   */
  async function renderCommitDetail(detail, claim, preparation = null) {
    const bridge = shell();
    if (!bridge) {
      return;
    }
    const previewClaim = claim ?? bridge.claimPreview("git");
    const commit = detail.commit;
    const stats = detail.stats || {};
    const files = detail.files || [];

    let html = `<div class="git-commit-view" data-revision="${escapeHtml(commit.id)}">`;
    html += renderCommitSummary(detail);

    // Files outside the served root are the one thing the comparison
    // below cannot show: it renders paths this server can open, and
    // hiding the rest would misreport what the commit changed.
    const external = files.filter((file) => file.outside_root);
    if (external.length) {
      html += '<div class="git-commit-files">';
      html += '<div class="git-commit-files-summary">';
      html += `${external.length} file${external.length === 1 ? "" : "s"} outside this folder`;
      html += "</div>";
      html += external.map(renderFileRow).join("");
      html += "</div>";
    }
    if (detail.files_truncated) {
      // Say what was cut. A silently shortened list reads as a complete
      // one, which is the worse failure.
      html += `<div class="git-commit-file git-commit-file-note">This commit changes ${
        stats.files_changed || files.length
      } files; the diff below is bounded.</div>`;
    }
    // The commit's diff is rendered by the diff plugin's own view over
    // this commit's first-parent comparison — the history view composes
    // the comparison layer instead of growing a diff surface of its own
    // (arch-nav-containers.md, the general diff rendering plan).
    html += '<div class="git-commit-diff metabrowser-diff-host"></div>';
    html += "</div>";

    const stage = document.createElement("div");
    stage.className = "git-commit-stage";
    measure(
      "gitRevision:commitMarkup",
      () => {
        stage.innerHTML = html;
      },
      { revision: commit.id },
    );
    const diffPreparation = preparation ?? {
      ...beginDiffPreparation(commit.id, null),
    };
    const nextHandle = await mountCommitDiff(stage, commit.id, diffPreparation);
    if (state.selectedId !== commit.id || !bridge.isPreviewClaimCurrent(previewClaim)) {
      nextHandle?.dispose?.();
      return;
    }

    wireCommitFileNavigation(stage);
    const preview = bridge.renderPreviewNode(stage, previewClaim);
    if (!preview) {
      nextHandle?.dispose?.();
      return;
    }
    const previousHandle = commitDiffHandle;
    commitDiffHandle = nextHandle || null;
    previousHandle?.dispose?.();
  }

  /** @param {HTMLElement} root */
  function wireCommitFileNavigation(root) {
    for (const element of root.querySelectorAll(".git-commit-file[data-path]")) {
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
   * Mount the diff view for one commit, disposing any previous mount.
   *
   * @param {HTMLElement} preview
   * @param {string} revision
   * @param {{assets: Promise<void>, comparison?: Promise<unknown>}} preparation
   * @returns {Promise<{cancelPending?: () => void, dispose?: () => void} | null>}
   */
  async function mountCommitDiff(preview, revision, preparation) {
    const host = preview.querySelector(".git-commit-diff");
    const bridge = shell();
    if (!(host instanceof HTMLElement) || !bridge) {
      return null;
    }
    const pluginSdk = sdk();
    if (!pluginSdk) {
      host.remove();
      return null;
    }
    try {
      await preparation.assets;
      const view = pluginSdk.getRegisteredView("diff", "diff");
      if (!view) {
        // The diff plugin is absent: the file list above still stands on
        // its own, so say nothing rather than showing an empty frame.
        host.remove();
        return null;
      }
      return measureAsync(
        "gitRevision:diffMount",
        async () =>
          /** @type {{cancelPending?: () => void, dispose?: () => void} | null} */ (
            await view.render(host, { revision, raw: preparation.comparison })
          ),
        { revision },
      );
    } catch (_error) {
      host.textContent = "Could not load this commit's diff.";
      return null;
    }
  }

  function disposeCommitDiff() {
    commitDiffHandle?.dispose?.();
    commitDiffHandle = null;
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
      `<span class="git-file-status" data-tip-text="${escapeHtml(file.status)}">` +
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
    clearPendingState();
    preparationSlot?.controller?.abort();
    preparationSlot = null;
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
    clearPendingState();
    cancelHover();
    preparationSlot?.controller?.abort();
    preparationSlot = null;
    disposeCommitDiff();
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

    if (routeSelection) {
      // The URL named a commit: show the Git panel and that commit,
      // without rewriting the route it came from. Its own failure is
      // reported here rather than rejecting init, so a bad revision in
      // a shared link degrades to an ordinary empty panel.
      const wanted = routeSelection.revision;
      const startedAt = Date.now();
      try {
        bridge.activateNavPanel("git");
        await ensureHistory();
        await selectCommit(wanted, { fromRoute: true });
      } catch (error) {
        console.error(
          "metabrowser git panel: restoring the commit route failed",
          { revision: wanted, url: location.pathname, elapsedMs: Date.now() - startedAt },
          error,
        );
      }
    }
  }

  window.MetabrowserGitPanel = Object.freeze({
    init,
    // Exposed for tests, which drive the panel without a network.
    _internals: {
      appendPage,
      emptyState,
      ageClass,
      relativeAge,
      renderCommitSummary,
      renderCommitTooltip,
      renderCommitDetail,
      renderFileRow,
      renderPanel,
      renderRefBadges,
      selectCommit,
      wireCommitFileNavigation,
      setStateForTests: (/** @type {PanelState} */ next) => {
        state = next;
      },
      stateForTests: () => state,
    },
  });
})();
