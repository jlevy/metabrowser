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
   * @typedef {{value: string, label: string, title?: string, className?: string,
   *            count?: number, icon?: string, iconClass?: string}} ChipOption
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
   *
   * Passing `icon` (a raw SVG string, supplied by the caller so this
   * module carries no icon dependency) makes it an icon-only control
   * on the app's `.icon-btn` primitive. Such a button has no
   * accessible name of its own, so `ariaLabel` stops being optional:
   * pass one that says what will happen, not what the glyph looks
   * like.
   *
   * @param {{key: string, label?: string, pressed?: boolean, badge?: number,
   *          title?: string, className?: string, controls?: string,
   *          icon?: string, ariaLabel?: string}} spec
   */
  function toggleHtml(spec) {
    const count = typeof spec.badge === "number" && spec.badge > 0 ? spec.badge : 0;
    const badge = count > 0 ? `<span class="chip-badge">${esc(count)}</span>` : "";
    const title = spec.title ? ` title="${esc(spec.title)}"` : "";
    const controls = spec.controls ? ` aria-controls="${esc(spec.controls)}"` : "";
    const ariaLabel = spec.ariaLabel ? ` aria-label="${esc(spec.ariaLabel)}"` : "";
    const cls = spec.className ? ` ${esc(spec.className)}` : "";
    if (spec.icon) {
      // Icon-only controls are all the same control: this rides the
      // app's .icon-btn primitive, so it matches the settings gear and
      // the print button rather than being a pill with a glyph in it.
      // The badge sits outside the button because .icon-btn is a fixed
      // --icon-btn-size box built to hold exactly one glyph.
      return (
        `${badge}<button type="button" class="icon-btn${cls}"` +
        ` data-chip-key="${esc(spec.key)}" aria-pressed="${spec.pressed === true}"` +
        `${controls}${ariaLabel}${title}>${spec.icon}</button>`
      );
    }
    return (
      `<button type="button" class="chip chip-toggle${cls}"` +
      ` data-chip-key="${esc(spec.key)}" aria-pressed="${spec.pressed === true}"` +
      `${controls}${ariaLabel}${title}>${esc(spec.label || "")}${badge}</button>`
    );
  }

  /**
   * A chip that opens a multi-select dropdown.
   *
   * There was no widget for this: the app had a floating `.menu` of
   * single-choice `.menu-item` rows and a native `.menu-select`, and
   * neither lets you pick several things. This composes the existing
   * menu surface — same border, radius, shadow, and dismissal rules —
   * with `menuitemcheckbox` rows, so it inherits the app's one menu
   * look rather than introducing a second.
   *
   * The trigger summarises the selection the way a select does ("Any
   * type", "md", "md +2") so the collapsed control still answers "what
   * is filtered?" without being opened.
   *
   * @param {{key: string, label: string, options: ChipOption[],
   *          value: string[] | null, anyLabel: string, open?: boolean,
   *          menuId: string}} spec
   */
  function menuGroupHtml(spec) {
    const selected = Array.isArray(spec.value) ? spec.value : [];
    const chosen = (spec.options || []).filter((o) => selected.indexOf(o.value) >= 0);
    let summary = spec.anyLabel;
    if (chosen.length === 1) {
      summary = chosen[0].label;
    } else if (chosen.length > 1) {
      summary = `${chosen[0].label} +${chosen.length - 1}`;
    }
    const rows = (spec.options || [])
      .map((opt) => {
        const on = selected.indexOf(opt.value) >= 0;
        const extra = opt.className ? ` ${esc(opt.className)}` : "";
        const count =
          typeof opt.count === "number"
            ? `<span class="chip-menu-count">${esc(opt.count.toLocaleString())}</span>`
            : "";
        // The file-type icon, not a colored label: the icon is what
        // identifies a type everywhere else in the app, and tinting
        // the text of every row would make eight competing hues fight
        // the check mark for the eye. `iconClass` still carries the
        // ft-* subtype so the glyph takes the same hue it has in the
        // tree.
        const icon = opt.icon
          ? `<span class="menu-item-icon ${esc(opt.iconClass || "")}">${opt.icon}</span>`
          : "";
        return (
          `<button type="button" class="menu-item chip-menu-item${extra}"` +
          ` role="menuitemcheckbox" aria-checked="${on}"` +
          ` data-chip-key="${esc(spec.key)}" data-chip-value="${esc(opt.value)}">` +
          `<span class="chip-menu-check" aria-hidden="true">${on ? "✓" : ""}</span>` +
          `${icon}<span class="menu-item-label">${esc(opt.label)}</span>${count}</button>`
        );
      })
      .join("");
    // A row rather than a separate Clear: "Any type" is the default
    // value of this dimension, so it belongs in the same list as the
    // other values.
    const anyRow =
      `<button type="button" class="menu-item chip-menu-item"` +
      ` role="menuitemcheckbox" aria-checked="${selected.length === 0}"` +
      ` data-chip-key="${esc(spec.key)}" data-chip-any>` +
      `<span class="chip-menu-check" aria-hidden="true">${selected.length === 0 ? "✓" : ""}</span>` +
      `<span class="menu-item-label">${esc(spec.anyLabel)}</span></button>`;
    return (
      `<span class="chip-menu" data-chip-menu="${esc(spec.key)}"` +
      ` aria-expanded="${spec.open === true}">` +
      `<button type="button" class="chip chip-menu-trigger" data-chip-menu-toggle="${esc(spec.key)}"` +
      ` aria-haspopup="true" aria-expanded="${spec.open === true}"` +
      ` aria-controls="${esc(spec.menuId)}" aria-label="${esc(spec.label)}">` +
      `${esc(summary)}<span class="chip-menu-caret" aria-hidden="true">⌄</span></button>` +
      `<span class="menu chip-menu-panel" id="${esc(spec.menuId)}" role="menu"` +
      ` aria-label="${esc(spec.label)}">${anyRow}${rows}</span></span>`
    );
  }

  /**
   * A labelled checkbox, for a boolean whose *polarity* has to be
   * legible.
   *
   * This is the one deliberate break from the family's
   * button-with-aria-pressed rule, and the reason is the label. A
   * pressed pill reading "Gitignored" does not say whether pressed
   * means those rows are shown or filtered away — the user has to
   * click it to find out. "Show ignored" with a tick states its own
   * polarity, and a checkbox is the control every user already knows
   * for that. It is also visibly smaller than a pill, which matters
   * where it sits beside one.
   *
   * @param {{key: string, label: string, checked?: boolean,
   *          title?: string, className?: string}} spec
   */
  function checkHtml(spec) {
    const title = spec.title ? ` title="${esc(spec.title)}"` : "";
    const cls = spec.className ? ` ${esc(spec.className)}` : "";
    return (
      `<label class="filter-check${cls}"${title}>` +
      `<input type="checkbox" data-chip-check="${esc(spec.key)}"` +
      `${spec.checked === true ? " checked" : ""}>` +
      `<span>${esc(spec.label)}</span></label>`
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
   *          onMenuToggle?: (key: string, open: boolean) => void,
   *          onMenuPick?: (key: string, value: string | null) => void,
   *          onClear?: () => void}} handlers
   */
  function bind(root, handlers) {
    const opts = handlers || {};

    /** Any open dropdown, so outside clicks and Escape can close it. */
    function openMenuKey() {
      const open = root.querySelector('.chip-menu[aria-expanded="true"]');
      return open ? open.getAttribute("data-chip-menu") : null;
    }

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
      // Dropdown trigger.
      const menuToggle = target.closest("[data-chip-menu-toggle]");
      if (menuToggle && root.contains(menuToggle)) {
        const key = menuToggle.getAttribute("data-chip-menu-toggle") || "";
        const wrap = menuToggle.closest(".chip-menu");
        const isOpen = wrap?.getAttribute("aria-expanded") === "true";
        if (opts.onMenuToggle) {
          opts.onMenuToggle(key, !isOpen);
        }
        return;
      }
      // A row inside the dropdown. Checked before the generic .chip
      // branch because menu rows are .menu-item, not .chip.
      const menuItem = /** @type {HTMLElement | null} */ (
        target.closest(".chip-menu-item[data-chip-key]")
      );
      if (menuItem && root.contains(menuItem)) {
        const key = menuItem.getAttribute("data-chip-key") || "";
        if (opts.onMenuPick) {
          opts.onMenuPick(
            key,
            menuItem.hasAttribute("data-chip-any")
              ? null
              : menuItem.getAttribute("data-chip-value") || "",
          );
        }
        return;
      }
      // Not `.chip[data-chip-key]`: a standalone toggle may render as
      // an .icon-btn instead of a pill, and both answer to the same
      // handler.
      const chip = /** @type {HTMLElement | null} */ (target.closest("[data-chip-key]"));
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

    /**
     * Move focus within a list of elements and return the one landed
     * on. Wraps, matching the ARIA patterns for both radiogroups and
     * menus.
     * @param {Element[]} items
     * @param {Element | null} from
     * @param {string} key
     */
    function moveFocus(items, from, key) {
      if (items.length === 0) {
        return null;
      }
      const at = from ? items.indexOf(from) : -1;
      let next = at;
      if (key === "Home") {
        next = 0;
      } else if (key === "End") {
        next = items.length - 1;
      } else if (at >= 0) {
        const step = key === "ArrowRight" || key === "ArrowDown" ? 1 : -1;
        next = (at + step + items.length) % items.length;
      } else {
        next = 0;
      }
      const el = /** @type {HTMLElement | undefined} */ (items[next]);
      if (el) {
        el.focus();
      }
      return el || null;
    }

    /** @param {Event} event */
    function onKeyDown(event) {
      const ev = /** @type {KeyboardEvent} */ (event);
      const key = ev.key;
      const target = /** @type {Element | null} */ (ev.target);
      if (!target || typeof target.closest !== "function") {
        return;
      }
      // Inside an open dropdown, Up/Down walk the rows. The menu is a
      // list, so it takes the vertical keys; the horizontal ones below
      // belong to the segmented groups.
      const panel = target.closest(".chip-menu-panel");
      if (panel) {
        if (key !== "ArrowDown" && key !== "ArrowUp" && key !== "Home" && key !== "End") {
          return;
        }
        ev.preventDefault();
        moveFocus(
          Array.prototype.slice.call(panel.querySelectorAll(".chip-menu-item")),
          target.closest(".chip-menu-item"),
          key,
        );
        return;
      }
      if (key !== "ArrowLeft" && key !== "ArrowRight" && key !== "Home" && key !== "End") {
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
      ev.preventDefault();
      // A radiogroup selects on arrow, unlike the menu above, where
      // moving and choosing are separate acts.
      const chip = moveFocus(chips, target.closest(".chip[data-chip-key]"), key);
      if (!chip) {
        return;
      }
      if (opts.onChange) {
        opts.onChange(
          chip.getAttribute("data-chip-key") || "",
          chip.getAttribute("data-chip-value") || "",
          "one",
        );
      }
    }

    // Outside interaction dismisses the dropdown. Bound on the
    // document because the whole point is clicks the bar never sees;
    // the disposer below detaches it with the rest.
    /** @param {Event} event */
    function onDocumentPointerDown(event) {
      const openKey = openMenuKey();
      if (openKey === null) {
        return;
      }
      const target = /** @type {Node | null} */ (event.target);
      if (target && root.contains(target)) {
        return;
      }
      if (opts.onMenuToggle) {
        opts.onMenuToggle(openKey, false);
      }
    }

    // Escape has to work even when focus has left the bar, so it is
    // bound on the document. Kept separate from onKeyDown so arrow
    // traversal stays scoped to the bar and nothing fires twice.
    /** @param {Event} event */
    function onDocumentEscape(event) {
      if (/** @type {KeyboardEvent} */ (event).key !== "Escape") {
        return;
      }
      const openKey = openMenuKey();
      if (openKey !== null && opts.onMenuToggle) {
        opts.onMenuToggle(openKey, false);
      }
    }

    // Checkboxes report through `change`, not `click`: that is the
    // event that fires for keyboard activation too.
    /** @param {Event} event */
    function onChange(event) {
      const target = /** @type {HTMLInputElement | null} */ (event.target);
      if (!target || typeof target.getAttribute !== "function") {
        return;
      }
      const key = target.getAttribute("data-chip-check");
      if (key && opts.onToggle) {
        opts.onToggle(key, target.checked === true);
      }
    }

    root.addEventListener("click", onClick);
    root.addEventListener("change", onChange);
    root.addEventListener("keydown", onKeyDown);
    const doc = root.ownerDocument;
    doc?.addEventListener("pointerdown", onDocumentPointerDown);
    doc?.addEventListener("keydown", onDocumentEscape);
    return () => {
      root.removeEventListener("click", onClick);
      root.removeEventListener("change", onChange);
      root.removeEventListener("keydown", onKeyDown);
      doc?.removeEventListener("pointerdown", onDocumentPointerDown);
      doc?.removeEventListener("keydown", onDocumentEscape);
    };
  }

  /** @type {Record<string, any>} */ (window).MetabrowserFilterControls = {
    escapeHtml: esc,
    nextSelection,
    isSelected,
    groupHtml,
    menuGroupHtml,
    toggleHtml,
    checkHtml,
    clearHtml,
    bind,
  };
})();
