/**
 * Initialize KPress's TOC with a scoped IntersectionObserver substitute when
 * the host runtime does not provide one. KPress still owns active-link state,
 * collapsible-group following, toggle behavior, and disposal; this adapter
 * supplies only the missing observation signal.
 *
 * @param {() => (() => void) | null} init
 * @param {{
 *   cancel?: (handle: number) => void,
 *   runtime?: Record<string, unknown>,
 *   schedule?: (callback: FrameRequestCallback) => number,
 *   windowTarget?: Pick<Window, "addEventListener" | "removeEventListener" | "innerHeight">,
 * }} [options]
 * @returns {() => void}
 */
export function initTocWithIntersectionFallback(init, options = {}) {
  const runtime = options.runtime ?? /** @type {Record<string, unknown>} */ (globalThis);
  if (typeof runtime.IntersectionObserver === "function") {
    return init() ?? (() => {});
  }

  const schedule = options.schedule ?? ((callback) => requestAnimationFrame(callback));
  const cancel = options.cancel ?? ((handle) => cancelAnimationFrame(handle));
  const windowTarget =
    options.windowTarget ??
    /** @type {Pick<Window, "addEventListener" | "removeEventListener" | "innerHeight">} */ (
      window
    );
  const descriptor = Object.getOwnPropertyDescriptor(runtime, "IntersectionObserver");
  const FallbackIntersectionObserver = createTocIntersectionObserver({
    cancel,
    schedule,
    windowTarget,
  });

  Object.defineProperty(runtime, "IntersectionObserver", {
    configurable: true,
    value: FallbackIntersectionObserver,
    writable: true,
  });
  try {
    return init() ?? (() => {});
  } finally {
    if (descriptor) {
      Object.defineProperty(runtime, "IntersectionObserver", descriptor);
    } else {
      delete runtime.IntersectionObserver;
    }
  }
}

/**
 * Select the section at KPress's reading line: the last heading at or above
 * the bottom of its top-quarter observation band. Keeping passed headings in
 * the candidate set makes a long section stay active until its successor
 * reaches the same line.
 *
 * KPress observes headings in document order, which is also their vertical
 * order in rendered Markdown. Binary search keeps fallback scroll work
 * logarithmic even for an unusually large TOC.
 *
 * @param {ReadonlyArray<Element>} targets
 * @param {number} readingLine
 * @returns {{rect: DOMRect, target: Element} | null}
 */
export function selectTocTargetAtReadingLine(targets, readingLine) {
  /** @type {{rect: DOMRect, target: Element} | null} */
  let selected = null;
  let low = 0;
  let high = targets.length - 1;
  while (low <= high) {
    const index = low + Math.floor((high - low) / 2);
    const target = targets[index];
    const rect = target.getBoundingClientRect();
    if (rect.top <= readingLine) {
      selected = { rect, target };
      low = index + 1;
    } else {
      high = index - 1;
    }
  }
  return selected;
}

/**
 * @param {{
 *   cancel: (handle: number) => void,
 *   schedule: (callback: FrameRequestCallback) => number,
 *   windowTarget: Pick<Window, "addEventListener" | "removeEventListener" | "innerHeight">,
 * }} dependencies
 */
