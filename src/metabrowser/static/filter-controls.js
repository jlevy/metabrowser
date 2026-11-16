// Filter controls — the one chip family every filtering surface uses.
// See docs/design-system.md ("Filter Controls") for the visual
// contract and docs/project/specs/active/
// plan-2026-08-09-nav-filter-controls.md for why it exists.
//
// Three shapes, one atom:
//   .chip                        the pill itself
//   .chip-group[data-layout=joined] single-row segmented control
//   .chip-group[data-layout=wrap]   wrapping cluster of independent
//                                   chips
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
   * The attribute that carries a dropdown row's letter, lowercase, or nothing when the row
   * declares none or one that is not a single letter. A row's letter chooses it while its
   * menu is open and has focus (docs/design-system.md, "Keys in a Menu").
   * @param {unknown} key
   */
  function rowKeyAttr(key) {
    const letter = typeof key === "string" ? key.toLowerCase() : "";
    return /^[a-z]$/.test(letter) ? ` data-menu-key="${letter}"` : "";
  }

  /**
   * `key`, on a dropdown's option, is the letter that chooses its row while the menu is
   * open and has focus; the shell's keymap gives it to the shortcut registry.
   * @typedef {{value: string, label: string, tip?: string, className?: string,
   *            count?: number, icon?: string, iconClass?: string,
   *            ageClass?: string, key?: string}} ChipOption
   * @typedef {{key: string, select?: string, layout?: string, label: string,
   *            options: ChipOption[], value: string | string[] | null,
   *            className?: string}} ChipGroupSpec
   */

  /**
   * One semantic group, rendered either as a single joined row or as a
   * wrapping chip cluster. `key` rides every segment as data-chip-key
   * so a single delegated listener can serve every group in a bar.
   * @param {ChipGroupSpec} spec
   */
  function groupHtml(spec) {
    const select = spec.select === "many" ? "many" : "one";
    const layout = spec.layout === "wrap" ? "wrap" : "joined";
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
        const tip = opt.tip ? ` data-tip-text="${esc(opt.tip)}"` : "";
        const extra = opt.className ? ` ${esc(opt.className)}` : "";
        return (
          `<button type="button" class="chip${extra}"` +
          ` data-chip-key="${esc(spec.key)}" data-chip-value="${esc(opt.value)}"` +
          `${state}${tip}>${esc(opt.label)}</button>`
        );
      })
      .join("");
    const role = select === "one" ? "radiogroup" : "group";
    const cls = spec.className ? ` ${esc(spec.className)}` : "";
    return (
      `<span class="chip-group${cls}" data-select="${select}" data-layout="${layout}"` +
      ` data-chip-group="${esc(spec.key)}"` +
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
   *          tip?: string, className?: string, controls?: string,
   *          icon?: string, ariaLabel?: string}} spec
   */
  function toggleHtml(spec) {
    const count = typeof spec.badge === "number" && spec.badge > 0 ? spec.badge : 0;
    const badge = count > 0 ? `<span class="chip-badge">${esc(count)}</span>` : "";
    const tip = spec.tip ? ` data-tip-text="${esc(spec.tip)}"` : "";
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
        `${controls}${ariaLabel}${tip}>${spec.icon}</button>`
      );
    }
    return (
      `<button type="button" class="chip chip-toggle${cls}"` +
      ` data-chip-key="${esc(spec.key)}" aria-pressed="${spec.pressed === true}"` +
      `${controls}${ariaLabel}${tip}>${esc(spec.label || "")}${badge}</button>`
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
   * type", ".md", ".md +2") so the collapsed control still answers
   * "what is filtered?" without being opened.
   *
   * `select` picks the kind, exactly as it does for a chip group:
   * "many" (default) takes a list and `menuitemcheckbox` rows; "one"
   * takes a scalar and `menuitemradio` rows, and `anyValue` names the
   * scalar that means "no constraint" so the any-row can show as
   * checked.
   *
   * `presets` are named shorthands rendered above the raw list, each
   * standing for the full set of values it names.
   *
   * The panel's height is fitted to its rows and the window (`fitOpenMenus`):
   * `bind` fits it when its trigger opens it, and a consumer that renders it
   * open another way calls `fitOpenMenus(root)` after rendering.
   *
   * An option's `key`, and `anyKey` for the any-row, is the letter that chooses
   * that row while the menu is open and has focus. A menu that gives one row a
   * letter gives every row one (docs/design-system.md, "Keys in a Menu").
   *
   * @param {{key: string, label: string, options: ChipOption[],
   *          value: string[] | string | null, anyLabel: string,
   *          anyValue?: string, anyKey?: string, select?: string, open?: boolean,
   *          menuId: string,
   *          presets?: Array<{id: string, label: string, values: string[], count?: number}>,
   *          presetSections?: Array<{id: string, label?: string, presets: Array<{id: string, label: string, values: string[], count?: number}>}>}} spec
   */
  function menuGroupHtml(spec) {
    const many = spec.select !== "one";
    const menuChevron = window.MetabrowserIcons?.toggle || "";
    // Single-select carries a scalar, multi-select a list; normalizing
    // to a list here keeps the row loop identical for both.
    const selected = many
      ? Array.isArray(spec.value)
        ? spec.value
        : []
      : spec.value === null || spec.value === undefined || spec.value === spec.anyValue
        ? []
        : [String(spec.value)];
    const chosen = (spec.options || []).filter((o) => selected.indexOf(o.value) >= 0);
    let summary = spec.anyLabel;
    if (chosen.length === 1) {
      summary = chosen[0].label;
    } else if (chosen.length > 1) {
      summary = `${chosen[0].label} +${chosen.length - 1}`;
    }
    // A selection that is exactly one preset reads better by its name
    // than as ".md +21" — the user picked "Docs", so say Docs.
    const presetSections = Array.isArray(spec.presetSections)
      ? spec.presetSections
      : spec.presets?.length
        ? [{ id: "presets", presets: spec.presets }]
        : [];
    const allPresets = presetSections.flatMap((section) => section.presets || []);
    const exact = allPresets.find(
      (preset) =>
        preset.values.length > 0 &&
        preset.values.length === selected.length &&
        preset.values.every((value) => selected.indexOf(value) >= 0),
    );
    if (exact) {
      summary = exact.label;
    }
    // A radio menu names one choice; a checkbox menu names several.
    // Getting this wrong is the same failure the chip groups guard
    // against — the control would not say which kind it is.
    const rowRole = many ? "menuitemcheckbox" : "menuitemradio";
    const rows = (spec.options || [])
      .map((opt) => {
        const on = selected.indexOf(opt.value) >= 0;
        const extra = opt.className ? ` ${esc(opt.className)}` : "";
        const tip = opt.tip ? ` data-tip-text="${esc(opt.tip)}"` : "";
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
        // `ageClass` selects the shared age foreground, so a menu row
        // and the rows it keeps stay in sync.
        const age = opt.ageClass ? ` ${esc(opt.ageClass)}` : "";
        return (
          `<button type="button" class="menu-item chip-menu-item${extra}${age}"` +
          `${tip}` +
          ` role="${rowRole}" aria-checked="${on}"` +
          ` data-chip-key="${esc(spec.key)}" data-chip-value="${esc(opt.value)}"` +
          `${rowKeyAttr(opt.key)}>` +
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
      ` role="${rowRole}" aria-checked="${selected.length === 0}"` +
      ` data-chip-key="${esc(spec.key)}" data-chip-any${rowKeyAttr(spec.anyKey)}>` +
      `<span class="chip-menu-check" aria-hidden="true">${selected.length === 0 ? "✓" : ""}</span>` +
      `<span class="menu-item-label">${esc(spec.anyLabel)}</span></button>`;

    // Named shorthands above the raw list. A preset is checked only
    // when every value it stands for is selected, so a half-covered
    // group never claims to be on. Each section is the menu's one group
    // pattern (docs/design-system.md, "Groups in a Menu"): a .menu-group
    // draws its own divider, and its heading names it for assistive
    // technology as well as on screen.
    const presetRows = presetSections
      .filter((section) => section.presets.length > 0)
      .map((section, sectionIndex) => {
        const labelId = `${spec.menuId}-section-${sectionIndex}`;
        return (
          `<div class="menu-group" role="group" aria-labelledby="${esc(labelId)}"` +
          ` data-chip-menu-section="${esc(section.id)}">` +
          `<div class="group-heading" id="${esc(labelId)}">${esc(section.label || section.id)}</div>` +
          section.presets
            .map((preset) => {
              const on =
                preset.values.length > 0 &&
                preset.values.every((value) => selected.indexOf(value) >= 0);
              const count =
                typeof preset.count === "number"
                  ? `<span class="chip-menu-count">${esc(preset.count.toLocaleString())}</span>`
                  : "";
              return (
                `<button type="button" class="menu-item chip-menu-item chip-menu-preset"` +
                ` role="${rowRole}" aria-checked="${on}"` +
                ` data-chip-key="${esc(spec.key)}" data-chip-preset="${esc(preset.id)}">` +
                `<span class="chip-menu-check" aria-hidden="true">${on ? "✓" : ""}</span>` +
                `<span class="menu-item-label">${esc(preset.label)}</span>${count}</button>`
              );
            })
            .join("") +
          `</div>`
        );
      })
      .join("");
    // The raw rows have no heading, so a plain separator sets them off.
    const optionSeparator = presetRows ? '<div class="menu-separator"></div>' : "";
    return (
      `<span class="chip-menu" data-chip-menu="${esc(spec.key)}"` +
      ` aria-expanded="${spec.open === true}">` +
      `<button type="button" class="chip chip-menu-trigger disclosure-toggle" data-chip-menu-toggle="${esc(spec.key)}"` +
      // A trigger showing a value has to look different from one
      // showing "Any …", or a set filter is invisible until you read
      // the label — which is the one thing a collapsed control must
      // not require.
      ` data-active="${selected.length > 0}"` +
      ` aria-haspopup="true" aria-expanded="${spec.open === true}"` +
      ` aria-controls="${esc(spec.menuId)}" aria-label="${esc(spec.label)}">` +
      `${esc(summary)}<span class="chip-menu-caret" aria-hidden="true">${menuChevron}</span></button>` +
      `<span class="menu chip-menu-panel" id="${esc(spec.menuId)}" role="menu"` +
      ` aria-label="${esc(spec.label)}">${anyRow}${presetRows}${optionSeparator}${rows}</span></span>`
    );
  }

  // How tall an open dropdown may be: up to 16 rows, as the user asked, and always
  // inside the window. Measured in headless Chrome on the Files type menu
  // (2026-11-15): every row, check or icon, is 29px and the panel's padding and
  // border add 10px, so 16 rows are 474px. The cap is rows times the rendered row,
  // so it follows the row if its type or padding changes.
  const MENU_MAX_ROWS = 16;
  // The space kept between a dropdown and the window's edge: the tooltip's
  // TOOLTIP_VIEWPORT_MARGIN in app.js, so every floating surface stops short of
  // the edge by the same amount.
  const MENU_WINDOW_MARGIN = 8;

  /**
   * The max-height for an open dropdown: MENU_MAX_ROWS rendered rows and the
   * frame, or the room from the panel's top to the window's bottom edge less
   * MENU_WINDOW_MARGIN, whichever is smaller; never less than one row and the
   * frame, so a menu opened with less room is still a menu, scrolled one row at a
   * time. A menu with fewer rows is shorter than its cap and keeps its natural
   * height. Pure, so the rule is checked without a browser.
   *
   * @param {{rowHeight: number, frame: number, top: number, windowHeight: number}} geometry
   *   `rowHeight` is one rendered row, `frame` the panel's vertical padding and
   *   border, `top` the panel's top edge in the viewport, and `windowHeight` the
   *   viewport's height.
   * @returns {number}
   */
  function menuMaxHeight(geometry) {
    const rows = MENU_MAX_ROWS * geometry.rowHeight + geometry.frame;
    const room = geometry.windowHeight - MENU_WINDOW_MARGIN - geometry.top;
    return Math.max(geometry.rowHeight + geometry.frame, Math.min(rows, room));
  }

  /**
   * Fit one open dropdown panel to its rows and the window, reading the
   * geometry `menuMaxHeight` needs from the rendered panel.
   * @param {HTMLElement} panel
   */
  function fitMenuPanel(panel) {
    const view = panel.ownerDocument?.defaultView;
    const row = panel.querySelector(".menu-item");
    // A panel with no box (its toolbar hidden) has no geometry to read: fitting it
    // would write a one-row sliver that outlives the toolbar's return.
    if (!view || !row || panel.getClientRects().length === 0) {
      return;
    }
    const style = view.getComputedStyle(panel);
    const frame =
      parseFloat(style.paddingTop) +
      parseFloat(style.paddingBottom) +
      parseFloat(style.borderTopWidth) +
      parseFloat(style.borderBottomWidth);
    const height = menuMaxHeight({
      rowHeight: row.getBoundingClientRect().height,
      frame,
      top: panel.getBoundingClientRect().top,
      windowHeight: view.innerHeight,
    });
    panel.style.maxHeight = `${height}px`;
  }

  /**
   * Fit every open dropdown under `root`. `bind` calls it when its trigger is
   * clicked and the consumer has rendered the menu open, and again when the
   * window resizes; a consumer that opens or re-renders a menu another way, as
   * the shell's keyboard path does, calls it after rendering.
   * @param {Element} root
   */
  function fitOpenMenus(root) {
    for (const panel of root.querySelectorAll(
      '.chip-menu[aria-expanded="true"] > .chip-menu-panel',
    )) {
      fitMenuPanel(/** @type {HTMLElement} */ (panel));
    }
  }

  // ── A segmented group wider than its line ───────────────────────
  // Segmented controls never wrap (docs/design-system.md, "Groups Or Dropdowns"). A
  // navigation toolbar's pane can be dragged narrower than a short set, the Pulls tab's
  // Show group among them, so there a joined group wider than its whole line takes the
  // wrapping cluster layout instead, and takes the joined layout back once its line holds
  // it. `data-fit="wrap"` on the group asks for that, and styles.css draws it as
  // `data-layout="wrap"`.

  const JOINED_GROUPS = '.chip-group[data-layout="joined"]';

  /**
   * Whether a joined group fits its line: `joined` is its width in the joined layout and
   * `room` its line's content width. Neither depends on which layout the group shows (the
   * joined width is measured off-layout, on a copy, and a toolbar row is as wide as its
   * toolbar), so the answer at one pane width is the same however often it is asked: the
   * two layouts cannot alternate near the break, and no hysteresis is needed. Pure.
   *
   * @param {{joined: number, room: number}} widths
   */
  function joinedGroupFits(widths) {
    return widths.joined <= widths.room;
  }

  /**
   * A joined group's width in the joined layout, whichever layout it shows: an invisible
   * copy beside it, out of flow, so the same rules match it and the group itself is never
   * laid out joined where that does not fit. The copy is gone before the browser can paint.
   * @param {HTMLElement} group
   */
  function joinedWidth(group) {
    const probe = /** @type {HTMLElement} */ (group.cloneNode(true));
    probe.removeAttribute("data-fit");
    for (const element of [probe, ...probe.querySelectorAll("[id]")]) {
      element.removeAttribute("id");
    }
    probe.setAttribute("aria-hidden", "true");
    probe.style.cssText =
      "position: absolute; inset-block-start: 0; inset-inline-start: 0; visibility: hidden;" +
      " pointer-events: none; flex: none; width: max-content; max-width: none; min-width: 0;";
    group.after(probe);
    const width = probe.getBoundingClientRect().width;
    probe.remove();
    return width;
  }

  /**
   * Give each joined group under `root` the layout its line holds: joined where it fits,
   * the cluster where it does not. A group with no box (its toolbar hidden) keeps the one
   * it has, since there is no line to measure.
   * @param {Element} root
   */
  function fitJoinedGroups(root) {
    for (const element of root.querySelectorAll(JOINED_GROUPS)) {
      const group = /** @type {HTMLElement} */ (element);
      const line = group.parentElement;
      const view = group.ownerDocument?.defaultView;
      if (!line || !view || group.getClientRects().length === 0) {
        continue;
      }
      const style = view.getComputedStyle(line);
      const room =
        line.getBoundingClientRect().width -
        parseFloat(style.paddingLeft) -
        parseFloat(style.paddingRight) -
        parseFloat(style.borderLeftWidth) -
        parseFloat(style.borderRightWidth);
      const fits = joinedGroupFits({ joined: joinedWidth(group), room });
      if (fits && group.hasAttribute("data-fit")) {
        group.removeAttribute("data-fit");
      } else if (!fits && group.getAttribute("data-fit") !== "wrap") {
        group.setAttribute("data-fit", "wrap");
      }
    }
  }

  /**
   * Keep the joined groups under a navigation toolbar's `root` fitted to their lines, and
   * return what stops it. A group is fitted at once, again when its text changes or its
   * toolbar is shown (a mutation, before the browser paints it), and again when the row or
   * a chip changes size: a pane dragged narrower, a font set or face arriving. A hidden
   * toolbar has no line to fit, so one shown again after its pane crossed the break would
   * otherwise draw its stale layout until the size change's frame. A size change is fitted
   * in the next frame, not in the ResizeObserver's own callback: a layout changed there
   * resizes the panel under the toolbar, which other observers watch, and the browser
   * reports that as a ResizeObserver loop error. So a drag across the break draws the
   * outgoing layout for one frame, and never both in turn.
   * @param {Element} root
   * @returns {() => void}
   */
  function keepJoinedGroupsFitted(root) {
    const view = root.ownerDocument?.defaultView;
    const toolbar = typeof root.closest === "function" ? root.closest("[data-nav-toolbar]") : null;
    if (
      !view ||
      toolbar === null ||
      typeof view.ResizeObserver !== "function" ||
      typeof view.MutationObserver !== "function"
    ) {
      return () => {};
    }
    let disposed = false;
    /** @type {number | null} */
    let frame = null;
    /** @type {MutationObserver | null} */
    let mutations = null;
    const fit = () => {
      if (disposed) {
        return;
      }
      fitJoinedGroups(root);
      // The probes were mutations of `root` too; they are not the reader's.
      mutations?.takeRecords();
    };
    const sizes = new view.ResizeObserver(() => {
      if (disposed || frame !== null) {
        return;
      }
      frame = view.requestAnimationFrame(() => {
        frame = null;
        fit();
      });
    });
    // The row, and the chips of its joined groups, which the consumer may replace.
    /** @type {Set<Element>} */
    const watched = new Set();
    const watchSizes = () => {
      const chips = new Set(root.querySelectorAll(`${JOINED_GROUPS} > .chip`));
      for (const chip of watched) {
        if (!chips.has(chip)) {
          sizes.unobserve(chip);
          watched.delete(chip);
        }
      }
      for (const chip of chips) {
        if (!watched.has(chip)) {
          sizes.observe(chip);
          watched.add(chip);
        }
      }
    };
    sizes.observe(root);
    mutations = new view.MutationObserver(() => {
      if (disposed) {
        return;
      }
      watchSizes();
      fit();
    });
    const text = { childList: true, characterData: true, subtree: true };
    // The toolbar shown: the main tabs show the one in front by its `hidden` attribute. An
    // observer holds one set of options per node, and a second `observe` of the node
    // replaces the first, so a row that is its own toolbar, as the Files bar is, takes both.
    const shown = { attributes: true, attributeFilter: ["hidden"] };
    if (toolbar === root) {
      mutations.observe(root, { ...text, ...shown });
    } else {
      mutations.observe(root, text);
      mutations.observe(toolbar, shown);
    }
    watchSizes();
    fit();
    return () => {
      disposed = true;
      sizes.disconnect();
      mutations?.disconnect();
      if (frame !== null) {
        view.cancelAnimationFrame(frame);
        frame = null;
      }
    };
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
   *          tip?: string, className?: string}} spec
   */
  function checkHtml(spec) {
    const tip = spec.tip ? ` data-tip-text="${esc(spec.tip)}"` : "";
    const cls = spec.className ? ` ${esc(spec.className)}` : "";
    return (
      `<label class="filter-check${cls}"${tip}>` +
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

  // ── Focus in a dropdown ──────────────────────────────────────
  // One path for every dropdown (docs/design-system.md, "Keys in a Menu"): opening one, by
  // its trigger or by a key, focuses its checked row or else its first; Escape, or a
  // choice that closes it, gives focus back to its trigger; and a consumer's rebuild of
  // the markup keeps focus on the same control.

  /** @param {string} value A value for a double-quoted attribute selector. */
  const quoted = (value) => value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');

  // The attributes that name a filter control, so it can be found again after a rebuild.
  const CONTROL_ATTRIBUTES = [
    "data-chip-menu-toggle",
    "data-chip-key",
    "data-chip-value",
    "data-chip-any",
    "data-chip-preset",
    "data-chip-check",
    "data-chip-clear",
  ];
  const CONTROL_SELECTOR = CONTROL_ATTRIBUTES.map((name) => `[${name}]`).join(", ");

  /**
   * A selector for the control `element` is or is in, which finds the same control in
   * rebuilt markup: each naming attribute it carries, by value, and each it lacks, absent.
   * @param {Element} element
   */
  function controlSelector(element) {
    const control = element.closest(CONTROL_SELECTOR);
    if (!control) {
      return null;
    }
    return CONTROL_ATTRIBUTES.map((name) => {
      const value = control.getAttribute(name);
      return value === null ? `:not([${name}])` : `[${name}="${quoted(value)}"]`;
    }).join("");
  }

  /**
   * Focus an open dropdown's checked row, or else its first row, so its arrow keys,
   * Enter, Escape, and its rows' letters work at once. Every way a dropdown opens comes
   * here: its trigger's click, Enter, and Space, the arrow keys on its trigger, and the
   * shell's filter numbers. Returns the row, or null when the menu is not open.
   * @param {Element} root
   * @param {string} key
   */
  function focusMenu(root, key) {
    const menu = root.querySelector(`.chip-menu[data-chip-menu="${quoted(key)}"]`);
    if (menu?.getAttribute("aria-expanded") !== "true") {
      return null;
    }
    const panel = menu.querySelector(".chip-menu-panel");
    const row = /** @type {HTMLElement | null} */ (
      panel?.querySelector('.chip-menu-item[aria-checked="true"]') ??
        panel?.querySelector(".chip-menu-item") ??
        null
    );
    row?.focus();
    return row;
  }

  /**
   * Put focus back where it belongs after a change to `root`: on the control `selector`
   * names, as rebuilt, or on its menu's trigger when it is a row of a menu now closed.
   * Focus that has moved on to a live element outside `root` is left there.
   * @param {Element} root
   * @param {string | null} selector
   */
  function settleFocus(root, selector) {
    const doc = root.ownerDocument;
    if (!selector || !doc) {
      return;
    }
    const now = doc.activeElement;
    if (now && now !== doc.body && now.isConnected !== false && !root.contains(now)) {
      return;
    }
    let target = /** @type {HTMLElement | null} */ (root.querySelector(selector));
    const menu = target?.closest(".chip-menu");
    if (
      target &&
      menu &&
      menu.getAttribute("aria-expanded") !== "true" &&
      target.closest(".chip-menu-panel")
    ) {
      target = /** @type {HTMLElement | null} */ (menu.querySelector("[data-chip-menu-toggle]"));
    }
    if (target && target !== now) {
      target.focus();
    }
  }

  /**
   * Keep focus across a rebuild of `root`'s markup: call it before the rebuild and the
   * function it returns after, and the control that had focus has it again, or its
   * menu's trigger when the rebuild closed that menu (`settleFocus`). Nothing happens
   * when focus was outside `root`.
   * @param {Element} root
   * @returns {() => void}
   */
  function keepFocus(root) {
    const active = root.ownerDocument?.activeElement;
    const selector =
      active && active !== root && root.contains(active) ? controlSelector(active) : null;
    return () => settleFocus(root, selector);
  }

  /** Each bound container's row path, so a row's letter runs what a click on it runs.
   * @type {WeakMap<Element, (row: HTMLElement) => void>} */
  const boundRows = new WeakMap();

  /**
   * Choose a dropdown row as a click on it does, through the handlers of the container
   * `bind` wired around it. The shell's keymap runs it for a row's letter
   * (docs/design-system.md, "Keys in a Menu"). Returns whether a bound container held
   * the row.
   * @param {HTMLElement} row
   */
  function activateMenuRow(row) {
    if (
      !row ||
      typeof row.matches !== "function" ||
      !row.matches(".chip-menu-item[data-chip-key]")
    ) {
      return false;
    }
    for (let node = row.parentElement; node; node = node.parentElement) {
      const pick = boundRows.get(node);
      if (pick) {
        pick(row);
        return true;
      }
    }
    return false;
  }

  /**
   * Wire one container. `onChange(key, value, select)` fires for group
   * segments, `onToggle(key, nextPressed)` for standalone chips, and
   * `onClear()` for the clear affordance, and `onMenuFocus(key, value)` when the arrow
   * keys, Home, or End move focus to a dropdown row (its value, or null for the any-row),
   * so a consumer can act on the row a reader rests on. Returns a disposer, because
   * every listener the shell installs needs a way back out.
   *
   * @param {Element} root
   * @param {{onChange?: (key: string, value: string, select: string) => void,
   *          onToggle?: (key: string, pressed: boolean) => void,
   *          onMenuToggle?: (key: string, open: boolean) => void,
   *          onMenuPick?: (key: string, value: string | null) => void,
   *          onMenuFocus?: (key: string, value: string | null) => void,
   *          onMenuPreset?: (key: string, presetId: string, wasOn: boolean) => void,
   *          onClear?: () => void}} handlers
   */
  function bind(root, handlers) {
    const opts = handlers || {};

    /** Any open dropdown, so outside clicks and Escape can close it. */
    function openMenuKey() {
      const open = root.querySelector('.chip-menu[aria-expanded="true"]');
      return open ? open.getAttribute("data-chip-menu") : null;
    }

    /**
     * Choose one dropdown row: what a click on it runs, and what its letter runs
     * (`activateMenuRow`), so a key never synthesizes the click. Focus then stays on the
     * row while its menu stays open, as a multi-select one does, and goes back to the
     * trigger when the choice closed it.
     * @param {HTMLElement} menuItem
     */
    function pickRow(menuItem) {
      const key = menuItem.getAttribute("data-chip-key") || "";
      const row = controlSelector(menuItem);
      const preset = menuItem.getAttribute("data-chip-preset");
      if (preset !== null) {
        if (opts.onMenuPreset) {
          opts.onMenuPreset(key, preset, menuItem.getAttribute("aria-checked") === "true");
        }
      } else if (opts.onMenuPick) {
        opts.onMenuPick(
          key,
          menuItem.hasAttribute("data-chip-any")
            ? null
            : menuItem.getAttribute("data-chip-value") || "",
        );
      }
      settleFocus(root, row);
    }

    /**
     * Open a dropdown from its trigger, as a click or an arrow key on it does, and focus
     * its checked row; or close it and leave focus on the trigger.
     * @param {Element} menuToggle
     * @param {boolean} open
     */
    function toggleMenu(menuToggle, open) {
      const key = menuToggle.getAttribute("data-chip-menu-toggle") || "";
      const trigger = controlSelector(menuToggle);
      if (opts.onMenuToggle) {
        opts.onMenuToggle(key, open);
      }
      // The consumer has rendered the menu open: fit it to its rows and the window.
      fitOpenMenus(root);
      if (!open || !focusMenu(root, key)) {
        settleFocus(root, trigger);
      }
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
        const wrap = menuToggle.closest(".chip-menu");
        toggleMenu(menuToggle, wrap?.getAttribute("aria-expanded") !== "true");
        return;
      }
      // A row inside the dropdown. Checked before the generic .chip
      // branch because menu rows are .menu-item, not .chip.
      const menuItem = /** @type {HTMLElement | null} */ (
        target.closest(".chip-menu-item[data-chip-key]")
      );
      if (menuItem && root.contains(menuItem)) {
        pickRow(menuItem);
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
      // A key held with Command, Control, or Option is the browser's: Command-Left and
      // Alt-Left go back, and Command-Up scrolls to the top.
      if (
        !target ||
        typeof target.closest !== "function" ||
        ev.altKey ||
        ev.ctrlKey ||
        ev.metaKey
      ) {
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
        const row = moveFocus(
          Array.prototype.slice.call(panel.querySelectorAll(".chip-menu-item")),
          target.closest(".chip-menu-item"),
          key,
        );
        if (row && opts.onMenuFocus) {
          opts.onMenuFocus(
            row.getAttribute("data-chip-key") || "",
            row.hasAttribute("data-chip-any") ? null : row.getAttribute("data-chip-value") || "",
          );
        }
        return;
      }
      // On a dropdown's trigger, Up and Down open it, as Enter and Space do through the
      // click, and focus its checked row; on an open one's, they move focus into it.
      const menuToggle = target.closest("[data-chip-menu-toggle]");
      if (menuToggle && root.contains(menuToggle) && (key === "ArrowDown" || key === "ArrowUp")) {
        ev.preventDefault();
        const menuKey = menuToggle.getAttribute("data-chip-menu-toggle") || "";
        if (!focusMenu(root, menuKey)) {
          toggleMenu(menuToggle, true);
        }
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
        const value = chip.getAttribute("data-chip-value") || "";
        opts.onChange(chip.getAttribute("data-chip-key") || "", value, "one");
        // A consumer repaints the group from its state, as the Files / Bytes and Split /
        // Unified controls do, which replaces the element holding focus. Focus stays on
        // the chosen segment, or the next arrow key has nothing to act on.
        if (chip.isConnected === false) {
          Array.prototype.slice
            .call(root.querySelectorAll(".chip[data-chip-key]"))
            .find((next) => next.getAttribute("data-chip-value") === value)
            ?.focus();
        }
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
      const ev = /** @type {KeyboardEvent} */ (event);
      if (ev.key !== "Escape" || ev.altKey || ev.ctrlKey || ev.metaKey) {
        return;
      }
      // An Escape that closed a surface above the bar, such as Quick Search or Help, is
      // that surface's: the topmost closes first (docs/design-system.md, "Shared Overlay
      // Lifecycle"), and the menu waits for the next.
      if (ev.defaultPrevented) {
        return;
      }
      const openKey = openMenuKey();
      if (openKey !== null && opts.onMenuToggle) {
        const trigger = root.querySelector(`[data-chip-menu-toggle="${quoted(openKey)}"]`);
        opts.onMenuToggle(openKey, false);
        // Back to the trigger, unless focus had already left the bar for the page.
        settleFocus(root, trigger ? controlSelector(trigger) : null);
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

    // An open dropdown's room changes with the window, so it is fitted again.
    function onWindowResize() {
      fitOpenMenus(root);
    }

    root.addEventListener("click", onClick);
    root.addEventListener("change", onChange);
    root.addEventListener("keydown", onKeyDown);
    const doc = root.ownerDocument;
    const view = doc?.defaultView;
    doc?.addEventListener("pointerdown", onDocumentPointerDown);
    doc?.addEventListener("keydown", onDocumentEscape);
    view?.addEventListener("resize", onWindowResize);
    boundRows.set(root, pickRow);
    // In a navigation toolbar, a segmented group wider than its line takes the cluster.
    const stopFitting = keepJoinedGroupsFitted(root);
    return () => {
      if (boundRows.get(root) === pickRow) {
        boundRows.delete(root);
      }
      root.removeEventListener("click", onClick);
      root.removeEventListener("change", onChange);
      root.removeEventListener("keydown", onKeyDown);
      doc?.removeEventListener("pointerdown", onDocumentPointerDown);
      doc?.removeEventListener("keydown", onDocumentEscape);
      view?.removeEventListener("resize", onWindowResize);
      stopFitting();
    };
  }

  const api = {
    activateMenuRow,
    escapeHtml: esc,
    nextSelection,
    isSelected,
    groupHtml,
    menuGroupHtml,
    menuMaxHeight,
    fitOpenMenus,
    focusMenu,
    keepFocus,
    joinedGroupFits,
    fitJoinedGroups,
    toggleHtml,
    checkHtml,
    clearHtml,
    bind,
  };
  if (!window.metabrowser) {
    console.error("metabrowser filter controls: window.metabrowser missing — SDK not loaded");
    return;
  }
  window.metabrowser.filterControls = api;
})();
