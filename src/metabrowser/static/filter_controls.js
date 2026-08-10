// Filter controls — the one chip family every filtering surface uses.
// See docs/design-system.md ("Filter Controls") for the visual
// contract and docs/project/specs/active/
// plan-2026-08-09-nav-filter-controls.md for why it exists.
//
// Three shapes, one atom:
//   .chip                        the pill itself
//   .chip-group[data-select=one] joined single-select (radiogroup)
//   .chip-group[data-select=many] joined multi-select (independent
//                                 toggles, each its own tab stop)
//   .chip-toggle                 a standalone boolean chip
//
// Single-select segments carry role="radio"/aria-checked and fill with
// the accent tint; multi-select chips carry aria-pressed and fill
// neutral. That split is the only way a user can tell the two apart
// before clicking, so the ARIA and the styling must stay in step.
//
// This module owns markup and interaction, never state: it reports
// what the user asked for and lets the caller decide what to store.

(() => {
  /** @param {unknown} value */
  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /**
   * What a click on `value` means for a group's current selection.
   * Pure, so selection semantics can be tested without a DOM.
   *
   * Single-select returns the clicked value; re-clicking the active
   * segment is a no-op rather than a toggle-to-empty, because a
   * radiogroup with nothing chosen has no meaning here.
   *
   * Multi-select toggles membership and normalizes the empty set to
   * null, which is the same thing as "no constraint" everywhere else
   * in the vocabulary.
   *
   * @param {string} select "one" | "many"
   * @param {string | string[] | null} current
   * @param {string} value
   * @returns {string | string[] | null}
   */
  function nextSelection(select, current, value) {
    if (select === "many") {
      const list = Array.isArray(current) ? current.slice() : [];
      const at = list.indexOf(value);
      if (at >= 0) {
        list.splice(at, 1);
      } else {
        list.push(value);
      }
      return list.length > 0 ? list : null;
    }
    return value;
  }

  /**
   * @param {string | string[] | null} current
   * @param {string} value
   */
  function isSelected(current, value) {
    return Array.isArray(current) ? current.indexOf(value) >= 0 : current === value;
  }

  /**
   * @typedef {{value: string, label: string, title?: string, className?: string}} ChipOption
   * @typedef {{key: string, select?: string, label: string, options: ChipOption[],
   *            value: string | string[] | null, className?: string}} ChipGroupSpec
   */

  /**
   * One joined group. `key` rides every segment as data-chip-key so a
   * single delegated listener can serve every group in a bar.
   * @param {ChipGroupSpec} spec
   */
  function groupHtml(spec) {
    const select = spec.select === "many" ? "many" : "one";
    const current = spec.value !== undefined ? spec.value : null;
    const segments = (spec.options || [])
      .map((opt) => {
        const on = isSelected(current, opt.value);
        // Roving tabindex inside a radiogroup: the group is one tab
        // stop and arrows move within it. Every chip in a `many` group
        // is independently reachable, which is what pressed toggles
        // should be.
        const state =
          select === "one"
            ? ` role="radio" aria-checked="${on}" tabindex="${on ? "0" : "-1"}"`
            : ` aria-pressed="${on}"`;
        const title = opt.title ? ` title="${esc(opt.title)}"` : "";
        const extra = opt.className ? ` ${esc(opt.className)}` : "";
        return (
          `<button type="button" class="chip${extra}"` +
          ` data-chip-key="${esc(spec.key)}" data-chip-value="${esc(opt.value)}"` +
          `${state}${title}>${esc(opt.label)}</button>`
        );
      })
      .join("");
    const role = select === "one" ? "radiogroup" : "group";
    const cls = spec.className ? ` ${esc(spec.className)}` : "";
    return (
      `<span class="chip-group${cls}" data-select="${select}" data-chip-group="${esc(spec.key)}"` +
      ` role="${role}" aria-label="${esc(spec.label)}">${segments}</span>`
    );
  }

  /**
   * A standalone boolean chip. `badge` renders a count pill inside the
   * chip when it is a positive number, and nothing otherwise, so a
   * clean filter state carries no visual weight.
   * @param {{key: string, label: string, pressed?: boolean, badge?: number,
   *          title?: string, className?: string, controls?: string}} spec
   */
  function toggleHtml(spec) {
    const count = typeof spec.badge === "number" && spec.badge > 0 ? spec.badge : 0;
    const badge = count > 0 ? `<span class="chip-badge">${esc(count)}</span>` : "";
    const title = spec.title ? ` title="${esc(spec.title)}"` : "";
    const controls = spec.controls ? ` aria-controls="${esc(spec.controls)}"` : "";
    const cls = spec.className ? ` ${esc(spec.className)}` : "";
    return (
      `<button type="button" class="chip chip-toggle${cls}"` +
      ` data-chip-key="${esc(spec.key)}" aria-pressed="${spec.pressed === true}"` +
      `${controls}${title}>${esc(spec.label)}${badge}</button>`
    );
  }

  /**
   * @param {{label?: string, className?: string}} [spec]
   */
  function clearHtml(spec) {
    const opts = spec || {};
    const cls = opts.className ? ` ${esc(opts.className)}` : "";
    return (
      `<button type="button" class="chip-clear${cls}" data-chip-clear>` +
      `${esc(opts.label || "Clear all")}</button>`
    );
  }

  /**
   * Wire one container. `onChange(key, value, select)` fires for group
   * segments, `onToggle(key, nextPressed)` for standalone chips, and
   * `onClear()` for the clear affordance. Returns a disposer, because
   * every listener the shell installs needs a way back out.
   *
   * @param {Element} root
   * @param {{onChange?: (key: string, value: string, select: string) => void,
   *          onToggle?: (key: string, pressed: boolean) => void,
   *          onClear?: () => void}} handlers
   */
  function bind(root, handlers) {
    const opts = handlers || {};

    /** @param {Event} event */
    function onClick(event) {
      const target = /** @type {Element | null} */ (event.target);
      if (!target || typeof target.closest !== "function") {
        return;
      }
      const clear = target.closest("[data-chip-clear]");
      if (clear && root.contains(clear)) {
        if (opts.onClear) {
          opts.onClear();
        }
        return;
      }
      const chip = /** @type {HTMLElement | null} */ (target.closest(".chip[data-chip-key]"));
      if (!chip || !root.contains(chip)) {
        return;
      }
      const key = chip.getAttribute("data-chip-key") || "";
      const group = chip.closest(".chip-group");
      if (!group) {
        if (opts.onToggle) {
          opts.onToggle(key, chip.getAttribute("aria-pressed") !== "true");
        }
        return;
      }
      const select = group.getAttribute("data-select") === "many" ? "many" : "one";
      // A single-select segment that is already on has nothing to say.
      if (select === "one" && chip.getAttribute("aria-checked") === "true") {
        return;
      }
      if (opts.onChange) {
        opts.onChange(key, chip.getAttribute("data-chip-value") || "", select);
      }
    }

    /** @param {Event} event */
    function onKeyDown(event) {
      const ev = /** @type {KeyboardEvent} */ (event);
      const key = ev.key;
      if (key !== "ArrowLeft" && key !== "ArrowRight" && key !== "Home" && key !== "End") {
        return;
      }
      const target = /** @type {Element | null} */ (ev.target);
      if (!target || typeof target.closest !== "function") {
        return;
      }
      const group = target.closest('.chip-group[data-select="one"]');
      if (!group || !root.contains(group)) {
        return;
      }
      const chips = Array.prototype.slice.call(group.querySelectorAll(".chip[data-chip-key]"));
      if (chips.length === 0) {
        return;
      }
      const at = chips.indexOf(target.closest(".chip[data-chip-key]"));
      let next = at;
      if (key === "Home") {
        next = 0;
      } else if (key === "End") {
        next = chips.length - 1;
      } else if (at >= 0) {
        // Wrap, matching the ARIA radiogroup pattern.
        const step = key === "ArrowRight" ? 1 : -1;
        next = (at + step + chips.length) % chips.length;
      }
      const chip = /** @type {HTMLElement | undefined} */ (chips[next]);
      if (!chip) {
        return;
      }
      ev.preventDefault();
      chip.focus();
      if (opts.onChange) {
        opts.onChange(
          chip.getAttribute("data-chip-key") || "",
          chip.getAttribute("data-chip-value") || "",
          "one",
        );
      }
    }

    root.addEventListener("click", onClick);
    root.addEventListener("keydown", onKeyDown);
    return () => {
      root.removeEventListener("click", onClick);
      root.removeEventListener("keydown", onKeyDown);
    };
  }

  /** @type {Record<string, any>} */ (window).MetabrowserFilterControls = {
    escapeHtml: esc,
    nextSelection,
    isSelected,
    groupHtml,
    toggleHtml,
    clearHtml,
    bind,
  };
})();
