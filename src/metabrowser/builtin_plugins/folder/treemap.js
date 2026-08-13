// Folder Treemap view controller.
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
//
// Geometry comes from treemap_layout.js, toggle state
// persists through mb.prefs (host-only cookies, shared across per-root
// ports), and live refresh rides mb.watchRollup's debounced
// /api/events signal.

import { layoutTree } from "./treemap_layout.js";
import { parentPath, sanitizeTreemapState } from "./treemap_model.js";

/** @typedef {{sync: (keys: Array<string>) => void, release: () => void, classFor: (key: string) => string}} TreemapPalette */
/** @typedef {{acquire: (path: string) => TreemapPalette}} TreemapPalettePool */

/** @param {MetabrowserPublicSdk} mb @param {TreemapPalettePool} palettePool */
export function registerTreemap(mb, palettePool) {
  /** Persisted toggle state (one preference key; absent or invalid
   * fields fall to defaults). Stored through mb.prefs so the choice
   * survives across Metabrowser instances (each served root runs on
   * its own port and therefore its own localStorage origin). */
  const PREF_KEY = "folder.treemap";
  const LEGACY_STORAGE_KEY = "metabrowser.folder.treemap";
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
      return sanitizeTreemapState(stored);
    }
    // One-time migration from the pre-prefs localStorage key (which
    // was invisible to instances on other ports).
    try {
      const legacy = window.localStorage.getItem(LEGACY_STORAGE_KEY);
      if (legacy) {
        const state = sanitizeTreemapState(JSON.parse(legacy));
        mb.prefs.set(PREF_KEY, state);
        window.localStorage.removeItem(LEGACY_STORAGE_KEY);
        return state;
      }
    } catch (_err) {
      // No usable legacy value; fall through to defaults.
    }
    return sanitizeTreemapState(null);
  }

  /** @param {Record<string, string>} state */
  function saveState(state) {
    mb.prefs.set(PREF_KEY, sanitizeTreemapState(state));
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
   * @param {{classFor: (key: string) => string}} palette
   * @returns {string}
   */
  function typeFillClass(cell, palette) {
    const key = cell.kind === "rest" ? "" : cell.ext || "(none)";
    return palette.classFor(key);
  }

  /** @param {Record<string, any>} cell @param {Record<string, string>} state @param {{classFor: (key: string) => string}} palette */
  function cellClasses(cell, state, palette) {
    const cls = ["tm-cell", `tm-${cell.kind}`];
    if (state.color === "age") {
      cls.push(ageFillClass(cell.mtime));
    } else {
      cls.push("tm-type-fill", typeFillClass(cell, palette));
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
   * @param {TreemapPalette} palette
   */
  function cellHtml(cell, state, index, palette) {
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
      `<div class="${cellClasses(cell, state, palette)}"${outerAttrs}` +
      ` data-tm-cell="${index}" data-tm-kind="${cell.kind}" data-tm-path="${mb.escapeHtml(cell.path)}"` +
      ` style="${style}">${label}</div>`
    );
  }

  /**
   * Footer caption. In hidden-gitignored mode the map lays out from
   * the unignored_* weights, so the caption must quote those figures —
   * totals that disagree with the picture read as a bug.
   * @param {Record<string, any> | null} envelope
   * @param {Record<string, string>} state
   * @returns {string}
   */
  function statusHtml(envelope, state) {
    if (!envelope) {
      return "Loading rollup…";
    }
    const node = envelope.node;
    if (!node) {
      return "Indexing… the treemap fills in as the scan completes.";
    }
    const hideIgnored = state.ignored === "hidden";
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

  /**
   * ("folder", "treemap") renderer. All mutable state lives in this
   * closure; dispose tears down the watch, observer, and tooltip.
   * @param {HTMLElement} container
   * @param {Record<string, any>} ctx
   */
  function renderTreemap(container, ctx) {
    const state = loadState();
    const palette = palettePool.acquire(ctx.path || "");
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
      `<div class="tm-status">${statusHtml(null, state)}</div>`;
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
      status.textContent = statusHtml(envelope, state);
      if (!node || rect.width < 10 || rect.height < 10) {
        viewport.innerHTML = envelope
          ? ""
          : '<div class="tm-loading"><div class="spinner"></div></div>';
        return;
      }
      cells = layoutTree(
        node,
        { w: rect.width, h: rect.height },
        {
          metric: state.metric,
          grouping: state.grouping,
          ignored: state.ignored,
          extTallies: envelope ? envelope.ext_tallies : [],
        },
      );
      const html = cells.map((cell, i) => cellHtml(cell, state, i, palette)).join("");
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
    /** Tab switches hide inactive view containers (display:none)
     * without disposing them, so the watch must not spend fetches on
     * a map nobody can see. The stub-tolerant checks treat missing
     * properties (vm harness) as visible. */
    function isVisible() {
      return mb.viewState.isActive(container);
    }
    const watch = mb.watchRollup(ctx.path, { active: isVisible, ext_rank: "dual" }, (env) => {
      envelope = env;
      palette.sync(
        Array.isArray(env.ext_tallies)
          ? env.ext_tallies
              .map((row) => (Array.isArray(row) && typeof row[0] === "string" ? row[0] : ""))
              .filter((key) => key !== "")
          : [],
      );
      relayout();
    });
    const unsubscribeActive = mb.viewState.subscribeActive(container, (active) => {
      if (active && watch.stale()) {
        void watch.refresh();
      }
    });
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

    const dispose = () => {
      if (disposed) {
        return;
      }
      disposed = true;
      watch.dispose();
      unsubscribeActive();
      window.removeEventListener("resize", onWindowResize);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      mb.tooltip.hide();
      palette.release();
    };
    return Object.freeze({ dispose });
  }

  mb.registerView("folder", "treemap", { render: renderTreemap });
}