function createTocIntersectionObserver({ cancel, schedule, windowTarget }) {
  return class TocIntersectionObserverFallback {
    /**
     * @param {IntersectionObserverCallback} callback
     * @param {IntersectionObserverInit} [observerOptions]
     */
    constructor(callback, observerOptions = {}) {
      this.root = observerOptions.root ?? null;
      this.rootMargin = observerOptions.rootMargin ?? "0px";
      this.thresholds = normalizeThresholds(observerOptions.threshold);
      this.scrollMargin = "0px";
      this.callback = callback;
      /** @type {Element[]} */
      this.targets = [];
      /** @type {Element | null} */
      this.activeTarget = null;
      this.scheduledFrame = 0;
      this.scrollTarget = isListenerTarget(this.root) ? this.root : windowTarget;
      this.scheduleUpdate = () => {
        if (this.scheduledFrame) {
          return;
        }
        this.scheduledFrame = schedule(() => {
          this.scheduledFrame = 0;
          this.update();
        });
      };
      this.scrollTarget.addEventListener("scroll", this.scheduleUpdate, { passive: true });
      windowTarget.addEventListener("resize", this.scheduleUpdate, { passive: true });
    }

    /** @param {Element} target */
    observe(target) {
      if (!this.targets.includes(target)) {
        this.targets.push(target);
        this.scheduleUpdate();
      }
    }

    /** @param {Element} target */
    unobserve(target) {
      const index = this.targets.indexOf(target);
      if (index >= 0) {
        this.targets.splice(index, 1);
      }
      if (this.activeTarget === target) {
        this.activeTarget = null;
        this.scheduleUpdate();
      }
    }

    disconnect() {
      this.scrollTarget.removeEventListener("scroll", this.scheduleUpdate);
      windowTarget.removeEventListener("resize", this.scheduleUpdate);
      if (this.scheduledFrame) {
        cancel(this.scheduledFrame);
        this.scheduledFrame = 0;
      }
      this.targets.length = 0;
      this.activeTarget = null;
    }

    /** @returns {IntersectionObserverEntry[]} */
    takeRecords() {
      return [];
    }

    update() {
      const bounds = observerBounds(this.root, windowTarget);
      const selected = selectTocTargetAtReadingLine(
        this.targets,
        observerReadingLine(bounds, this.rootMargin),
      );
      if (!selected || selected.target === this.activeTarget) {
        return;
      }
      this.activeTarget = selected.target;
      const entry = /** @type {IntersectionObserverEntry} */ (
        /** @type {unknown} */ ({
          boundingClientRect: selected.rect,
          intersectionRatio: 1,
          intersectionRect: selected.rect,
          isIntersecting: true,
          rootBounds: bounds.rect,
          target: selected.target,
          time: typeof performance === "undefined" ? 0 : performance.now(),
        })
      );
      this.callback([entry], /** @type {IntersectionObserver} */ (/** @type {unknown} */ (this)));
    }
  };
}

/** @param {number | number[] | undefined} threshold */
function normalizeThresholds(threshold) {
  if (Array.isArray(threshold)) {
    return [...threshold].sort((left, right) => left - right);
  }
  return [typeof threshold === "number" ? threshold : 0];
}

/**
 * Resolve the bottom edge of the observer's effective root. KPress declares
 * `0px 0px -75% 0px`, so this produces its top-quarter reading band without a
 * second hard-coded threshold that could drift from the production config.
 *
 * @param {{height: number, top: number}} bounds
 * @param {string} rootMargin
 */
function observerReadingLine(bounds, rootMargin) {
  const tokens = rootMargin.trim().split(/\s+/);
  const bottom = tokens.length < 3 ? tokens[0] : tokens[2];
  const value = Number.parseFloat(bottom || "0");
  const margin = Number.isFinite(value)
    ? bottom?.endsWith("%")
      ? bounds.height * (value / 100)
      : bottom?.endsWith("px")
        ? value
        : 0
    : 0;
  return bounds.top + bounds.height + margin;
}

/**
 * @param {unknown} value
 * @returns {value is Pick<EventTarget, "addEventListener" | "removeEventListener">}
 */
function isListenerTarget(value) {
  return Boolean(
    value &&
      typeof (/** @type {{addEventListener?: unknown}} */ (value).addEventListener) ===
        "function" &&
      typeof (/** @type {{removeEventListener?: unknown}} */ (value).removeEventListener) ===
        "function",
  );
}

/**
 * Avoid an `instanceof Element` realm check: a host can render KPress content
 * from another same-origin realm, and its observer root remains a valid
 * element even though it has a different constructor.
 *
 * @param {unknown} value
 * @returns {value is Element}
 */
function isElementRoot(value) {
  const candidate = /** @type {{clientHeight?: unknown, getBoundingClientRect?: unknown}} */ (
    value
  );
  return (
    typeof candidate?.clientHeight === "number" &&
    typeof candidate.getBoundingClientRect === "function"
  );
}

/**
 * @param {Element | Document | null} root
 * @param {Pick<Window, "innerHeight">} windowTarget
 */
function observerBounds(root, windowTarget) {
  if (isElementRoot(root)) {
    const rect = root.getBoundingClientRect();
    return {
      height: rect.height || root.clientHeight,
      rect,
      top: rect.top,
    };
  }
  const height = windowTarget.innerHeight || document.documentElement.clientHeight;
  const rect = /** @type {DOMRect} */ (
    /** @type {unknown} */ ({
      bottom: height,
      height,
      left: 0,
      right: document.documentElement.clientWidth,
      top: 0,
      width: document.documentElement.clientWidth,
      x: 0,
      y: 0,
    })
  );
  return { height, rect, top: 0 };
}
