// The Git nav panel: commit graph, ref badges, paging, hover cards, and
// the commit-detail view.
//
// Layering, and why it is split this way:
//
//   git-graph.js           pure lane assignment and SVG, ported from VS Code
//   git-history-window.js bounded decoded pages and logical row coordinates
//   git-panel.js           network, DOM ownership, selection, and lifecycle
//
// The row layout mirrors VS Code's `.history-item`: a fixed-width graph
// gutter, then ref badges, subject, author, and relative date. The
// gutter is one width for the whole panel — taken as the max over the
// rows loaded so far — so subjects line up in a column instead of
// stepping in and out as lanes open and close.
//
// Lane state at the end of one page is saved as the next page's checkpoint.
// Only the current virtual window expands those commits into graph-row models.

(() => {
  const settings = (typeof window !== "undefined" && window.METABROWSER_SETTINGS) || {};
  const LOG_LIMIT = settings.GIT_LOG_LIMIT || 250;
  const WINDOW_MAX_ROWS = settings.GIT_HISTORY_WINDOW_MAX_ROWS || 256;
  const WINDOW_OVERSCAN_ROWS = settings.GIT_HISTORY_WINDOW_OVERSCAN_ROWS || 64;
  const PAGE_CACHE_PAGES = settings.GIT_HISTORY_PAGE_CACHE_PAGES || 8;
  const SEGMENT_REBASE_PX = settings.GIT_HISTORY_SEGMENT_REBASE_PX || 8_000_000;
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
   * @property {MetabrowserGitHistoryPageCache} pageCache Bounded decoded wire pages.
   * @property {MetabrowserGitHistoryVirtualWindow} virtualWindow Logical row coordinates.
   * @property {number} rowCount Number of sequential rows loaded in this session.
   * @property {number} nextPageNumber Page expected from the next append.
   * @property {string | null} cursor Next-page cursor, null at the end.
   * @property {boolean} loading A page request is in flight.
   * @property {number | null} loadingPage Logical page currently requested.
   * @property {boolean} failed The last page request failed.
   * @property {number | null} failedPage Logical page whose request failed.
   * @property {string | null} retryCursor Cursor retained for an in-place retry.
   * @property {boolean} retryInitial Whether the failed request starts a session.
   * @property {boolean} endReached Git reported the real end of this session.
   * @property {string | null} headRevision
   * @property {string | null} headRef
   * @property {string | null} selectedId
   * @property {number | null} focusedOrdinal Logical roving-focus target.
   * @property {number | null} pendingSelectionOrdinal Keyboard target awaiting its page.
   * @property {boolean} focusSuspended The scroller temporarily owns DOM focus.
   * @property {MetabrowserGitHistoryWindowRange | null} mountedRange
   * @property {string} scopeFingerprint
   * @property {Map<number, string>} cursorByPage Replay cursor for every visited page.
   * @property {{commitCount: number, firstCommitAt: number | null} | null} summary
   */

  /** @returns {PanelState} */
  function emptyState() {
    const historyWindow = historyWindowModule();
    return {
      pageCache: historyWindow.createPageCache({ maxPages: PAGE_CACHE_PAGES }),
      virtualWindow: historyWindow.createVirtualWindow({
        rowHeight: graphModule().SWIMLANE_HEIGHT,
        maxRows: WINDOW_MAX_ROWS,
        overscanRows: WINDOW_OVERSCAN_ROWS,
        rebasePx: SEGMENT_REBASE_PX,
      }),
      rowCount: 0,
      nextPageNumber: 0,
      cursor: null,
      loading: false,
      loadingPage: null,
      failed: false,
      failedPage: null,
      retryCursor: null,
      retryInitial: false,
      endReached: false,
      headRevision: null,
      headRef: null,
      selectedId: null,
      focusedOrdinal: null,
      pendingSelectionOrdinal: null,
      focusSuspended: false,
      mountedRange: null,
      scopeFingerprint: "",
      // One retained cursor string (~175 characters) per visited page:
      // the key that lets the server seek any visited spool frame in a
      // single request. Growth is one entry per LOG_LIMIT rows walked —
      // about 1 MiB at the validated 1,454,667-row corpus — not per row.
      cursorByPage: new Map(),
      // The header tally, loaded off the render path like the file
      // tree's summary row; null renders the pending shimmer.
      summary: null,
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
  let recoveringSession = false;
  /** @type {{start: number, end: number} | null} */
  let wantedRange = null;
  /** @type {Promise<void> | null} */
  let rangeLoadPromise = null;
  let historyGeneration = 0;
  let historyAbortController = new AbortController();
  /** @type {HTMLElement | null} */
  let scrollOwner = null;

  function graphModule() {
    return window.MetabrowserGitGraph;
  }

  function historyWindowModule() {
    return window.MetabrowserGitHistoryWindow;
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
   * @returns {string}
   */
  function renderCommitChangeStats(stats) {
    const fileStatuses = [
      [stats.files_modified ?? "?", "M", "modified", "git-commit-file-status-modified"],
      [stats.files_added ?? "?", "A", "added", "git-commit-file-status-added"],
      [stats.files_deleted ?? "?", "D", "deleted", "git-commit-file-status-deleted"],
    ]
      .filter(([count]) => count !== 0)
      .map(([count, code, label, className]) => {
        const fileLabel = count === 1 ? "file" : "files";
        return (
          `<span class="git-commit-file-status ${className}"` +
          ` aria-label="${escapeHtml(String(count))} ${label} ${fileLabel}">` +
          `${escapeHtml(String(count))} ${code}</span>`
        );
      })
      .join("");
    const filesChanged = stats.files_changed ?? "?";
    const fileUnit = filesChanged === 1 ? "file" : "files";
    const additions = stats.additions ?? "?";
    const deletions = stats.deletions ?? "?";
    const lineTotal =
      typeof additions === "number" && typeof deletions === "number" ? additions + deletions : null;
    const lineUnit = lineTotal === 1 ? "line" : "lines";
    return (
      '<div class="git-commit-change-stats">' +
      '<div class="git-commit-file-statuses" aria-label="File changes">' +
      `${fileStatuses}<span class="git-commit-stat-unit">${fileUnit}</span>` +
      "</div>" +
      '<div class="git-commit-line-stats" aria-label="Line changes">' +
      `<span class="git-stat-add" aria-label="${escapeHtml(String(additions))} lines added">` +
      `+${escapeHtml(String(additions))}</span>` +
      `<span class="git-stat-del" aria-label="${escapeHtml(String(deletions))} lines deleted">` +
      `−${escapeHtml(String(deletions))}</span>` +
      `<span class="git-commit-stat-unit">${lineUnit}</span>` +
      "</div>" +
      "</div>"
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
    const compact = options.compact === true;
    const summaryClass = compact
      ? "git-commit-summary git-commit-summary-compact"
      : "git-commit-summary";
    const subjectTag = compact ? "div" : "h1";
    let html = `<section class="${summaryClass}" aria-label="Commit summary">`;
    html += '<div class="git-commit-header">';
    html += `<${subjectTag} class="git-commit-subject">${escapeHtml(commit.subject)}</${subjectTag}>`;
    html += '<div class="git-commit-meta">';
    html += '<span class="git-commit-identity">';
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
    if (commit.refs?.length) {
      html += `<span class="git-commit-refs">${renderRefBadges(commit.refs)}</span>`;
    }
    html += "</span>";
    html += `<span class="git-commit-author">${escapeHtml(commit.author?.name || "")}</span>`;
    html += `<span class="git-commit-age ${escapeHtml(ageClass(commit.committed_at))}">`;
    html += `${escapeHtml(relativeAge(commit.committed_at))}</span>`;
    html += "</div>";
    html += renderCommitChangeStats(stats);
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
   * @param {RequestInit} [options]
   * @returns {Promise<Response>}
   */
  function apiFetch(path, params, options) {
    const query = params ? `?${new URLSearchParams(params).toString()}` : "";
    return fetch(`${path}${query}`, options);
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
   * Validate and translate the server checkpoint. A session page without one
   * cannot be replayed exactly, so it invalidates the session instead of
   * drawing a plausible graph from empty lanes.
   *
   * @param {Partial<MetabrowserGitLogPage>} wirePage
   * @param {number} pageNumber
   * @returns {MetabrowserGitGraphCheckpoint}
   */
  function checkpointFromWire(wirePage, pageNumber) {
    const checkpoint = wirePage.graph_checkpoint;
    if (!checkpoint) {
      throw new Error(`Git history page ${pageNumber} omitted its graph checkpoint`);
    }
    const fingerprint = wirePage.scope_fingerprint ?? "";
    if (
      !fingerprint ||
      checkpoint.version !== 1 ||
      checkpoint.scope_fingerprint !== fingerprint ||
      checkpoint.head_revision !== state.headRevision ||
      !Number.isSafeInteger(checkpoint.color_index) ||
      !Array.isArray(checkpoint.prior_swimlanes) ||
      checkpoint.prior_swimlanes.some(
        (lane) =>
          !lane || typeof lane.id !== "string" || typeof lane.color !== "string" || !lane.color,
      )
    ) {
      throw new Error(`Git history page ${pageNumber} has an invalid graph checkpoint`);
    }
    return {
      version: 1,
      priorSwimlanes: checkpoint.prior_swimlanes.map((lane) => ({ ...lane })),
      colorIndex: checkpoint.color_index,
      headRevision: checkpoint.head_revision,
      scopeFingerprint: checkpoint.scope_fingerprint,
    };
  }

  /**
   * Store a sequential or replayed page. Only a newly discovered tail page
   * extends logical height; replay replaces one cache entry in place.
   *
   * @param {MetabrowserGitCommit[]} commits
   * @param {string | null} cursor
   * @param {MetabrowserGitLogPage} wirePage
   * @returns {void}
   */
  function appendPage(commits, cursor, wirePage) {
    if (wirePage.page === undefined) {
      throw new Error("Git history session page omitted its page number");
    }
    const pageNumber = wirePage.page;
    if (pageNumber > state.nextPageNumber) {
      throw new Error(
        `Expected Git history page at most ${state.nextPageNumber}, received ${pageNumber}`,
      );
    }
    const fingerprint = wirePage.scope_fingerprint ?? state.scopeFingerprint;
    if (state.scopeFingerprint && fingerprint !== state.scopeFingerprint) {
      throw new Error("Git history scope changed while storing a page");
    }
    const checkpoint = checkpointFromWire(wirePage, pageNumber);
    if (typeof wirePage.page_cursor === "string" && wirePage.page_cursor) {
      state.cursorByPage.set(pageNumber, wirePage.page_cursor);
    }
    const startOrdinal = pageNumber * LOG_LIMIT;
    state.pageCache.put({
      page: pageNumber,
      startOrdinal,
      commits,
      checkpoint,
      pageCursor: wirePage.page_cursor ?? `loaded-page-${pageNumber}`,
      nextCursor: cursor,
      previousCursor: wirePage.previous_cursor ?? null,
    });
    state.scopeFingerprint = fingerprint;

    if (pageNumber === state.nextPageNumber) {
      state.rowCount = startOrdinal + commits.length;
      state.virtualWindow.setRowCount(state.rowCount);
      state.nextPageNumber = pageNumber + 1;
      state.cursor = cursor;
      state.endReached = cursor === null;
    }
  }

  /**
   * @param {string | null} cursor
   * @param {number} expectedPage
   * @param {{initial?: boolean}} [options]
   * @returns {Promise<boolean>}
   */
  async function loadPage(cursor, expectedPage, options = {}) {
    if (state.loading || (!options.initial && !cursor)) {
      return false;
    }
    state.loading = true;
    state.loadingPage = expectedPage;
    state.failed = false;
    state.failedPage = null;
    renderPanel();
    const requestGeneration = historyGeneration;
    const requestState = state;
    let recoverSession = false;
    let loaded = false;
    try {
      /** @type {Record<string, string>} */
      const params = { limit: String(LOG_LIMIT) };
      if (!options.initial && cursor) {
        params.cursor = cursor;
      }
      const response = await apiFetch("/api/git/log", params, {
        signal: historyAbortController.signal,
      });
      if (requestGeneration !== historyGeneration || state !== requestState) {
        return false;
      }
      if (!response.ok) {
        recoverSession =
          !options.initial &&
          (response.status === 400 || response.status === 409 || response.status === 410);
        throw new Error(`HTTP ${response.status}`);
      }
      const page = /** @type {MetabrowserGitLogPage} */ (await response.json());
      if (!page.is_repo) {
        teardown();
        return false;
      }
      if (page.page !== undefined && page.page !== expectedPage) {
        recoverSession = !options.initial;
        throw new Error(`Expected Git history page ${expectedPage}, received ${page.page}`);
      }
      try {
        const commits = page.commits || [];
        if (page.page === undefined && commits.length === 0 && page.cursor == null) {
          state.cursor = null;
          state.endReached = true;
          state.virtualWindow.setRowCount(0);
        } else {
          appendPage(commits, page.cursor ?? null, page);
        }
      } catch (error) {
        // A malformed continuation invalidates an established walk, but an
        // invalid first page has no older session to recover. Keep that first
        // failure visible so reopening or Refresh can retry from scratch.
        recoverSession = !options.initial;
        throw error;
      }
      state.retryCursor = null;
      state.retryInitial = false;
      loaded = true;
    } catch {
      if (requestGeneration === historyGeneration && state === requestState && !recoverSession) {
        state.failed = true;
        state.failedPage = expectedPage;
        state.retryCursor = cursor;
        state.retryInitial = Boolean(options.initial);
      }
    } finally {
      if (requestGeneration === historyGeneration && state === requestState) {
        state.loading = false;
        state.loadingPage = null;
        renderPanel();
      }
    }
    if (recoverSession && requestGeneration === historyGeneration && state === requestState) {
      await recoverHistorySession();
    }
    return loaded;
  }

  /** @param {boolean} initial @returns {Promise<boolean>} */
  async function loadNextPage(initial) {
    if (!initial && (!state.cursor || state.endReached)) {
      return false;
    }
    return loadPage(initial ? null : state.cursor, state.nextPageNumber, { initial });
  }

  /**
   * Name the request that makes progress toward mounting target. A page
   * visited in this session replays in one request — the server seeks
   * its spool frame directly through the retained page cursor — so only
   * an unvisited page beyond the walk frontier steps one page at a time.
   *
   * @param {number} targetPage
   * @returns {{cursor: string, page: number} | null}
   */
  function replayStep(targetPage) {
    const direct = state.cursorByPage.get(targetPage);
    if (direct) {
      return { cursor: direct, page: targetPage };
    }
    let best = null;
    for (const pageNumber of state.pageCache.keys()) {
      const page = state.pageCache.peek(pageNumber);
      if (!page) {
        continue;
      }
      let candidate = null;
      if (pageNumber < targetPage && page.nextCursor) {
        candidate = { cursor: page.nextCursor, page: pageNumber + 1 };
      } else if (pageNumber > targetPage && page.previousCursor) {
        candidate = { cursor: page.previousCursor, page: pageNumber - 1 };
      }
      if (
        candidate &&
        (!best || Math.abs(candidate.page - targetPage) < Math.abs(best.page - targetPage))
      ) {
        best = candidate;
      }
    }
    return best;
  }

  /** @param {number} targetPage @returns {Promise<boolean>} */
  async function ensurePageLoaded(targetPage) {
    while (!state.pageCache.peek(targetPage)) {
      const step = replayStep(targetPage);
      if (!step || !(await loadPage(step.cursor, step.page))) {
        return false;
      }
    }
    state.pageCache.get(targetPage);
    return true;
  }

  /** @param {number} start @param {number} end @returns {Promise<void>} */
  async function ensureRangeLoaded(start, end) {
    if (end <= start) {
      return;
    }
    const firstPage = Math.floor(start / LOG_LIMIT);
    const lastPage = Math.floor((end - 1) / LOG_LIMIT);
    for (let page = firstPage; page <= lastPage; page += 1) {
      if (!(await ensurePageLoaded(page))) {
        return;
      }
    }
  }

  /** @param {{start: number, end: number}} range */
  function scheduleRangeLoad(range) {
    wantedRange = { start: range.start, end: range.end };
    if (rangeLoadPromise) {
      return;
    }
    const generation = historyGeneration;
    const loading = (async () => {
      while (wantedRange) {
        if (generation !== historyGeneration) {
          return;
        }
        const target = wantedRange;
        wantedRange = null;
        await ensureRangeLoaded(target.start, target.end);
        if (generation !== historyGeneration) {
          return;
        }
        renderVirtualRows(true);
        if (state.failed) {
          wantedRange = null;
        }
      }
    })();
    rangeLoadPromise = loading;
    void loading.finally(() => {
      if (rangeLoadPromise === loading) {
        rangeLoadPromise = null;
      }
    });
  }

  /**
   * Expand only cached commits intersecting a mounted logical range. Each
   * page starts from its stored graph checkpoint, so an evicted earlier page
   * is not required to draw it.
   *
   * @param {number} start
   * @param {number} end
   * @returns {Array<{ordinal: number, row: MetabrowserGitGraphRow}>}
   */
  function rowsForRange(start, end) {
    /** @type {Array<{ordinal: number, row: MetabrowserGitGraphRow}>} */
    const mounted = [];
    const pages = state.pageCache
      .keys()
      .map((pageNumber) => state.pageCache.peek(pageNumber))
      .filter((page) => page !== null)
      .sort((left, right) => left.startOrdinal - right.startOrdinal);
    for (const page of pages) {
      const pageEnd = page.startOrdinal + page.commits.length;
      if (pageEnd <= start || page.startOrdinal >= end) {
        continue;
      }
      state.pageCache.get(page.page);
      const localStart = Math.max(0, start - page.startOrdinal);
      const localEnd = Math.min(page.commits.length, end - page.startOrdinal);
      const result = graphModule().computeSwimlanes(page.commits, {
        priorSwimlanes: page.checkpoint.priorSwimlanes,
        colorIndex: page.checkpoint.colorIndex,
        headRevision: page.checkpoint.headRevision,
        refColors,
        rowStart: localStart,
        rowEnd: localEnd,
      });
      for (let index = 0; index < result.rows.length; index += 1) {
        const row = result.rows[index];
        if (row) {
          mounted.push({ ordinal: page.startOrdinal + localStart + index, row });
        }
      }
    }
    return mounted;
  }

  /**
   * Fetch one commit's detail, through a bounded cache.
   *
   * The cache is what makes hovering a row and then clicking it a single
   * request: both surfaces read the same payload.
   *
   * @param {string} revision
   * @param {AbortSignal | undefined} [signal]
   * @returns {Promise<MetabrowserGitCommitDetail | null>}
   */
  async function fetchCommitDetail(revision, signal) {
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
          const response = await apiFetch(`/api/git/commit/${revision}`, undefined, { signal });
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
    abortPreparation(preparationSlot);
    const controller = typeof AbortController === "undefined" ? null : new AbortController();
    const diff = beginDiffPreparation(revision, controller);
    preparationSlot = {
      revision,
      detail: fetchCommitDetail(revision, controller?.signal),
      assets: diff.assets,
      comparison: diff.comparison,
      controller,
      speculative,
    };
    return preparationSlot;
  }

  /** @param {RevisionPreparation | null} preparation */
  function abortPreparation(preparation) {
    if (!preparation) {
      return;
    }
    detailInFlight.delete(preparation.revision);
    preparation.controller?.abort();
  }

  /** @param {string | null} [revision] */
  function cancelSpeculativePreparation(revision = null) {
    if (
      !preparationSlot?.speculative ||
      (revision !== null && preparationSlot.revision !== revision)
    ) {
      return;
    }
    abortPreparation(preparationSlot);
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

  /** @returns {HTMLElement | null} */
  function historyScroller() {
    const element = scrollOwner ?? document.getElementById("tree-content") ?? panelElement();
    return element instanceof HTMLElement ? element : null;
  }

  /** @param {HTMLElement} scroller */
  function viewportHeight(scroller) {
    return scroller.clientHeight || graphModule().SWIMLANE_HEIGHT * 20;
  }

  /**
   * Preserve every logical row's fixed-height coordinate while one or more
   * evicted pages are being replayed. A placeholder is an honest loading or
   * retry state; it never lets a partial window read as the complete history.
   *
   * @param {HTMLElement} host
   * @param {Array<{ordinal: number, row: MetabrowserGitGraphRow}>} rows
   * @param {number} start
   * @param {number} end
   */
  function appendWindowContents(host, rows, start, end) {
    const byOrdinal = new Map(rows.map((item) => [item.ordinal, item]));
    let ordinal = start;
    while (ordinal < end) {
      const item = byOrdinal.get(ordinal);
      if (item) {
        host.appendChild(renderRow(item.row, item.ordinal));
        ordinal += 1;
        continue;
      }
      const missingStart = ordinal;
      while (ordinal < end && !byOrdinal.has(ordinal)) {
        ordinal += 1;
      }
      const placeholder = document.createElement("div");
      placeholder.className = "git-history-page-placeholder";
      placeholder.style.height = `${(ordinal - missingStart) * graphModule().SWIMLANE_HEIGHT}px`;
      placeholder.setAttribute("role", "status");
      if (state.failed && state.failedPage !== null) {
        const retry = document.createElement("button");
        retry.type = "button";
        retry.className = "btn git-history-retry";
        retry.textContent = "Retry loading history";
        retry.addEventListener("click", () => {
          void retryFailedPage();
        });
        placeholder.appendChild(retry);
      } else {
        placeholder.textContent = "Loading history…";
      }
      host.appendChild(placeholder);
    }
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
    const previous = list.querySelector(".git-graph-row[data-roving-anchor]");
    if (previous instanceof HTMLElement && previous !== anchor) {
      previous.setAttribute("tabindex", "-1");
      delete previous.dataset.rovingAnchor;
    }
    anchor.setAttribute("tabindex", "0");
    anchor.dataset.rovingAnchor = "";
  }

  /** @param {HTMLElement} list */
  function synchronizeCommitRowFocus(list) {
    const rows = commitRows(list);
    const focused = rows.find((row) => Number(row.dataset.ordinal) === state.focusedOrdinal);
    const selected = rows.find((row) => row.dataset.revision === state.selectedId);
    const existing = rows.find((row) => row.getAttribute("tabindex") === "0");
    const anchor = focused ?? selected ?? existing ?? rows[0];
    if (anchor) {
      setCommitRowAnchor(list, anchor);
    }
  }

  /** @param {Event} event */
  function handleCommitListFocus(event) {
    const row = event.target;
    if (!(row instanceof HTMLElement) || !row.classList.contains("git-graph-row")) {
      return;
    }
    const ordinal = Number(row.dataset.ordinal);
    if (Number.isSafeInteger(ordinal)) {
      state.focusedOrdinal = ordinal;
      state.focusSuspended = false;
    }
  }

  /**
   * Rebuild only the mounted logical range. Spacers account for every cached
   * row outside it, and a segment rebase rewrites the physical scroll offset
   * before any DOM is replaced.
   *
   * @param {boolean} [force]
   */
  function renderVirtualRows(force = false) {
    const list = panelElement()?.querySelector(".git-graph-list");
    const scroller = historyScroller();
    if (!(list instanceof HTMLElement) || !scroller) {
      return;
    }
    const range = state.virtualWindow.read(scroller.scrollTop || 0, viewportHeight(scroller));
    if (range.rebased && scroller.scrollTop !== range.scrollTop) {
      scroller.scrollTop = range.scrollTop;
    }
    const previous = state.mountedRange;
    if (
      !force &&
      previous?.start === range.start &&
      previous.end === range.end &&
      previous.segmentStart === range.segmentStart
    ) {
      return;
    }

    const active = document.activeElement;
    const activeOrdinal =
      active instanceof HTMLElement && active.classList.contains("git-graph-row")
        ? Number(active.dataset.ordinal)
        : null;
    if (activeOrdinal !== null && Number.isSafeInteger(activeOrdinal)) {
      state.focusedOrdinal = activeOrdinal;
    }
    const mounted = rowsForRange(range.start, range.end);
    const mountedRevisions = new Set(mounted.map((item) => item.row.commit.id));
    if (hoverRevision && !mountedRevisions.has(hoverRevision)) {
      cancelHover(hoverRevision);
    }

    const top = document.createElement("div");
    top.className = "git-history-spacer git-history-spacer-top";
    top.style.height = `${range.topSpacerPx}px`;
    top.setAttribute("aria-hidden", "true");
    const host = document.createElement("div");
    host.className = "git-history-window";
    appendWindowContents(host, mounted, range.start, range.end);
    const bottom = document.createElement("div");
    bottom.className = "git-history-spacer git-history-spacer-bottom";
    bottom.style.height = `${range.bottomSpacerPx}px`;
    bottom.setAttribute("aria-hidden", "true");
    list.replaceChildren(top, host, bottom);
    list.dataset.historyEnd = state.endReached ? "true" : "false";
    list.dataset.historyRows = String(state.rowCount);
    list.setAttribute("aria-busy", state.loading ? "true" : "false");
    state.mountedRange = range;
    synchronizeCommitRowFocus(list);
    renderTrailingState();

    const focusedRow =
      state.focusedOrdinal === null
        ? null
        : list.querySelector(`.git-graph-row[data-ordinal="${state.focusedOrdinal}"]`);
    if (focusedRow instanceof HTMLElement && (activeOrdinal !== null || state.focusSuspended)) {
      state.focusSuspended = false;
      focusedRow.focus({ preventScroll: true });
    } else if (activeOrdinal !== null) {
      scroller.setAttribute("tabindex", "-1");
      scroller.focus({ preventScroll: true });
      state.focusSuspended = true;
    }
    if (mounted.length < range.end - range.start && !state.loading && !state.failed) {
      scheduleRangeLoad(range);
    }
    if (
      focusedRow instanceof HTMLElement &&
      state.pendingSelectionOrdinal === state.focusedOrdinal
    ) {
      state.pendingSelectionOrdinal = null;
      const revision = focusedRow.dataset.revision;
      if (revision) {
        void selectCommit(revision, { rowElement: focusedRow });
      }
    }
  }

  /**
   * @param {HTMLElement} row
   * @param {-1 | 1} delta
   * @returns {boolean} Whether the row belongs to a mounted commit list.
   */
  function moveCommitRowFocus(row, delta) {
    const list = panelElement()?.querySelector(".git-graph-list");
    if (!(list instanceof HTMLElement)) {
      return false;
    }
    const currentOrdinal = Number(row.dataset.ordinal);
    if (!Number.isSafeInteger(currentOrdinal)) {
      return false;
    }
    const requestedOrdinal = currentOrdinal + delta;
    if (requestedOrdinal >= state.rowCount && delta > 0 && state.cursor && !state.loading) {
      const nextOrdinal = state.rowCount;
      state.focusedOrdinal = nextOrdinal;
      state.pendingSelectionOrdinal = nextOrdinal;
      void loadNextPage(false).then((loaded) => {
        if (!loaded || nextOrdinal >= state.rowCount) {
          state.focusedOrdinal = currentOrdinal;
          state.pendingSelectionOrdinal = null;
          return;
        }
        const scroller = historyScroller();
        if (!scroller) {
          return;
        }
        scroller.scrollTop = state.virtualWindow.rebaseToOrdinal(
          nextOrdinal,
          viewportHeight(scroller),
          "nearest",
        );
        state.mountedRange = null;
        renderVirtualRows(true);
      });
      return true;
    }
    const nextOrdinal = Math.max(0, Math.min(state.rowCount - 1, requestedOrdinal));
    if (nextOrdinal === currentOrdinal) {
      return true;
    }
    state.focusedOrdinal = nextOrdinal;
    state.pendingSelectionOrdinal = nextOrdinal;
    let next = list.querySelector(`.git-graph-row[data-ordinal="${nextOrdinal}"]`);
    if (!(next instanceof HTMLElement)) {
      const scroller = historyScroller();
      if (!scroller) {
        return false;
      }
      scroller.scrollTop = state.virtualWindow.rebaseToOrdinal(
        nextOrdinal,
        viewportHeight(scroller),
        "center",
      );
      state.mountedRange = null;
      renderVirtualRows();
      next = list.querySelector(`.git-graph-row[data-ordinal="${nextOrdinal}"]`);
    }
    if (!(next instanceof HTMLElement)) {
      return true;
    }
    next.focus({ preventScroll: true });
    next.scrollIntoView({ block: "nearest" });
    state.pendingSelectionOrdinal = null;
    const revision = next.dataset.revision;
    if (revision) {
      void selectCommit(revision, { rowElement: next });
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
          dismissHoverTooltip();
          if (moveCommitRowFocus(row, -1)) {
            event.preventDefault();
          }
          return;
        case "ArrowDown":
          dismissHoverTooltip();
          if (moveCommitRowFocus(row, 1)) {
            event.preventDefault();
          }
          return;
      }
    }
    if (event.key === "Enter" || event.key === " ") {
      dismissHoverTooltip();
      event.preventDefault();
      void selectCommit(revision, { rowElement: row });
    }
  }

  function renderPanel() {
    const panel = panelElement();
    if (!panel) {
      return;
    }

    if (state.rowCount === 0 && state.loading) {
      panel.innerHTML = '<div class="loading"><div class="spinner"></div>Loading history…</div>';
      return;
    }
    if (state.rowCount === 0 && state.failed) {
      renderRefreshState(panel, "Could not read repository history.");
      return;
    }
    if (state.rowCount === 0) {
      // A repository with no commits yet. Distinct from a failure, and
      // it should read that way.
      renderRefreshState(panel, "No commits yet.");
      return;
    }

    let list = panel.querySelector(".git-graph-list");
    if (!(list instanceof HTMLElement)) {
      const summary = document.createElement("div");
      summary.className = "git-history-summary";
      list = document.createElement("div");
      list.className = "git-graph-list";
      list.addEventListener("focusin", handleCommitListFocus);
      panel.replaceChildren(summary, list);
    }
    renderHistorySummary(panel);
    state.mountedRange = null;
    renderVirtualRows(true);
  }

  /**
   * The header tally above the graph — the Git tab's counterpart of the
   * file tree's summary row, deliberately under its own class names:
   * app.js live-patches the document's first `.tree-summary`, so this
   * row must not present itself as one. Pending until the summary
   * response lands.
   *
   * @param {HTMLElement} panel
   */
  function renderHistorySummary(panel) {
    const row = panel.querySelector(".git-history-summary");
    if (!(row instanceof HTMLElement)) {
      return;
    }
    if (!state.summary) {
      const pending = document.createElement("span");
      pending.className = "count tally-pending";
      row.replaceChildren(pending);
      return;
    }
    const count = state.summary.commitCount;
    const countSpan = document.createElement("span");
    countSpan.className = "git-history-summary-count";
    countSpan.textContent = `${count.toLocaleString()} ${count === 1 ? "commit" : "commits"}`;
    const firstCommitAt = state.summary.firstCommitAt;
    const firstAge = firstCommitAt === null ? "" : relativeAge(firstCommitAt);
    if (!firstAge || firstCommitAt === null) {
      row.replaceChildren(countSpan);
      return;
    }
    // "begun 3mo ago" — the age value carries the shared age primitive
    // (tier hue, weight, tabular numerals) exactly as commit rows do;
    // the words around it stay ordinary row text.
    const firstSpan = document.createElement("span");
    firstSpan.className = "git-history-summary-first";
    const begun = document.createElement("span");
    begun.textContent = "begun";
    const ageSpan = document.createElement("span");
    ageSpan.className = `git-history-summary-age ${ageClass(firstCommitAt)}`;
    ageSpan.textContent = firstAge;
    const ago = document.createElement("span");
    ago.textContent = "ago";
    firstSpan.replaceChildren(begun, ageSpan, ago);
    row.replaceChildren(countSpan, firstSpan);
  }

  /**
   * Load the header tally the way the file tree loads its own numbers:
   * after first paint, off the render path, replacing a pending shimmer.
   * A failed load keeps the shimmer; the next refresh retries.
   *
   * @returns {Promise<void>}
   */
  async function loadHistorySummary() {
    const requestGeneration = historyGeneration;
    const requestState = state;
    try {
      const response = await apiFetch("/api/git/summary", undefined, {
        signal: historyAbortController.signal,
      });
      if (!response.ok) {
        return;
      }
      const summary = /** @type {MetabrowserGitHistorySummary} */ (await response.json());
      if (requestGeneration !== historyGeneration || state !== requestState) {
        return;
      }
      if (!summary.is_repo || typeof summary.commit_count !== "number") {
        return;
      }
      state.summary = {
        commitCount: summary.commit_count,
        firstCommitAt: typeof summary.first_commit_at === "number" ? summary.first_commit_at : null,
      };
      const panel = panelElement();
      if (panel) {
        renderHistorySummary(panel);
      }
    } catch {
      // Leave the pending shimmer rather than blanking a number the
      // user may be reading; refreshHistory issues the retry.
    }
  }

  /** Retry the exact failed append or replay request. */
  async function retryFailedPage() {
    if (!state.failed || state.failedPage === null) {
      return;
    }
    await loadPage(state.retryCursor, state.failedPage, { initial: state.retryInitial });
  }

  /**
   * Put the trailing append state at the end of the list. Replay state is
   * rendered at its missing logical rows, where its retry action belongs.
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
    if (state.loading && state.loadingPage === state.nextPageNumber) {
      trailing = document.createElement("div");
      trailing.className = "git-graph-more";
      trailing.textContent = "Loading…";
    } else if (state.failed && state.failedPage === state.nextPageNumber) {
      trailing = document.createElement("div");
      trailing.className = "git-graph-more git-graph-more-failed";
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "btn git-history-retry";
      retry.textContent = "Retry loading history";
      retry.addEventListener("click", () => {
        void retryFailedPage();
      });
      trailing.appendChild(retry);
    }
    if (trailing) {
      list.appendChild(trailing);
    }
  }

  /**
   * @param {MetabrowserGitGraphRow} row
   * @param {number} ordinal
   * @returns {HTMLElement}
   */
  function renderRow(row, ordinal) {
    const commit = row.commit;
    const element = document.createElement("div");
    element.className = "git-graph-row";
    element.dataset.revision = commit.id;
    element.dataset.ordinal = String(ordinal);
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

    element.addEventListener("click", () => selectCommit(commit.id, { rowElement: element }));
    element.addEventListener("keydown", (event) =>
      handleCommitRowKeydown(event, element, commit.id),
    );
    element.addEventListener("mouseenter", () => scheduleHover(element, commit.id));
    element.addEventListener("mouseleave", () => cancelHover(commit.id));
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
    // Both preparation and presentation wait for a stable target. Starting
    // detail and comparison requests on every pointer crossing made scrolling
    // the history compete with the commit the reader actually selected.
    hoverTimer = setTimeout(async () => {
      hoverTimer = null;
      const preparation = prepareRevision(revision, true);
      const detail = await (preparation?.detail ?? fetchCommitDetail(revision));
      if (!detail) {
        return;
      }
      if (hoverRevision !== revision || !rowElement.matches(":hover")) {
        return;
      }
      sdk()?.tooltip?.show(renderCommitTooltip(detail), rowElement);
    }, HOVER_DEBOUNCE_MS);
  }

  function dismissHoverTooltip() {
    if (hoverTimer !== null) {
      clearTimeout(hoverTimer);
      hoverTimer = null;
    }
    sdk()?.tooltip?.hide();
    hoverRevision = null;
  }

  /** @param {string | null} [revision] */
  function cancelHover(revision = null) {
    if (revision !== null && hoverRevision !== revision) {
      return;
    }
    dismissHoverTooltip();
    cancelSpeculativePreparation(revision);
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
   * @param {{fromRoute?: boolean, rowElement?: HTMLElement}} [options]
   *   `fromRoute` when the URL is already this commit (restore on load), so
   *   the route is not rewritten. Pointer and keyboard paths pass their row
   *   so immediate feedback does not search the mounted history.
   */
  async function selectCommit(revision, options = {}) {
    const bridge = shell();
    if (!bridge) {
      return;
    }
    /** @type {number | null} */
    let selectionClaim = null;
    /** @type {HTMLElement | null} */
    let selectedRowForAnchor = null;
    return measureAsync(
      "gitRevision:selectToReady",
      async () => {
        const feedback = measure(
          "gitRevision:selectionFeedback",
          () => {
            const { previewClaim, retainedPreview } = measure(
              "gitRevision:selectionFeedback:pending",
              () => {
                clearPendingState();
                const claim = bridge.claimPreview("git");
                selectionClaim = claim;
                const retained = bridge.beginPreviewNavigation(claim);
                pendingPreviewClaim = claim;
                return { previewClaim: claim, retainedPreview: retained };
              },
              { revision },
            );
            selectionClaim = previewClaim;
            const revisionChanged = state.selectedId !== revision;
            measure(
              "gitRevision:selectionFeedback:route",
              () => {
                // A commit is a selection like any other, so it owns the URL while
                // it is shown: /commit/<rev> (Browser URL Grammar). Replacing rather
                // than pushing matches the tree's skim rule — walking a history list
                // must not bury the reader's entry point.
                const routes = window.MetabrowserNavigationRoute;
                if (
                  routes &&
                  !options.fromRoute &&
                  typeof window.history?.replaceState === "function"
                ) {
                  window.history.replaceState(null, "", routes.commitHref(revision));
                }
                state.selectedId = revision;
              },
              { revision },
            );
            measure(
              "gitRevision:selectionFeedback:rows",
              () => {
                const mountedPanel = panelElement();
                const priorRow =
                  mountedPanel instanceof HTMLElement
                    ? mountedPanel.querySelector(".git-graph-row.selected")
                    : null;
                const matchedRow =
                  options.rowElement?.dataset.revision === revision
                    ? options.rowElement
                    : mountedPanel
                      ? commitRows(mountedPanel).find((row) => row.dataset.revision === revision)
                      : null;
                const selectedRow = matchedRow instanceof HTMLElement ? matchedRow : null;
                selectedRowForAnchor = selectedRow;
                if (priorRow instanceof HTMLElement && priorRow !== selectedRow) {
                  priorRow.classList.remove("selected");
                  priorRow.removeAttribute("aria-current");
                }
                if (selectedRow) {
                  selectedRow.classList.add("selected");
                  selectedRow.setAttribute("aria-current", "true");
                  const ordinal = Number(selectedRow.dataset.ordinal);
                  if (Number.isSafeInteger(ordinal)) {
                    state.focusedOrdinal = ordinal;
                  }
                }
              },
              { revision },
            );
            return { previewClaim, retainedPreview, revisionChanged };
          },
          { revision },
        );
        const { previewClaim, retainedPreview, revisionChanged } = feedback;
        if (revisionChanged) {
          // Keep the prior DOM as the handoff surface, but stop its deferred
          // hydration and syntax work from competing with the selected diff.
          // Pointer and keyboard paths have already updated their exact two
          // rows and the claim-owned busy state before this bounded cancellation
          // work.
          commitDiffHandle?.cancelPending?.();
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
      if (
        state.selectedId === revision &&
        selectedRowForAnchor?.parentElement instanceof HTMLElement
      ) {
        measure(
          "gitRevision:rowAnchor",
          () => {
            if (selectedRowForAnchor?.parentElement instanceof HTMLElement) {
              setCommitRowAnchor(selectedRowForAnchor.parentElement, selectedRowForAnchor);
            }
          },
          { revision },
        );
      }
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
    const content = historyScroller();
    const panel = panelElement();
    if (!content || !panel || panel.style.display === "none") {
      return;
    }
    renderVirtualRows();
    if (state.loading || state.failed || !state.cursor) {
      return;
    }
    const remaining = content.scrollHeight - content.scrollTop - content.clientHeight;
    if (remaining < PAGE_AHEAD_PX) {
      void loadNextPage(false);
    }
  }

  // ── Lifecycle ──────────────────────────────────────────────

  /** @param {PanelState} current */
  function disposeHistoryState(current) {
    current.pageCache.dispose();
    current.virtualWindow.dispose();
  }

  function resetHistoryRequests() {
    historyAbortController.abort();
    historyAbortController = new AbortController();
    historyGeneration += 1;
    wantedRange = null;
    rangeLoadPromise = null;
  }

  /**
   * Rebuild an invalid or expired server session without replacing the
   * already-rendered selected commit detail. Partial rows are discarded
   * before the new walk starts, and the prior logical position is rebuilt
   * up to a bounded replay depth.
   */
  async function recoverHistorySession() {
    // Recovery itself issues page requests, and one of those can come
    // back 400/409/410 while refs are churning — without this guard that
    // response recurses through a fresh refresh-and-replay cycle with no
    // depth bound.
    if (recoveringSession) {
      return;
    }
    recoveringSession = true;
    try {
      const selectedId = state.selectedId;
      // The new walk replays its prefix one request per page, so the
      // restored position must be bounded: the cache retains at most
      // PAGE_CACHE_PAGES pages anyway, and at the measured 13-70 ms per
      // page request this cap costs well under a second. A deeper
      // pre-expiry position lands at the cap instead of issuing one
      // request per LOG_LIMIT rows of unbounded prefix.
      const restoreOrdinal = Math.min(
        Math.max(0, state.focusedOrdinal ?? state.mountedRange?.visibleStart ?? 0),
        PAGE_CACHE_PAGES * LOG_LIMIT - 1,
      );
      await refreshHistory({ preserveDetail: true, selectedId });
      while (state.rowCount <= restoreOrdinal && state.cursor && !state.failed) {
        if (!(await loadNextPage(false))) {
          break;
        }
      }
      const scroller = historyScroller();
      if (scroller && state.rowCount > 0) {
        const ordinal = Math.min(restoreOrdinal, state.rowCount - 1);
        scroller.scrollTop = state.virtualWindow.rebaseToOrdinal(
          ordinal,
          viewportHeight(scroller),
          "start",
        );
        state.focusedOrdinal = ordinal;
        state.mountedRange = null;
        renderVirtualRows(true);
      }
    } finally {
      recoveringSession = false;
    }
  }

  /**
   * @param {{preserveDetail?: boolean, selectedId?: string | null}} [options]
   * @returns {Promise<void>}
   */
  async function refreshHistory(options = {}) {
    if (state.loading || refreshing) {
      return;
    }

    refreshing = true;
    resetHistoryRequests();
    clearPendingState();
    abortPreparation(preparationSlot);
    preparationSlot = null;
    disposeHistoryState(state);
    state = emptyState();
    state.selectedId = options.selectedId ?? null;
    // The detail cache is keyed by object id, but a commit's *payload*
    // is not immutable: its refs move as branches and tags do. Keeping
    // the cache across a refresh would let the hover card and detail
    // view serve pre-refresh refs for a row the graph just redrew.
    if (!options.preserveDetail) {
      detailCache.clear();
    }
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
      state.headRef = info.head?.ref ?? null;

      // Ref colors are an input to lane assignment, so they must settle
      // before the first page is laid out.
      await loadRefColors();
      state.loading = false;
      await loadNextPage(true);
      // Fired, not awaited: the tally walks the whole graph server-side
      // and must never hold up the first page of history.
      void loadHistorySummary();
    } finally {
      refreshing = false;
    }
  }

  /** @returns {Promise<void>} */
  async function ensureHistory() {
    if (state.loading) {
      return;
    }
    if (state.rowCount === 0 && state.endReached) {
      renderPanel();
      return;
    }
    if (state.rowCount === 0) {
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
    if (
      (info.head?.revision ?? null) !== state.headRevision ||
      (info.head?.ref ?? null) !== state.headRef
    ) {
      await refreshHistory();
      return;
    }

    if (state.failed) {
      if (state.failedPage !== null) {
        await retryFailedPage();
      } else if (state.cursor) {
        await loadNextPage(false);
      }
      return;
    }
    renderVirtualRows(true);
  }

  function teardown() {
    resetHistoryRequests();
    clearPendingState();
    cancelHover();
    abortPreparation(preparationSlot);
    preparationSlot = null;
    disposeCommitDiff();
    // The focus-suspension path writes ``tabindex`` onto the shared
    // ``#tree-content`` node, which the shell owns and other panels keep
    // using after this panel is gone; renderer state written onto a
    // borrowed node is restored here, its disposal path.
    historyScroller()?.removeAttribute("tabindex");
    if (scrollOwner) {
      scrollOwner.removeEventListener("scroll", onTreeScroll);
      scrollOwner = null;
    }
    disposeHistoryState(state);
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
    if (started || !graphModule() || !historyWindowModule() || !bridge) {
      return;
    }
    started = true;

    const info = await fetchRepoInfo();
    if (!info) {
      started = false;
      return;
    }
    state.headRevision = info.head?.revision ?? null;
    state.headRef = info.head?.ref ?? null;

    bridge.registerNavPanel({
      id: "git",
      label: "Git",
      onFirstShow: null,
      onShow: () => {
        void ensureHistory();
      },
    });

    scrollOwner = document.getElementById("tree-content");
    scrollOwner?.addEventListener("scroll", onTreeScroll, { passive: true });

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
      ensurePageLoaded,
      emptyState,
      ageClass,
      relativeAge,
      renderCommitSummary,
      renderCommitTooltip,
      renderCommitDetail,
      renderFileRow,
      renderPanel,
      renderVirtualRows,
      renderRefBadges,
      rowsForRange,
      loadNextPage,
      retryFailedPage,
      selectCommit,
      wireCommitFileNavigation,
      setStateForTests: (/** @type {PanelState} */ next) => {
        if (state.pageCache !== next.pageCache) {
          disposeHistoryState(state);
        }
        state = next;
      },
      stateForTests: () => {
        const mounted = rowsForRange(0, state.rowCount);
        return {
          ...state,
          rows: mounted.map((item) => item.row),
          commits: mounted.map((item) => item.row.commit),
        };
      },
    },
  });
})();
