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
  const DEFAULT_STATE = { metric: "size", grouping: "folder", color: "type", ignored: "dimmed" };
  /** @type {Record<string, string[]>} */
  const VALID_STATE_VALUES = {
    metric: ["size", "files"],
    grouping: ["folder", "type"],
    color: ["type", "age"],
    ignored: ["shown", "dimmed", "hidden"],
  };

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

  function loadState() {
    const stored = mb.prefs.get(PREF_KEY, null);
    if (stored !== null) {
      return sanitizeState(stored);
    }
    // One-time migration from the pre-prefs localStorage key (which
    // was invisible to instances on other ports).
    try {
      const legacy = window.localStorage.getItem(LEGACY_STORAGE_KEY);
      if (legacy) {
        const state = sanitizeState(JSON.parse(legacy));
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

  /** @param {Record<string, any>} cell @param {Record<string, string>} state */
  function cellClasses(cell, state) {
    const cls = ["tm-cell", `tm-${cell.kind}`];
    if (state.color === "age") {
      cls.push(ageFillClass(cell.mtime));
    } else {
      cls.push("tm-type-fill", typeFillClass(cell));
    }
    if (cell.gitignored && state.ignored === "dimmed") {
      cls.push("tm-ignored");
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
    return `${cell.name} (${what}, ${cellValueText(cell, state)})`;
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
    return `<span class="tm-seg" role="group">${buttons}</span>`;
  }

  /** @param {Record<string, string>} state */
  function toolbarHtml(state) {
    return (
      '<div class="tm-toolbar">' +
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
        "ignored",
        [
          ["shown", "Ignored: shown"],
          ["dimmed", "Dimmed"],
          ["hidden", "Hidden"],
        ],
        state.ignored,
      ) +
      "</div>"
    );
  }

  /**
   * @param {Record<string, any>} cell
   * @param {Record<string, string>} state
   * @param {number} index
   */
  function cellHtml(cell, state, index) {
    const style =
      `left:${cell.x.toFixed(1)}px;top:${cell.y.toFixed(1)}px;` +
      `width:${Math.max(0, cell.w - 1).toFixed(1)}px;height:${Math.max(0, cell.h - 1).toFixed(1)}px`;
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
    const label = showLabel
      ? `<span class="tm-cell-title"${titleAttrs}><span class="tm-cell-label">${mb.escapeHtml(cell.name)}</span>${
          ageHtml ? `<span class="tm-cell-age">${ageHtml}</span>` : ""
        }</span>${showSub ? `<span class="tm-cell-sub">${mb.escapeHtml(sub)}</span>` : ""}`
      : "";
    const outerInteractive = actionable && !titleInteractive;
    const outerAttrs = outerInteractive
      ? ` role="button" tabindex="-1" data-tm-index="${index}" aria-label="${aria}"`
      : ` role="group" aria-label="${aria}"`;
    return (
      `<div class="${cellClasses(cell, state)}"${outerAttrs}` +
      ` data-tm-cell="${index}" data-tm-kind="${cell.kind}" data-tm-path="${mb.escapeHtml(cell.path)}"` +
      ` style="${style}">${label}</div>`
    );
  }

  /** @param {Record<string, any> | null} envelope @returns {string} */
  function statusHtml(envelope) {
    if (!envelope) {
      return "Loading rollup…";
    }
    const node = envelope.node;
    if (!node) {
      return "Indexing… the treemap fills in as the scan completes.";
    }
    const parts = [
      `${node.total_files} files`,
      mb.formatSize(node.total_size),
      `scan: ${envelope.index_status}`,
    ];
    if (node.state === "pending") {
      parts.push("this folder is still being scanned");
    }
    if (envelope.truncated) {
      parts.push(`index capped at ${envelope.max_files} files — totals are lower bounds`);
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
      rows.push(mb.formatSize(cell.value));
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
    /** @type {Record<string, any> | null} */
    let envelope = null;
    /** @type {Record<string, any>[]} */
    let cells = [];
    let disposed = false;
    /** @type {number[]} */
    let actionableIndexes = [];
    let focusPos = 0;

    container.innerHTML =
      toolbarHtml(state) +
      '<div class="tm-viewport" role="application" aria-label="Folder treemap"></div>' +
      `<div class="tm-status">${statusHtml(null)}</div>`;
    const viewport = /** @type {HTMLElement} */ (container.querySelector(".tm-viewport"));
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
      const avail = winH - rect.top - VIEWPORT_BOTTOM_RESERVE;
      const next = `${Math.round(Math.max(VIEWPORT_MIN_H, Math.min(VIEWPORT_MAX_H, avail)))}px`;
      if (viewport.style.height !== next) {
        viewport.style.height = next;
      }
    }

    function relayout() {
      if (disposed || !viewport) {
        return;
      }
      const rect = viewport.getBoundingClientRect();
      const node = envelope ? envelope.node : null;
      status.textContent = statusHtml(envelope);
      if (!node || rect.width < 10 || rect.height < 10) {
        viewport.innerHTML = envelope
          ? ""
          : '<div class="tm-loading"><div class="spinner"></div></div>';
        return;
      }
      cells = window.MetabrowserTreemapLayout.layoutTree(
        node,
        { w: rect.width, h: rect.height },
        {
          metric: state.metric,
          grouping: state.grouping,
          ignored: state.ignored,
          extTallies: envelope ? envelope.ext_tallies : [],
        },
      );
      const html = cells.map((cell, i) => cellHtml(cell, state, i)).join("");
      viewport.innerHTML =
        html || '<div class="preview-empty">Empty folder — nothing to draw yet</div>';
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
        mb.openPath(cell.path);
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
        if (ctx.path) {
          mb.openPath(parentPath(ctx.path) || "/");
        }
        e.preventDefault();
      }
    });

    container.addEventListener("click", (e) => {
      const btn = /** @type {HTMLElement | null} */ (
        /** @type {Element} */ (e.target).closest("[data-tm-key]")
      );
      if (!btn) {
        return;
      }
      const key = btn.dataset.tmKey || "";
      const value = btn.dataset.tmValue || "";
      if (!key || !value || state[key] === value) {
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

    sizeViewport();
    const watch = mb.watchRollup(ctx.path, {}, (env) => {
      envelope = env;
      relayout();
    });
    const resizeObserver =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(() => {
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
      watch.dispose();
      window.removeEventListener("resize", onWindowResize);
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
