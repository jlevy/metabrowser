// Folder built-in plugin — directory views.
//
// The `folder` kind is assigned by the server's api_file is_dir branch
// (see manifest.toml for why there is no [[kind]] rule). Owns two views:
//
//   ("folder", "treemap") — squarified treemap of the subtree from
//       /api/rollup via mb.watchRollup: joined toggle groups for
//       metric / grouping / color plus a three-state gitignored
//       control, hover tooltip, click-to-zoom (zoom is navigation:
//       cells open through mb.openPath), keyboard support, pending
//       and truncated presentations.
//   ("folder", "readme")  — the folder's direct-child README rendered
//       through the markdown built-ins, or an explicit empty state.
//
// Geometry comes from treemap_layout.js (extra_scripts), toggle state
// persists through mb.prefs (host-only cookies, shared across per-root
// ports), and live refresh rides mb.watchRollup's debounced
// /api/events signal.

(() => {
  const mb = window.metabrowser;
  if (!mb) {
    console.error("metabrowser folder plugin: window.metabrowser missing — SDK not loaded");
    return;
  }

  /** Persisted toggle state (one preference key; absent or invalid
   * fields fall to defaults). Stored through mb.prefs so the choice
   * survives across Metabrowser instances (each served root runs on
   * its own port and therefore its own localStorage origin). */
  const PREF_KEY = "folder.treemap";
  const LEGACY_STORAGE_KEY = "metabrowser.folder.treemap";
  /** View-local encodings only. The gitignored three-state moved to
   * the shared filter vocabulary (mb.filters), where the nav bar and
   * this toolbar edit the same value. */
  const DEFAULT_STATE = {
    metric: "size",
    grouping: "folder",
    color: "type",
    depth: "all",
  };
  /** @type {Record<string, string[]>} */
  const VALID_STATE_VALUES = {
    metric: ["size", "files"],
    grouping: ["folder", "type"],
    color: ["type", "age"],
    depth: ["1", "2", "3", "all"],
  };
  const IGNORED_VALUES = ["shown", "dimmed", "hidden"];

  /** @param {unknown} raw @returns {Record<string, string>} */
  function sanitizeState(raw) {
    /** @type {Record<string, string>} */
    const state = Object.assign({}, DEFAULT_STATE);
    if (raw && typeof raw === "object") {
      for (const key of Object.keys(VALID_STATE_VALUES)) {
        const value = /** @type {Record<string, unknown>} */ (raw)[key];
        if (typeof value === "string" && VALID_STATE_VALUES[key].includes(value)) {
          state[key] = value;
        }
      }
    }
    return state;
  }
  /** Label paint thresholds: name needs LABEL_MIN, the size sub-label SUB_MIN. */
  const LABEL_MIN_W = 56;
  const LABEL_MIN_H = 16;
  const SUB_MIN_H = 30;
  /** Minimum cell width before the age chip joins the name row. */
  const AGE_MIN_W = 88;
  /** Viewport height bounds: the map fills the space between its own
   * top edge and the window bottom (minus the status line and pane
   * padding), so wrapped toolbars or long breadcrumbs never push it
   * past the pane's single scroll owner. The CSS calc() height is
   * only the pre-measurement fallback. */
  const VIEWPORT_MIN_H = 280;
  const VIEWPORT_MAX_H = 900;
  const VIEWPORT_BOTTOM_RESERVE = 64;
  /** Keep the route handoff aligned with the shared layout-motion token. */
  const ZOOM_DURATION_MS = 180;
  /** A pending camera handoff is useful only for the immediately replacing view. */
  const ZOOM_PENDING_TTL_MS = 5000;
  /** Keep a bounded ancestor scene across route changes so the same
   * world rectangles can drive both sides of a camera transition. */
  const RETAINED_SCENE_MAX_NODES = 2400;
  /**
   * @typedef {{
   *   direction: "in" | "out",
   *   sourcePath: string,
   *   targetPath: string,
   *   refineFromDepth: number,
   *   expiresAt: number
   * }} SceneTransition
   */
  /** @type {SceneTransition | null} */
  let pendingSceneTransition = null;
  /** @type {{rootPath: string, node: Record<string, any>} | null} */
  let retainedScene = null;

  /** @param {string} path @returns {string} */
  function normalizedNavigationPath(path) {
    return path === "/" ? "" : path.replace(/^\/+|\/+$/g, "");
  }

  /** @param {Record<string, any>} node @returns {number} */
  function countSceneNodes(node) {
    let count = 1;
    const stack = Array.isArray(node.children) ? node.children.slice() : [];
    while (stack.length > 0 && count <= RETAINED_SCENE_MAX_NODES) {
      const current = stack.pop();
      count += 1;
      if (current && Array.isArray(current.children)) {
        stack.push(...current.children);
      }
    }
    return count;
  }

  /**
   * Replace a matching directory subtree without disturbing ancestor
   * ordering or weights. Those ancestors define the stable world.
   *
   * @param {Record<string, any>} root
   * @param {string} targetPath
   * @param {Record<string, any>} replacement
   * @returns {boolean}
   */
  function replaceSceneSubtree(root, targetPath, replacement) {
    const children = Array.isArray(root.children) ? root.children : [];
    for (let index = 0; index < children.length; index += 1) {
      const child = children[index];
      if (normalizedNavigationPath(child.path) === targetPath) {
        children[index] = replacement;
        return true;
      }
      if (
        child.type === "dir" &&
        targetPath.startsWith(`${normalizedNavigationPath(child.path)}/`) &&
        replaceSceneSubtree(child, targetPath, replacement)
      ) {
        return true;
      }
    }
    return false;
  }

  /**
   * Keep full detail only for the active camera subtree. Sibling
   * directory nodes retain totals and outer geometry, but their
   * descendants can be reloaded if the camera returns to them.
   *
   * @param {Record<string, any>} root
   * @param {string} targetPath
   */
  function pruneSceneOutsidePath(root, targetPath) {
    if (normalizedNavigationPath(root.path) === targetPath) {
      return;
    }
    const children = Array.isArray(root.children) ? root.children : [];
    for (const child of children) {
      if (child.type !== "dir") {
        continue;
      }
      const childPath = normalizedNavigationPath(child.path);
      if (targetPath === childPath || targetPath.startsWith(`${childPath}/`)) {
        pruneSceneOutsidePath(child, targetPath);
      } else {
        child.children = null;
      }
    }
  }

  /**
   * Merge the newly fetched route subtree into a bounded retained
   * ancestor scene. Unrelated/deep-linked routes start a new world.
   *
   * @param {Record<string, any>} node
   * @param {string} requestedPath
   * @returns {Record<string, any>}
   */
  function updateRetainedScene(node, requestedPath) {
    const targetPath = normalizedNavigationPath(requestedPath);
    const incomingPath = normalizedNavigationPath(node.path);
    if (!retainedScene) {
      retainedScene = { rootPath: incomingPath, node };
      return node;
    }
    if (targetPath === retainedScene.rootPath && incomingPath === targetPath) {
      retainedScene.node = node;
    } else if (
      incomingPath === targetPath &&
      targetPath.startsWith(retainedScene.rootPath ? `${retainedScene.rootPath}/` : "") &&
      replaceSceneSubtree(retainedScene.node, targetPath, node)
    ) {
      // The target subtree now has a deeper rollup; ancestors remain
      // untouched so their geometry is identical across the handoff.
      pruneSceneOutsidePath(retainedScene.node, targetPath);
    } else {
      retainedScene = { rootPath: incomingPath, node };
    }
    if (countSceneNodes(retainedScene.node) > RETAINED_SCENE_MAX_NODES) {
      retainedScene = { rootPath: incomingPath, node };
    }
    return retainedScene.node;
  }

  /**
   * CSS matrix for a projected directory's child rectangle.
   * @param {Record<string, any>} cell
   * @param {{w: number, h: number}} viewport
   * @returns {string}
   */
  function cellFocusMatrix(cell, viewport) {
    const focus = cell.inner || cell;
    const transform = window.MetabrowserTreemapLayout.focusTransform(focus, viewport);
    return `matrix(${transform.scaleX},0,0,${transform.scaleY},${transform.translateX},${transform.translateY})`;
  }

  /** @returns {boolean} */
  function prefersReducedMotion() {
    return (
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  /** One-time migration of a legacy per-view ignored value into the
   * shared filter state (defaults never overwrite a shared choice).
   * Returns whether *raw* carried the legacy field at all, so the
   * caller can strip it from storage — without that, every remount
   * would re-apply the stale value over a later shared choice.
   * @param {unknown} raw @returns {boolean} */
  function migrateLegacyIgnored(raw) {
    if (!raw || typeof raw !== "object") {
      return false;
    }
    const record = /** @type {Record<string, unknown>} */ (raw);
    if (!("ignored" in record)) {
      return false;
    }
    const value = record.ignored;
    if (typeof value === "string" && IGNORED_VALUES.includes(value) && value !== "dimmed") {
      mb.filters.set({ ignored: /** @type {"shown" | "hidden"} */ (value) });
    }
    return true;
  }

  function loadState() {
    const stored = mb.prefs.get(PREF_KEY, null);
    if (stored !== null) {
      const state = sanitizeState(stored);
      if (migrateLegacyIgnored(stored)) {
        // One-shot: persist the sanitized state (legacy field
        // stripped) so a remount can never migrate again.
        mb.prefs.set(PREF_KEY, state);
      }
      return state;
    }
    // One-time migration from the pre-prefs localStorage key (which
    // was invisible to instances on other ports).
    try {
      const legacy = window.localStorage.getItem(LEGACY_STORAGE_KEY);
      if (legacy) {
        const parsed = JSON.parse(legacy);
        migrateLegacyIgnored(parsed);
        const state = sanitizeState(parsed);
        mb.prefs.set(PREF_KEY, state);
        window.localStorage.removeItem(LEGACY_STORAGE_KEY);
        return state;
      }
    } catch (_err) {
      // No usable legacy value; fall through to defaults.
    }
    return sanitizeState(null);
  }

  /** @param {Record<string, string>} state */
  function saveState(state) {
    mb.prefs.set(PREF_KEY, sanitizeState(state));
  }

  /** @param {number | null | undefined} mtimeSec @returns {string} */
  function ageFillClass(mtimeSec) {
    const bucket = mb.ageBucket(mtimeSec);
    return bucket ? `tm-age-${bucket}` : "tm-age-none";
  }

  /**
   * File-type class for a cell: real path for files, a synthetic name
   * carrying the dominant extension for directories and ext cells.
   * @param {Record<string, any>} cell
   * @returns {string}
   */
  function typeFillClass(cell) {
    const ext = cell.kind === "file" ? "" : cell.ext || "";
    const pathLike = cell.kind === "file" ? cell.path : `_${ext}`;
    return mb.fileTypeClass(pathLike) || "ft-text";
  }

  /**
   * Non-matching cells for the shared age/type filters dim in place.
   * The activity dimension is nav-only in v1 (rollup nodes carry no
   * active flag), so it is stripped before matching; dir cells keep
   * their context role (type filters skip them via isDir), and rest
   * cells never dim.
   * @param {Record<string, any>} cell
   * @param {Record<string, any>} filters
   * @param {number} nowSec
   */
  function cellFilterDim(cell, filters, nowSec) {
    if (!filters || cell.kind === "rest" || (!filters.ageWindow && !filters.types)) {
      return false;
    }
    const sansCurrent = Object.assign({}, filters, { current: false });
    return !mb.filters.rowMatches(
      {
        mtime: cell.mtime,
        path: cell.kind === "file" ? cell.path : `_${cell.ext || ""}`,
        isDir: cell.kind === "dir",
      },
      /** @type {any} */ (sansCurrent),
      nowSec,
    );
  }

  /**
   * @param {Record<string, any>} cell
   * @param {Record<string, string>} state
   * @param {Record<string, any>} filters
   * @param {boolean} filterDim
   */
  function cellClasses(cell, state, filters, filterDim) {
    const cls = ["tm-cell", `tm-${cell.kind}`];
    if (state.color === "age") {
      cls.push(ageFillClass(cell.mtime));
    } else {
      cls.push("tm-type-fill", typeFillClass(cell));
    }
    if (cell.gitignored && filters.ignored === "dimmed") {
      cls.push("tm-ignored");
    }
    if (filterDim) {
      cls.push("tm-filter-dim");
    }
    if (cell.state === "pending") {
      cls.push("tm-pending");
    }
    if (cell.nested) {
      cls.push("tm-nested");
    }
    return cls.join(" ");
  }

  /**
   * Value phrase for a cell under the active metric: byte sizes in
   * Bytes mode, "N files" in Files mode (a file cell keeps its real
   * byte size in either mode — "1 file" carries no information).
   * @param {Record<string, any>} cell
   * @param {Record<string, string>} state
   * @returns {string}
   */
  function cellValueText(cell, state) {
    if (cell.kind === "file") {
      return mb.formatSize(cell.bytes ?? cell.value);
    }
    if (state.metric === "files") {
      return `${cell.files ?? cell.value} files`;
    }
    return mb.formatSize(cell.kind === "ext" ? cell.bytes : cell.value);
  }

  /**
   * @param {Record<string, any>} cell
   * @param {Record<string, string>} state
   * @returns {string}
   */
  function cellAriaLabel(cell, state) {
    if (cell.kind === "rest") {
      return `${cell.files || 0} more items, ${cellValueText(cell, state)}`;
    }
    if (cell.kind === "ext") {
      return `${cell.name}: ${cell.files} files, ${mb.formatSize(cell.bytes)}`;
    }
    const what = cell.kind === "dir" ? "folder" : "file";
    const action = cell.kind === "dir" ? ", zoom in" : "";
    return `${cell.name} (${what}, ${cellValueText(cell, state)}${action})`;
  }

  /** @param {Record<string, any>} cell @returns {boolean} */
  function cellIsActionable(cell) {
    return cell.kind === "dir" || cell.kind === "file";
  }

  /**
   * One toolbar segment control.
   * @param {string} key state key
   * @param {[string, string][]} options [value, label] pairs
   * @param {string} active
   */
  function segmentHtml(key, options, active) {
    const buttons = options
      .map(
        ([value, label]) =>
          `<button type="button" data-tm-key="${key}" data-tm-value="${value}"` +
          ` aria-pressed="${value === active}">${label}</button>`,
      )
      .join("");
    /** @type {Record<string, string>} */
    const labels = {
      metric: "Area metric",
      grouping: "Grouping",
      color: "Color",
      depth: "Visible detail depth",
      ignored: "Gitignored files",
    };
    return `<span class="tm-seg" role="group" aria-label="${labels[key] || key}">${buttons}</span>`;
  }

  /** @param {Record<string, string>} state */
  /**
   * @param {Record<string, string>} state view-local encodings
   * @param {string} ignoredValue shared visibility dimension (mb.filters)
   * @param {string} path current folder path
   */
  function toolbarHtml(state, ignoredValue, path) {
    const zoomOut = path
      ? '<button type="button" class="tm-zoom-out" data-tm-zoom-out ' +
        'aria-label="Zoom out to the parent folder">↑ Zoom out</button>'
      : "";
    return (
      '<div class="tm-toolbar">' +
      zoomOut +
      segmentHtml(
        "metric",
        [
          ["size", "Bytes"],
          ["files", "Files"],
        ],
        state.metric,
      ) +
      segmentHtml(
        "grouping",
        [
          ["folder", "Folders"],
          ["type", "Types"],
        ],
        state.grouping,
      ) +
      segmentHtml(
        "color",
        [
          ["type", "Type"],
          ["age", "Age"],
        ],
        state.color,
      ) +
      segmentHtml(
        "depth",
        [
          ["1", "Depth 1"],
          ["2", "2"],
          ["3", "3"],
          ["all", "All"],
        ],
        state.depth,
      ) +
      segmentHtml(
        "ignored",
        [
          ["shown", "Ignored: shown"],
          ["dimmed", "Dimmed"],
          ["hidden", "Hidden"],
        ],
        ignoredValue,
      ) +
      "</div>"
    );
  }

  /**
   * @param {Record<string, any>} cell
   * @param {Record<string, string>} state
   * @param {number} index
   * @param {Record<string, any>} filters
   * @param {number} nowSec
   * @param {number | null} refineFromDepth
   */
  function cellHtml(cell, state, index, filters, nowSec, refineFromDepth) {
    const style =
      `left:${cell.x.toFixed(1)}px;top:${cell.y.toFixed(1)}px;` +
      `width:${Math.max(0, cell.w - 1).toFixed(1)}px;height:${Math.max(0, cell.h - 1).toFixed(1)}px` +
      (cell.nested ? `;z-index:${100 - cell.depth}` : "");
    const showLabel = cell.w >= LABEL_MIN_W && cell.h >= LABEL_MIN_H;
    // Nested parents suppress the sublabel: the reserved header strip
    // is one line tall, and a second line would overlap child cells.
    const showSub = showLabel && cell.h >= SUB_MIN_H && cell.kind !== "rest" && !cell.nested;
    const sub = cellValueText(cell, state);
    // The header's colored age chip rides next to the name (dir and
    // file cells only — ext/rest cells have no meaningful mtime).
    const ageHtml =
      showLabel && cell.w >= AGE_MIN_W && cellIsActionable(cell) ? mb.ageLabelHtml(cell.mtime) : "";
    const aria = mb.escapeHtml(cellAriaLabel(cell, state));
    const actionable = cellIsActionable(cell);
    // A nested directory cell contains its children's cells, so the
    // cell itself is a group and only its label strip is the button —
    // no button-inside-button tree, and the click target matches the
    // visible affordance.
    const titleInteractive = actionable && cell.nested;
    const titleAttrs = titleInteractive
      ? ` role="button" tabindex="-1" data-tm-index="${index}" aria-label="${aria}"`
      : "";
    const zoomCue =
      showLabel && cell.kind === "dir"
        ? '<span class="tm-cell-zoom" aria-hidden="true">+</span>'
        : "";
    const label = showLabel
      ? `<span class="tm-cell-title"${titleAttrs}><span class="tm-cell-label">${mb.escapeHtml(cell.name)}</span>${
          ageHtml ? `<span class="tm-cell-age">${ageHtml}</span>` : ""
        }${zoomCue}</span>` +
        (showSub ? `<span class="tm-cell-sub">${mb.escapeHtml(sub)}</span>` : "")
      : "";
    const outerInteractive = actionable && !titleInteractive;
    const outerAttrs = outerInteractive
      ? ` role="button" tabindex="-1" data-tm-index="${index}" aria-label="${aria}"`
      : ` role="group" aria-label="${aria}"`;
    const pendingRefinement = refineFromDepth !== null && cell.depth >= refineFromDepth;
    const classes =
      cellClasses(cell, state, filters, cellFilterDim(cell, filters, nowSec)) +
      (pendingRefinement ? " tm-lod-refine" : "");
    return (
      `<div class="${classes}"${outerAttrs}` +
      ` data-tm-cell="${index}" data-tm-kind="${cell.kind}" data-tm-path="${mb.escapeHtml(cell.path)}"` +
      ` data-tm-depth="${cell.depth}"` +
      ` style="${style}">${label}</div>`
    );
  }

  /**
   * Footer caption. In hidden-gitignored mode the map lays out from
   * the unignored_* weights, so the caption must quote those figures —
   * totals that disagree with the picture read as a bug.
   * @param {Record<string, any> | null} envelope
   * @param {Record<string, any>} filters
   * @returns {string}
   */
  function statusHtml(envelope, filters) {
    if (!envelope) {
      return "Loading rollup…";
    }
    const node = envelope.node;
    if (!node) {
      return "Indexing… the treemap fills in as the scan completes.";
    }
    const hideIgnored = filters.ignored === "hidden";
    const files = hideIgnored ? node.unignored_files : node.total_files;
    const size = hideIgnored ? node.unignored_size : node.total_size;
    const parts = [`${files} files`, mb.formatSize(size), `scan: ${envelope.index_status}`];
    if (hideIgnored) {
      parts.push("gitignored hidden");
    }
    if (node.state === "pending") {
      parts.push("this folder is still being scanned");
    }
    if (envelope.truncated) {
      parts.push(`index capped at ${envelope.max_files} files — totals are lower bounds`);
    }
    const active = [];
    if (filters.ageWindow) {
      active.push(`age ≤${filters.ageWindow}`);
    }
    if (filters.types) {
      active.push(
        `types ${filters.types.map((/** @type {string} */ t) => t.replace(/^ft-/, "")).join(",")}`,
      );
    }
    if (filters.current) {
      active.push("Current applies in the tree only");
    }
    if (active.length > 0) {
      parts.push(`filters: ${active.join(" · ")}`);
    }
    return parts.join(" · ");
  }

  /**
   * @param {Record<string, any>} cell
   * @param {Record<string, string>} state
   * @returns {string}
   */
  function tooltipHtml(cell, state) {
    const rows = [];
    if (cell.kind === "ext") {
      rows.push(`<strong>${mb.escapeHtml(cell.name)}</strong>`);
      rows.push(`${cell.files} files · ${mb.formatSize(cell.bytes)}`);
    } else if (cell.kind === "rest") {
      rows.push(`<strong>${cell.files || 0} more items</strong>`);
      rows.push(cellValueText(cell, state));
    } else {
      rows.push(`<strong>${mb.escapeHtml(cell.path || cell.name)}</strong>`);
      rows.push(
        state.metric === "files" && cell.kind === "dir"
          ? `${cell.value} files`
          : mb.formatSize(cell.value),
      );
      if (typeof cell.mtime === "number" && cell.mtime > 0) {
        rows.push(`modified ${mb.formatTimestamp(cell.mtime)}`);
      }
      if (cell.gitignored) {
        rows.push("gitignored");
      }
      if (cell.state === "pending") {
        rows.push("still scanning");
      }
      if (cell.kind === "dir") {
        rows.push("Click to zoom in");
      }
    }
    return rows.join("<br>");
  }

  /** @param {string} path @returns {string} */
  function parentPath(path) {
    const idx = path.lastIndexOf("/");
    return idx === -1 ? "" : path.slice(0, idx);
  }

  /**
   * ("folder", "treemap") renderer. All mutable state lives in this
   * closure; dispose tears down the watch, observer, and tooltip.
   * @param {HTMLElement} container
   * @param {Record<string, any>} ctx
   */
  function renderTreemap(container, ctx) {
    const state = loadState();
    let filters = mb.filters.get();
    /** @type {Record<string, any> | null} */
    let envelope = null;
    /** @type {Record<string, any> | null} */
    let sceneNode = null;
    /** @type {Record<string, any>[]} */
    let cells = [];
    let disposed = false;
    let zooming = false;
    let entrancePlayed = false;
    /** @type {number | null} */
    let exitTimer = null;
    /** @type {number | null} */
    let entranceTimer = null;
    /** @type {SceneTransition | null} */
    let ownedPendingTransition = null;
    /** @type {number[]} */
    let actionableIndexes = [];
    let focusPos = 0;

    container.innerHTML =
      toolbarHtml(state, filters.ignored, ctx.path) +
      '<div class="tm-viewport" role="application" ' +
      'aria-label="Folder treemap. Select a folder to zoom in.">' +
      '<div class="tm-scene"></div></div>' +
      `<div class="tm-status">${statusHtml(null, filters)}</div>`;
    const viewport = /** @type {HTMLElement} */ (container.querySelector(".tm-viewport"));
    const scene = /** @type {HTMLElement} */ (viewport.querySelector(".tm-scene"));
    const status = /** @type {HTMLElement} */ (container.querySelector(".tm-status"));

    /** Measure the height actually available below the viewport's top
     * edge and pin it as an inline style (clamped to the bounds
     * above). Skips silently where layout metrics are unavailable
     * (the vm test harness without a shim, a detached container) —
     * the CSS fallback height governs there. */
    function sizeViewport() {
      if (disposed || !viewport || !viewport.style) {
        return;
      }
      const winH = window.innerHeight;
      const rect = viewport.getBoundingClientRect();
      if (!Number.isFinite(winH) || winH <= 0 || !Number.isFinite(rect.top)) {
        return;
      }
      // Reserve what the caption actually needs (it can wrap to two
      // lines), not a blind constant: measured status height + its
      // top margin + the pane's bottom padding, floored at the
      // constant for harnesses that cannot measure.
      const statusH = status ? Number(status.offsetHeight) : Number.NaN;
      const reserve = Number.isFinite(statusH)
        ? Math.max(statusH + 8 + 24, VIEWPORT_BOTTOM_RESERVE)
        : VIEWPORT_BOTTOM_RESERVE;
      const avail = winH - rect.top - reserve;
      const next = `${Math.round(Math.max(VIEWPORT_MIN_H, Math.min(VIEWPORT_MAX_H, avail)))}px`;
      if (viewport.style.height !== next) {
        viewport.style.height = next;
      }
    }

    /**
     * Complete a route handoff against the same recursive world. A
     * zoom-out mounts the parent scene already focused on the prior
     * child and lets the compositor expand to identity. A zoom-in is
     * already at its exact destination after the outgoing transform,
     * so only newly eligible LOD cells refine into place.
     */
    function playPendingEntrance() {
      if (entrancePlayed || prefersReducedMotion()) {
        return;
      }
      const transition = pendingSceneTransition;
      if (!transition) {
        return;
      }
      if (transition.expiresAt <= Date.now()) {
        pendingSceneTransition = null;
        return;
      }
      if (normalizedNavigationPath(transition.targetPath) !== normalizedNavigationPath(ctx.path)) {
        return;
      }
      pendingSceneTransition = null;
      entrancePlayed = true;
      if (transition.direction === "out") {
        const sourceCell = cells.find(
          (cell) =>
            cell.kind === "dir" &&
            normalizedNavigationPath(cell.path) === normalizedNavigationPath(transition.sourcePath),
        );
        const rect = viewport.getBoundingClientRect();
        if (sourceCell && scene.style && typeof scene.style.setProperty === "function") {
          scene.style.setProperty(
            "--tm-scene-start-transform",
            cellFocusMatrix(sourceCell, { w: rect.width, h: rect.height }),
          );
          scene.classList.add("tm-scene-enter-out");
        }
      } else {
        // Newly materialized cells already carry tm-lod-refine. The
        // stable cells do not fade, preserving spatial continuity.
      }
      entranceTimer = window.setTimeout(() => {
        entranceTimer = null;
        scene.classList.remove("tm-scene-enter-out");
        if (scene.style && typeof scene.style.removeProperty === "function") {
          scene.style.removeProperty("--tm-scene-start-transform");
        }
      }, ZOOM_DURATION_MS);
    }

    function relayout() {
      if (disposed || !viewport) {
        return;
      }
      // Caption first (its height feeds the reserve), then size, then
      // measure — so a wrapping caption shrinks the map instead of
      // pushing the pane into scroll.
      status.textContent = statusHtml(envelope, filters);
      sizeViewport();
      const rect = viewport.getBoundingClientRect();
      const node = state.grouping === "folder" ? sceneNode : envelope ? envelope.node : null;
      if (!node || rect.width < 10 || rect.height < 10) {
        scene.innerHTML = envelope
          ? ""
          : '<div class="tm-loading"><div class="spinner"></div></div>';
        return;
      }
      const visibleDepth =
        state.depth === "all"
          ? window.MetabrowserTreemapLayout.LAYOUT_DEFAULTS.nestDepth
          : Number(state.depth);
      cells = window.MetabrowserTreemapLayout.layoutTree(
        node,
        { w: rect.width, h: rect.height },
        {
          metric: state.metric,
          grouping: state.grouping,
          ignored: filters.ignored,
          extTallies: envelope ? envelope.ext_tallies : [],
          focusPath: state.grouping === "folder" ? ctx.path : node.path,
          nestDepth: visibleDepth,
        },
      );
      const nowSec = Date.now() / 1000;
      const refineFromDepth =
        pendingSceneTransition &&
        pendingSceneTransition.direction === "in" &&
        normalizedNavigationPath(pendingSceneTransition.targetPath) ===
          normalizedNavigationPath(ctx.path)
          ? pendingSceneTransition.refineFromDepth
          : null;
      const html = cells
        .map((cell, i) => cellHtml(cell, state, i, filters, nowSec, refineFromDepth))
        .join("");
      scene.innerHTML =
        html || '<div class="preview-empty">Empty folder — nothing to draw yet</div>';
      playPendingEntrance();
      // Roving tabindex over actionable cells only (dir/file); ext and
      // rest cells are descriptive groups outside the focus order.
      actionableIndexes = [];
      cells.forEach((cell, i) => {
        if (cell.kind === "dir" || cell.kind === "file") {
          actionableIndexes.push(i);
        }
      });
      focusPos = 0;
      const first = /** @type {HTMLElement | null} */ (
        viewport.querySelector(`[data-tm-index="${actionableIndexes[0] ?? -1}"]`)
      );
      if (first) {
        first.setAttribute("tabindex", "0");
      }
    }

    /**
     * Play the old-root half of a spatial zoom, then hand the
     * destination to the normal open-path pipeline.
     * @param {"in" | "out"} direction
     * @param {string} targetPath
     * @param {Record<string, any> | null} originCell
     */
    function startZoom(direction, targetPath, originCell) {
      if (disposed || zooming) {
        return;
      }
      mb.tooltip.hide();
      if (prefersReducedMotion()) {
        pendingSceneTransition = null;
        mb.openPath(targetPath);
        return;
      }
      zooming = true;
      const transition = {
        direction,
        sourcePath: ctx.path,
        targetPath,
        refineFromDepth:
          direction === "in" && originCell
            ? Math.max(
                0,
                (state.depth === "all"
                  ? window.MetabrowserTreemapLayout.LAYOUT_DEFAULTS.nestDepth
                  : Number(state.depth)) -
                  Number(originCell.depth || 0) -
                  1,
              )
            : 0,
        expiresAt: Date.now() + ZOOM_PENDING_TTL_MS,
      };
      pendingSceneTransition = transition;
      ownedPendingTransition = transition;
      if (direction === "out") {
        ownedPendingTransition = null;
        mb.openPath(targetPath);
        return;
      }
      const rect = viewport.getBoundingClientRect();
      if (originCell && scene.style && typeof scene.style.setProperty === "function") {
        scene.style.setProperty(
          "--tm-scene-end-transform",
          cellFocusMatrix(originCell, { w: rect.width, h: rect.height }),
        );
      }
      scene.classList.add("tm-scene-exit-in");
      exitTimer = window.setTimeout(() => {
        exitTimer = null;
        ownedPendingTransition = null;
        mb.openPath(targetPath);
      }, ZOOM_DURATION_MS);
    }

    /**
     * Cell for hover/tooltip lookup: every cell carries data-tm-cell.
     * @param {Element | null} el
     * @returns {Record<string, any> | null}
     */
    function cellForElement(el) {
      if (!el) {
        return null;
      }
      const host = /** @type {HTMLElement | null} */ (el.closest("[data-tm-cell]"));
      if (!host) {
        return null;
      }
      const idx = Number(host.dataset.tmCell);
      return Number.isInteger(idx) && idx >= 0 && idx < cells.length ? cells[idx] : null;
    }

    /**
     * Cell for activation: only actionable elements carry data-tm-index
     * (a nested directory's label strip, or the whole cell otherwise).
     * @param {Element | null} el
     * @returns {Record<string, any> | null}
     */
    function actionableCellForElement(el) {
      if (!el) {
        return null;
      }
      const host = /** @type {HTMLElement | null} */ (el.closest("[data-tm-index]"));
      if (!host) {
        return null;
      }
      const idx = Number(host.dataset.tmIndex);
      return Number.isInteger(idx) && idx >= 0 && idx < cells.length ? cells[idx] : null;
    }

    /** @param {Record<string, any>} cell */
    function activateCell(cell) {
      if (cell.kind === "dir" && cell.path !== ctx.path) {
        startZoom("in", cell.path, cell);
      } else if (cell.kind === "file") {
        mb.openPath(cell.path);
      }
      // rest / ext cells have no navigation target.
    }

    /** @param {number} nextPos position within actionableIndexes */
    function moveFocus(nextPos) {
      if (nextPos < 0 || nextPos >= actionableIndexes.length) {
        return;
      }
      const prev = viewport.querySelector(`[data-tm-index="${actionableIndexes[focusPos]}"]`);
      if (prev) {
        prev.setAttribute("tabindex", "-1");
      }
      focusPos = nextPos;
      const next = /** @type {HTMLElement | null} */ (
        viewport.querySelector(`[data-tm-index="${actionableIndexes[focusPos]}"]`)
      );
      if (next) {
        next.setAttribute("tabindex", "0");
        next.focus();
      }
    }

    viewport.addEventListener("click", (e) => {
      const cell = actionableCellForElement(/** @type {Element} */ (e.target));
      if (cell) {
        activateCell(cell);
      }
    });
    viewport.addEventListener("mouseover", (e) => {
      const cell = cellForElement(/** @type {Element} */ (e.target));
      if (cell) {
        mb.tooltip.show(tooltipHtml(cell, state), e);
      }
    });
    viewport.addEventListener("mousemove", (e) => {
      mb.tooltip.move(e);
    });
    viewport.addEventListener("mouseout", () => {
      mb.tooltip.hide();
    });
    viewport.addEventListener("keydown", (e) => {
      const key = e.key;
      if (key === "Enter" || key === " ") {
        const cell = cells[actionableIndexes[focusPos]];
        if (cell) {
          activateCell(cell);
        }
        e.preventDefault();
      } else if (key === "ArrowRight" || key === "ArrowDown") {
        moveFocus(focusPos + 1);
        e.preventDefault();
      } else if (key === "ArrowLeft" || key === "ArrowUp") {
        moveFocus(focusPos - 1);
        e.preventDefault();
      } else if (key === "Backspace") {
        // At the served root there is no parent to open — let the
        // browser keep its own Backspace behavior (e.g. history back).
        if (ctx.path) {
          startZoom("out", parentPath(ctx.path) || "/", null);
          e.preventDefault();
        }
      }
    });

    container.addEventListener("click", (e) => {
      const zoomOut = /** @type {HTMLElement | null} */ (
        /** @type {Element} */ (e.target).closest("[data-tm-zoom-out]")
      );
      if (zoomOut) {
        startZoom("out", parentPath(ctx.path) || "/", null);
        return;
      }
      const btn = /** @type {HTMLElement | null} */ (
        /** @type {Element} */ (e.target).closest("[data-tm-key]")
      );
      if (!btn) {
        return;
      }
      const key = btn.dataset.tmKey || "";
      const value = btn.dataset.tmValue || "";
      if (!key || !value) {
        return;
      }
      if (key === "ignored") {
        // Shared dimension: write through mb.filters; the subscription
        // below re-syncs the toolbar and relayouts (nav stays in step).
        if (filters.ignored !== value) {
          mb.filters.set({ ignored: /** @type {"shown" | "dimmed" | "hidden"} */ (value) });
        }
        return;
      }
      if (state[key] === value) {
        return;
      }
      state[key] = value;
      saveState(state);
      const group = btn.parentElement;
      if (group) {
        group.querySelectorAll("button").forEach((b) => {
          b.setAttribute("aria-pressed", String(b === btn));
        });
      }
      relayout();
    });

    /** Reflect the shared visibility value on the toolbar's ignored
     * segment (stub containers without querySelectorAll skip). */
    function syncIgnoredToolbar() {
      if (typeof container.querySelectorAll !== "function") {
        return;
      }
      container.querySelectorAll('[data-tm-key="ignored"]').forEach((btn) => {
        btn.setAttribute(
          "aria-pressed",
          String(/** @type {HTMLElement} */ (btn).dataset.tmValue === filters.ignored),
        );
      });
    }
    const unsubscribeFilters = mb.filters.subscribe((next) => {
      filters = next;
      syncIgnoredToolbar();
      relayout();
    });

    sizeViewport();
    /** Tab switches hide inactive view containers (display:none)
     * without disposing them, so the watch must not spend fetches on
     * a map nobody can see. The stub-tolerant checks treat missing
     * properties (vm harness) as visible. */
    function isVisible() {
      return viewport.isConnected !== false && viewport.offsetParent !== null;
    }
    const watch = mb.watchRollup(
      ctx.path,
      {
        active: isVisible,
        onError: (/** @type {unknown} */ err) => {
          if (disposed || envelope) {
            return; // A stale map beats an error card; retry is armed.
          }
          scene.innerHTML =
            '<div class="preview-empty">Rollup failed — retrying on the next filesystem change</div>';
          status.textContent = `Rollup failed: ${err instanceof Error ? err.message : String(err)}`;
        },
      },
      (env) => {
        envelope = env;
        sceneNode = env.node ? updateRetainedScene(env.node, ctx.path) : null;
        relayout();
      },
    );
    // When the tab shows again after changes were skipped, catch up.
    const intersectionObserver =
      typeof IntersectionObserver !== "undefined"
        ? new IntersectionObserver((entries) => {
            for (const entry of entries) {
              if (entry.isIntersecting && watch.stale()) {
                watch.refresh();
                break;
              }
            }
          })
        : null;
    if (intersectionObserver) {
      intersectionObserver.observe(viewport);
    }
    const resizeObserver =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(() => {
            // The container can resize without a window resize (pane
            // drag wraps the toolbar or breadcrumb above, moving this
            // viewport's top edge) — re-measure before laying out.
            // sizeViewport only writes when the value changes, so the
            // observer settles after one extra tick.
            sizeViewport();
            relayout();
          })
        : null;
    if (resizeObserver) {
      resizeObserver.observe(viewport);
    }
    // Window resize re-measures the available height; the observer
    // then relayouts off the height change (directly where there is
    // no ResizeObserver, e.g. the vm harness).
    function onWindowResize() {
      sizeViewport();
      if (!resizeObserver) {
        relayout();
      }
    }
    window.addEventListener("resize", onWindowResize);

    activeTreemapDispose = () => {
      disposed = true;
      if (exitTimer !== null) {
        window.clearTimeout(exitTimer);
        exitTimer = null;
        if (pendingSceneTransition === ownedPendingTransition) {
          pendingSceneTransition = null;
        }
      }
      if (entranceTimer !== null) {
        window.clearTimeout(entranceTimer);
        entranceTimer = null;
      }
      watch.dispose();
      unsubscribeFilters();
      window.removeEventListener("resize", onWindowResize);
      if (intersectionObserver) {
        intersectionObserver.disconnect();
      }
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      mb.tooltip.hide();
    };
  }

  /** @type {(() => void) | null} */
  let activeTreemapDispose = null;

  function disposeTreemap() {
    if (activeTreemapDispose) {
      try {
        activeTreemapDispose();
      } catch (_err) {
        // Disposal is best-effort; the pane is already being replaced.
      }
      activeTreemapDispose = null;
    }
  }

  /**
   * ("folder", "readme") renderer: the folder's direct-child README
   * through the markdown built-ins, or an explicit empty state.
   * @param {HTMLElement} container
   * @param {Record<string, any>} ctx
   */
  function renderReadme(container, ctx) {
    const readmePath = ctx.raw ? ctx.raw.readme_path : "";
    if (!readmePath) {
      container.innerHTML = '<div class="preview-empty">No README in this folder</div>';
      return;
    }
    const markdown = mb.builtins ? mb.builtins.markdown : null;
    if (!markdown) {
      container.innerHTML = '<div class="preview-empty">Markdown renderer unavailable</div>';
      return;
    }
    const readmeCtx = Object.assign({}, ctx, { path: readmePath, kind: "markdown" });
    return markdown.renderRendered(container, readmeCtx);
  }

  function disposeReadme() {
    const markdown = mb.builtins ? mb.builtins.markdown : null;
    if (markdown && typeof markdown.disposeToc === "function") {
      markdown.disposeToc();
    }
  }

  mb.registerView("folder", "treemap", { render: renderTreemap, dispose: disposeTreemap });
  mb.registerView("folder", "readme", { render: renderReadme, dispose: disposeReadme });
})();
