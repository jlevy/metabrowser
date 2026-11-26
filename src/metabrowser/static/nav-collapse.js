// Hiding the navigation pane: the chevron on the shortcut strip's row at the main page's
// foot, and `\` (docs/keyboard-shortcuts.md), close the pane and open it again. app.js
// (`alignNavCollapseButton`) and the stylesheet (`.nav-collapse-toggle`) place the
// chevron, so nothing here measures it.
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
//
// With the pane out of the layout the stylesheet centers a reading column in the frame,
// by `--reading-inset` (styles.css), which is 0 whenever the pane is in it. The layout
// change that moves the column is the toggle's one reflow, at the start of a hide or the
// end of a show, so the content that starts at the inset (`GLIDING_CONTENT`) glides by
// the inset's change over the slide's own time, as a transform: from where it was drawn
// as a hide starts, and toward where it will be as a show ends, so it only ever moves
// toward the frame's start inside the frame and widens nothing.
// See docs/design-system.md, "Hiding the Navigation Pane".

/** @param {Window} global */
((global) => {
  // The slide's timing is `--motion-reveal` in styles.css, the shell's motion for chrome
  // that appears, read from the stylesheet when a slide starts: a duration, then an easing.
  const MOTION_TOKEN = "--motion-reveal";
  const COLLAPSED_ATTRIBUTE = "data-nav-collapsed";
  // The centered column's offset, a registered length, so it reads back in pixels.
  const INSET_TOKEN = "--reading-inset";
  // An inset that changed less than half a pixel is the same place (layout rounds to a 64th).
  const MOVE_TOLERANCE_PX = 0.5;
  // What the column's centering moves: the boxes that start at the header's rows', the tab
  // bar's, and the body's inset. The rows themselves span the frame, and the eyebrow's copy
  // button and the header's corner keep to its end. A staged view, drawn over the main one
  // until it replaces it, is not a child of these and is left alone.
  const GLIDING_CONTENT = [
    "#preview-pane > .view-header > .view-header-eyebrow > :not(.file-header-copy)",
    "#preview-pane > .view-header > .view-header-heading > *",
    "#preview-pane > .tab-bar > *",
    "#preview-pane > .content-body > *",
  ].join(", ");

  /**
   * The x offset a computed `transform` moves by: `matrix(a, b, c, d, e, f)`'s `e`, or
   * `matrix3d(...)`'s thirteenth value; 0 for `none` or anything else.
   *
   * @param {string} transform
   */
  function translationX(transform) {
    const match = /^matrix(3d)?\((.+)\)$/.exec(transform.trim());
    if (!match) {
      return 0;
    }
    const value = Number.parseFloat(match[2].split(",")[match[1] ? 12 : 4] ?? "");
    return Number.isFinite(value) ? value : 0;
  }

  /**
   * A token's `<duration> <easing>`, as `{ duration, easing }` in milliseconds, or null.
   *
   * @param {string} value
   */
  function parseMotion(value) {
    const match = /^(\d+(?:\.\d+)?)(ms|s)\s+(.+)$/.exec(value.trim());
    if (!match) {
      return null;
    }
    const duration = Number.parseFloat(match[1]) * (match[2] === "s" ? 1000 : 1);
    return { duration, easing: match[3] };
  }

  /**
   * @param {{
   *   button: HTMLButtonElement,
   *   container: HTMLElement,
   *   document?: Document,
   *   focusFallback?: () => HTMLElement | null,
   *   frame: HTMLElement,
   *   onHide?: () => void,
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
    // The registry reads styles through the document's own window too.
    const view = doc.defaultView || global;
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
    /** The content's glides of the slide in progress. @type {Animation[]} */
    let glides = [];
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

    /**
     * Each box the centering moves in the frame, with the inset its layout has and the
     * inset it is drawn at, a glide in progress included, so a toggle that turns one back
     * picks it up where it is.
     *
     * @returns {Map<Element, { laid: number, drawn: number }>}
     */
    function contentInsets() {
      /** @type {Map<Element, { laid: number, drawn: number }>} */
      const insets = new Map();
      if (typeof view.getComputedStyle !== "function") {
        return insets;
      }
      for (const box of frame.querySelectorAll(GLIDING_CONTENT)) {
        const style = view.getComputedStyle(box);
        const laid = Number.parseFloat(style.getPropertyValue(INSET_TOKEN)) || 0;
        insets.set(box, { laid, drawn: laid + translationX(style.transform || "none") });
      }
      return insets;
    }

    /** Stop the content's glides, each at its end, where layout already has it. */
    function stopGlides() {
      for (const glide of glides) {
        glide.cancel();
      }
      glides = [];
    }

    /** The frame's current horizontal offset, mid-slide, or 0. */
    function currentOffset() {
      return translationX(view.getComputedStyle?.(frame).transform || "none");
    }

    /** The slide's duration and easing, from the motion token, or null without one. */
    function motion() {
      const root = doc.documentElement;
      return root
        ? parseMotion(view.getComputedStyle?.(root).getPropertyValue?.(MOTION_TOKEN) ?? "")
        : null;
    }

    /** End a slide in progress at its end state, the content's glides with it. */
    function finishSlide() {
      const settle = settleSlide;
      settleSlide = null;
      slide?.cancel();
      slide = null;
      stopGlides();
      settle?.();
    }

    /**
     * Glide each content box from the inset it was drawn at (`before`) to the one it ends
     * at, `0` for a show, which ends with the pane back in the layout; the layout's inset
     * now is where a transform of 0 draws it. A show's glide holds its end until the slide
     * settles, which ends the glides as it applies the layout.
     *
     * @param {Map<Element, { laid: number, drawn: number }>} before
     * @param {{ duration: number, easing: string }} timing
     */
    function glideContent(before, timing) {
      for (const [box, now] of contentInsets()) {
        const from = (before.get(box)?.drawn ?? now.laid) - now.laid;
        const to = (collapsed ? now.laid : 0) - now.laid;
        if (
          (Math.abs(from) < MOVE_TOLERANCE_PX && Math.abs(to) < MOVE_TOLERANCE_PX) ||
          typeof box.animate !== "function"
        ) {
          continue;
        }
        glides.push(
          box.animate(
            [
              { transform: `translate3d(${from}px, 0, 0)` },
              { transform: `translate3d(${to}px, 0, 0)` },
            ],
            { ...timing, fill: collapsed ? "none" : "forwards" },
          ),
        );
      }
    }

    /**
     * Slide the frame from one offset to another, with the content the layout change moved
     * gliding from where it was drawn (`before`), then settle.
     *
     * @param {number} from
     * @param {number} to
     * @param {() => void} settle
     * @param {Map<Element, { laid: number, drawn: number }>} before
     */
    function slideFrame(from, to, settle, before) {
      const motionTiming =
        typeof frame.animate === "function" && !reducedMotion() ? motion() : null;
      if (motionTiming === null || from === to) {
        settle();
        return;
      }
      const timing = {
        // A slide picked up mid-way takes the share of the time its distance is.
        duration: motionTiming.duration * (Math.abs(to - from) / Math.max(1, pane.offsetWidth)),
        easing: motionTiming.easing,
      };
      // translateZ(0) is the frame's resting transform; every keyframe keeps it.
      const animation = frame.animate(
        [
          { transform: `translate3d(${from}px, 0, 0)` },
          { transform: `translate3d(${to}px, 0, 0)` },
        ],
        timing,
      );
      slide = animation;
      settleSlide = settle;
      glideContent(before, timing);
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
      // A slide in progress is picked up where the frame is now, not where it was going,
      // and its content where it is drawn now.
      const offset = slide ? currentOffset() : null;
      const before = contentInsets();
      if (slide) {
        settleSlide = null;
        slide.cancel();
        slide = null;
      }
      stopGlides();
      const width = pane.offsetWidth;
      collapsed = next;
      renderButton();
      if (collapsed) {
        // A menu the pane opened, a filter's or the branch chooser, would stay open under
        // the frame with its trigger inert, so the shell closes it first.
        options.onHide?.();
        // Focus inside the pane would be stranded in an inert subtree.
        const active = doc.activeElement;
        const focusMoves = active instanceof HTMLElement && pane.contains(active);
        applyLayout();
        if (focusMoves) {
          (options.focusFallback?.() ?? button).focus({ preventScroll: true });
        }
        // The frame now starts at the window's edge; it slides there from the pane's.
        slideFrame(offset ?? width, 0, () => {}, before);
      } else {
        pane.removeAttribute("inert");
        // The pane is back under the frame, still out of the flow; the frame slides off
        // it and then the pane takes its place in the layout.
        slideFrame(offset ?? 0, width, applyLayout, before);
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
        button.removeEventListener("click", onClick);
        listeners.clear();
      },
    });
  }

  global.MetabrowserNavCollapse = Object.freeze({ create });
})(window);
