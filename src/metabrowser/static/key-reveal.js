// The Shift key reveal: hold Shift alone and every live shortcut target shows its key.
//
// A pure state machine over injected time and visibility, fed by the registry's key
// observer and by passive pointer, focus, and visibility listeners. It drives
// presentation only: it sets `data-key-reveal` on the root and tells the registry to
// show or hide the badges. Dispatch stays in the registry; this module adds no
// `keydown` listener and calls no `preventDefault()`, so Shift+click, Shift+wheel,
// Shift selection, and every Shift chord keep their browser meaning.
// See docs/design-system.md, "Keyboard Commands and Help".

(() => {
  // How long Shift must be held alone before the badges show. PROVISIONAL, not yet
  // measured: about 200 ms is the plan's working assumption. It must sit just above
  // the Shift-to-next-key gap of typed `?`, capitals, and Shift+Arrow in Chrome and
  // Safari, so those chords never flash badges. What remains to measure, by a person
  // at a keyboard: that gap for each chord in both browsers, then the smallest value
  // above all of them (docs/qa-v012-repository-library.md, the reveal check).
  const REVEAL_HOLD_MS = 200;
  // How far the pointer may travel while Shift is armed before it cancels, so a hand
  // carrying the pointer to a Shift+click never reveals. PROVISIONAL, not yet measured:
  // about 4 px is the working assumption. What remains to measure: the jitter of a
  // resting hand on a mouse and on a trackpad, and a value just above it (the same
  // runbook check).
  const REVEAL_POINTER_SLOP_PX = 4;

  const IDLE = "idle";
  const ARMED = "armed";
  const REVEALED = "revealed";
  const ROOT_ATTRIBUTE = "data-key-reveal";

  /** @typedef {"armed" | "idle" | "revealed"} RevealState */

  /**
   * @param {{
   *   shortcuts: MetabrowserPublicShortcutRegistry,
   *   document?: Document,
   *   window?: Window,
   *   root?: HTMLElement,
   *   schedule?: (callback: () => void, delayMs: number) => unknown,
   *   cancel?: (handle: unknown) => void,
   *   visibility?: () => DocumentVisibilityState,
   *   holdMs?: number,
   *   slopPx?: number,
   * }} options
   */
  function createKeyReveal(options) {
    if (!options?.shortcuts) {
      throw new TypeError("The key reveal requires a shortcut registry");
    }
    const shortcuts = options.shortcuts;
    const hostDocument = options.document || window.document;
    const hostWindow = options.window || hostDocument.defaultView || window;
    const root = options.root || hostDocument.documentElement;
    const schedule =
      options.schedule ||
      ((/** @type {() => void} */ callback, /** @type {number} */ delayMs) =>
        hostWindow.setTimeout(callback, delayMs));
    const cancel =
      options.cancel ||
      ((/** @type {unknown} */ handle) => hostWindow.clearTimeout(/** @type {number} */ (handle)));
    const visibility = options.visibility || (() => hostDocument.visibilityState);
    const holdMs = options.holdMs ?? REVEAL_HOLD_MS;
    const slopPx = options.slopPx ?? REVEAL_POINTER_SLOP_PX;
    const isEditable = window.MetabrowserKeyboardShortcuts.isEditableTarget;

    /** @type {RevealState} */
    let state = IDLE;
    /** @type {unknown} */
    let timer = null;
    /** Where the pointer was last seen, and where it was when Shift armed.
     * @type {{x: number, y: number} | null} */
    let pointer = null;
    /** @type {{x: number, y: number} | null} */
    let origin = null;
    let pointerPressed = false;
    let disposed = false;

    function clearTimer() {
      if (timer !== null) {
        cancel(timer);
        timer = null;
      }
    }

    /** Back to rest: no timer, no attribute, no badges. */
    function idle() {
      clearTimer();
      origin = null;
      if (state === REVEALED) {
        root.removeAttribute(ROOT_ATTRIBUTE);
        shortcuts.setRevealed(false);
      }
      state = IDLE;
    }

    function reveal() {
      timer = null;
      if (state !== ARMED || disposed) {
        return;
      }
      state = REVEALED;
      root.setAttribute(ROOT_ATTRIBUTE, "");
      shortcuts.setRevealed(true);
    }

    /** @param {KeyboardEvent} event */
    function withChord(event) {
      return event.ctrlKey || event.altKey || event.metaKey;
    }

    /**
     * Every key, from the registry's observer once its dispatch has decided it:
     * keydowns with whether a handler acted, and keyups as unhandled.
     *
     * @param {KeyboardEvent} event
     * @param {boolean} handled
     */
    function observeKey(event, handled) {
      if (disposed) {
        return;
      }
      const shift = event.key === "Shift";
      if (state !== IDLE && !event.shiftKey && !(shift && event.type === "keydown")) {
        // A key event without Shift while Shift is thought held: its keyup was lost,
        // as when the window lost focus with Shift down.
        idle();
        return;
      }
      if (event.type === "keyup") {
        if (shift) {
          idle();
        }
        return;
      }
      if (shift) {
        if (
          state === IDLE &&
          !event.repeat &&
          !withChord(event) &&
          !event.isComposing &&
          !pointerPressed &&
          !isEditable(event.target)
        ) {
          state = ARMED;
          origin = pointer;
          timer = schedule(reveal, holdMs);
        }
        // A repeated Shift while held is ignored, armed or revealed.
        return;
      }
      if (state === ARMED || withChord(event) || !handled) {
        // Within the threshold any other key is a chord, such as `?` or a capital; while
        // revealed, a key no registry command took, or a modifier, ends the reveal.
        idle();
        return;
      }
      if (state === REVEALED && !event.repeat) {
        // The handler has returned: read every target again, since it can show or hide
        // one through a style change nothing publishes. A repeat does no reveal work.
        shortcuts.refreshBadges();
      }
    }

    /** @param {PointerEvent} event */
    function onPointerMove(event) {
      pointer = { x: event.clientX, y: event.clientY };
      if (state !== ARMED) {
        return;
      }
      if (origin === null) {
        origin = pointer;
      } else if (Math.hypot(pointer.x - origin.x, pointer.y - origin.y) > slopPx) {
        idle();
      }
    }

    /** @param {PointerEvent} event */
    function onPointerDown(event) {
      pointer = { x: event.clientX, y: event.clientY };
      pointerPressed = true;
      // A Shift+click keeps its browser meaning; the reveal only gets out of its way.
      idle();
    }

    function onPointerUp() {
      pointerPressed = false;
    }

    function onWheel() {
      // Shift+wheel is the browser's sideways scroll, which a Split diff relies on.
      idle();
    }

    /** @param {FocusEvent} event */
    function onFocusIn(event) {
      if (state !== IDLE && isEditable(event.target)) {
        idle();
      }
    }

    /**
     * The window itself losing focus, never an element inside it: a key or a press that
     * moves focus keeps the reveal and the press it is part of. This listener is not a
     * capture listener, since one on the window hears every element's `blur` too.
     *
     * @param {FocusEvent} event
     */
    function onBlur(event) {
      if (event.target !== hostWindow) {
        return;
      }
      pointerPressed = false;
      idle();
    }

    function onVisibilityChange() {
      if (visibility() === "hidden") {
        pointerPressed = false;
        idle();
      }
    }

    const passive = { capture: true, passive: true };
    hostDocument.addEventListener("pointermove", onPointerMove, passive);
    hostDocument.addEventListener("pointerdown", onPointerDown, passive);
    hostDocument.addEventListener("pointerup", onPointerUp, passive);
    hostDocument.addEventListener("pointercancel", onPointerUp, passive);
    hostDocument.addEventListener("wheel", onWheel, passive);
    hostDocument.addEventListener("focusin", onFocusIn, passive);
    hostDocument.addEventListener("visibilitychange", onVisibilityChange, passive);
    hostWindow.addEventListener("blur", onBlur, { passive: true });
    const stopObserving = shortcuts.observeKeys(observeKey);

    function dispose() {
      if (disposed) {
        return;
      }
      idle();
      disposed = true;
      stopObserving();
      hostDocument.removeEventListener("pointermove", onPointerMove, true);
      hostDocument.removeEventListener("pointerdown", onPointerDown, true);
      hostDocument.removeEventListener("pointerup", onPointerUp, true);
      hostDocument.removeEventListener("pointercancel", onPointerUp, true);
      hostDocument.removeEventListener("wheel", onWheel, true);
      hostDocument.removeEventListener("focusin", onFocusIn, true);
      hostDocument.removeEventListener("visibilitychange", onVisibilityChange, true);
      hostWindow.removeEventListener("blur", onBlur);
    }

    return Object.freeze({
      dispose,
      /** The machine's state, for the browserless session. */
      snapshot: () => Object.freeze({ armed: timer !== null, state }),
    });
  }

  window.MetabrowserKeyReveal = Object.freeze({
    REVEAL_HOLD_MS,
    REVEAL_POINTER_SLOP_PX,
    createKeyReveal,
  });
})();
