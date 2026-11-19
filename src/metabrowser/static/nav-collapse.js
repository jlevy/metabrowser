// Hiding the navigation pane: the chevron at the foot of the main page's left edge, and
// `\` (docs/keyboard-shortcuts.md), close the pane and open it again.
//
// The pane does not shrink. Hidden, it leaves the layout, and the main frame, which
// already floats over it with its left shadow, slides left over it to the window's
// edge; shown, the frame slides back. The frame keeps its full width for the whole slide
// and its contents reflow once, at the end of a show or the start of a hide, so a long
// document is laid out once per toggle rather than on every frame. The slide is a
// transform on the frame, which is already transformed (`.preview-frame` in styles.css),
// so it stays the containing block of KPress's floating UI throughout.
//
// While hidden the pane is `inert`, so no key or Tab reaches a control in it, and the
// keyboard registry, which skips inert targets, leaves its keys alone: only `\` and the
// keys of the main page stay live. The state lives in the document and is not persisted.
// See docs/design-system.md, "Hiding the Navigation Pane".

/** @param {Window} global */
((global) => {
  // How long the frame takes to slide, the duration of `--motion-reveal` in styles.css,
  // the shell's motion for chrome that appears. Long enough to read as the page moving
  // over the pane, short enough that a key press feels immediate; reduced motion skips it.
  const SLIDE_MS = 180;
  const SLIDE_EASING = "cubic-bezier(0.2, 0, 0, 1)";
  const COLLAPSED_ATTRIBUTE = "data-nav-collapsed";

  /**
   * @param {{
   *   anchor?: HTMLElement | null,
   *   button: HTMLButtonElement,
   *   container: HTMLElement,
   *   document?: Document,
   *   focusFallback?: () => HTMLElement | null,
   *   frame: HTMLElement,
   *   pane: HTMLElement,
   *   reducedMotion?: () => boolean,
   * }} options
   * @returns {MetabrowserPublicNavCollapseController}
   */
  function create(options) {
    const { button, container, frame, pane } = options;
    if (!button || !container || !frame || !pane) {
      throw new TypeError("Hiding the navigation needs its button, container, frame, and pane");
    }
    const doc = options.document || global.document;
    const reducedMotion =
      options.reducedMotion ||
      (() => {
        try {
          return !!global.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
        } catch (_error) {
          return false;
        }
      });
    let collapsed = false;
    /** @type {Animation | null} */
    let slide = null;
    /** @type {(() => void) | null} */
    let settleSlide = null;
    /** @type {Set<() => void>} */
    const listeners = new Set();

    /** Write the button's name, state, and tooltip for the pane's state. */
    function renderButton() {
      const label = collapsed ? "Show navigation" : "Hide navigation";
      button.setAttribute("aria-expanded", String(!collapsed));
      button.setAttribute("aria-label", label);
      button.dataset.tipText = label;
    }

    /** The layout for a state: the pane out of the flow and inert, or back in it. */
    function applyLayout() {
      container.toggleAttribute(COLLAPSED_ATTRIBUTE, collapsed);
      pane.toggleAttribute("inert", collapsed);
    }

    /** The frame's current horizontal offset, mid-slide, or 0. */
    function currentOffset() {
      const transform = global.getComputedStyle?.(frame).transform || "none";
      if (transform === "none") {
        return 0;
      }
      try {
        return new DOMMatrixReadOnly(transform).m41;
      } catch (_error) {
        return 0;
      }
    }

    /** End a slide in progress at its end state. */
    function finishSlide() {
      const settle = settleSlide;
      settleSlide = null;
      slide?.cancel();
      slide = null;
      settle?.();
    }

    /**
     * Slide the frame from one offset to another, then settle.
     *
     * @param {number} from
     * @param {number} to
     * @param {() => void} settle
     */
    function slideFrame(from, to, settle) {
      if (typeof frame.animate !== "function" || reducedMotion() || from === to) {
        settle();
        return;
      }
      // translateZ(0) is the frame's resting transform; every keyframe keeps it.
      const animation = frame.animate(
        [
          { transform: `translate3d(${from}px, 0, 0)` },
          { transform: `translate3d(${to}px, 0, 0)` },
        ],
        {
          duration: SLIDE_MS * (Math.abs(to - from) / Math.max(1, pane.offsetWidth)),
          easing: SLIDE_EASING,
        },
      );
      slide = animation;
      settleSlide = settle;
      animation.finished.then(
        () => {
          if (slide === animation) {
            finishSlide();
          }
        },
        () => {
          // Cancelled: whoever cancelled it settled it.
        },
      );
    }

    /**
     * Hide or show the pane.
     *
     * @param {boolean} next
     */
    function setCollapsed(next) {
      if (next === collapsed) {
        return;
      }
      // A slide in progress is picked up where the frame is now, not where it was going.
      const offset = slide ? currentOffset() : null;
      if (slide) {
        settleSlide = null;
        slide.cancel();
        slide = null;
      }
      const width = pane.offsetWidth;
      collapsed = next;
      renderButton();
      if (collapsed) {
        // Focus inside the pane would be stranded in an inert subtree.
        const active = doc.activeElement;
        const focusMoves = active instanceof HTMLElement && pane.contains(active);
        applyLayout();
        if (focusMoves) {
          (options.focusFallback?.() ?? button).focus({ preventScroll: true });
        }
        // The frame now starts at the window's edge; it slides there from the pane's.
        slideFrame(offset ?? width, 0, () => {});
      } else {
        pane.removeAttribute("inert");
        // The pane is back under the frame, still out of the flow; the frame slides off
        // it and then the pane takes its place in the layout.
        slideFrame(offset ?? 0, width, applyLayout);
      }
      for (const listener of listeners) {
        listener();
      }
    }

    function toggle() {
      setCollapsed(!collapsed);
    }

    /** @param {MouseEvent} event */
    function onClick(event) {
      event.preventDefault();
      toggle();
    }

    // The button sits on the shortcut strip's row, which moves when a row below it, the
    // scan's progress or a mirror's freshness, shows or hides: centered on the strip, which
    // starts where the pane starts, as the frame does.
    /** @type {ResizeObserver | null} */
    let alignment = null;
    const anchor = options.anchor ?? null;
    if (anchor && typeof global.ResizeObserver === "function") {
      alignment = new global.ResizeObserver(() => {
        const top = anchor.offsetTop + (anchor.offsetHeight - button.offsetHeight) / 2;
        button.style.top = `${Math.round(top)}px`;
        button.style.bottom = "auto";
      });
      alignment.observe(pane);
      alignment.observe(button);
      for (
        let node = /** @type {Element | null} */ (anchor);
        node;
        node = node.nextElementSibling
      ) {
        alignment.observe(node);
      }
    }

    button.addEventListener("click", onClick);
    renderButton();

    return Object.freeze({
      button,
      isCollapsed: () => collapsed,
      setCollapsed,
      toggle,
      /** @param {() => void} listener */
      subscribe(listener) {
        listeners.add(listener);
        return () => listeners.delete(listener);
      },
      dispose() {
        finishSlide();
        alignment?.disconnect();
        button.removeEventListener("click", onClick);
        listeners.clear();
      },
    });
  }

  global.MetabrowserNavCollapse = Object.freeze({ create, SLIDE_MS });
})(window);
