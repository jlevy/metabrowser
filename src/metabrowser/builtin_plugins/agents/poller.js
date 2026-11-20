// A poll that runs only while its page is visible, one request at a time.
//
// The agents views poll data-hook routes, since the SDK has no change subscription: the
// home's live strip polls `live`, and its summary progress polls `catalog` until the
// summary pass is complete. Both follow the same rules, kept here so one browserless
// session pins them (tests/dom/agents-views-session.js):
//
// - One request is in flight at most. A tick that finds one still running waits for the
//   next, so a slow server is never queued behind its own polls.
// - A hidden page makes no request. The poll holds its place and runs at once when the
//   page is shown again, if its interval has passed.
// - A failed tick doubles the wait, up to `MAX_BACKOFF`, and a good one resets it.
// - A tick that answers `false` ends the poll, as a summary that is complete does.
// - `dispose` ends it for good and aborts the request in flight.
//
// Time, visibility, and the timer are injected, so the browser passes its own and a
// session passes a clock it advances by hand.

/** The most times the interval is multiplied after consecutive failures. */
export const MAX_BACKOFF = 4;

/**
 * How often the live strip asks `live`. The server reuses one liveness check for
 * `LIVE_TTL_SECONDS` (catalog.py, 2 s), because a check runs a process probe per Claude
 * Code pid file, so a faster poll would only read the same answer. Twice that keeps a
 * session that starts or ends on the strip within about five seconds, a delay a person
 * watching sessions does not notice. Measured in Chrome over loopback against the 13
 * synthetic sessions (2026-11-20, load average near 10): a `live` request took 2.5 to 15 ms,
 * the first being the cold one. A real home's cost is the probe, which the server's reuse
 * bounds to one per `LIVE_TTL_SECONDS` however many pages ask.
 */
export const LIVE_POLL_MS = 5000;

/**
 * How often a page asks `catalog` or `sessions` again while the summary pass is
 * incomplete. A request that arrives while a pass is running continues it (catalog.py), and
 * the measured homes summarize in minutes to hours, so a page asks about as often as a
 * progress bar is worth redrawing, not as often as the pass advances. A `catalog` or
 * `sessions` request took 2.6 to 3.4 ms on the synthetic homes (same measurement).
 */
export const PROGRESS_POLL_MS = 3000;

/**
 * @typedef {object} PollerOptions
 * @property {(signal: AbortSignal) => Promise<boolean | void>} run One tick; `false` ends the poll.
 * @property {number} intervalMs
 * @property {() => boolean} isVisible
 * @property {(listener: () => void) => () => void} subscribeVisibility
 * @property {(callback: () => void, ms: number) => unknown} setTimer
 * @property {(handle: unknown) => void} clearTimer
 * @property {() => number} now
 * @property {(error: unknown) => void} [onError]
 */

/**
 * @typedef {object} Poller
 * @property {() => void} start Schedule the first tick one interval from now.
 * @property {() => void} stop End the poll; `start` begins it again.
 * @property {() => void} dispose
 * @property {() => {running: boolean, inFlight: boolean, failures: number, waitMs: number}} state
 */

/** @param {PollerOptions} options @returns {Poller} */
export function createPoller(options) {
  const { run, intervalMs, isVisible, subscribeVisibility, setTimer, clearTimer, now } = options;
  let running = false;
  let disposed = false;
  let failures = 0;
  /** @type {unknown} */
  let timer = null;
  /** @type {AbortController | null} */
  let flight = null;
  let dueAt = 0;
  /** @type {(() => void) | null} */
  let unsubscribe = null;

  const waitMs = () => intervalMs * Math.min(MAX_BACKOFF, 2 ** failures);

  function clear() {
    if (timer !== null) {
      clearTimer(timer);
      timer = null;
    }
  }

  function schedule() {
    clear();
    if (!running || disposed) {
      return;
    }
    dueAt = now() + waitMs();
    timer = setTimer(tick, waitMs());
  }

  async function tick() {
    timer = null;
    if (!running || disposed) {
      return;
    }
    if (!isVisible()) {
      // Held: the visibility listener runs the tick when the page is shown.
      return;
    }
    if (flight) {
      schedule();
      return;
    }
    const controller = new AbortController();
    flight = controller;
    let again = true;
    try {
      const answer = await run(controller.signal);
      failures = 0;
      again = answer !== false;
    } catch (error) {
      if (!controller.signal.aborted) {
        failures += 1;
        options.onError?.(error);
      }
    } finally {
      if (flight === controller) {
        flight = null;
      }
    }
    if (controller.signal.aborted) {
      return;
    }
    if (again) {
      schedule();
    } else {
      running = false;
    }
  }

  function onVisibility() {
    if (!running || disposed || !isVisible()) {
      return;
    }
    // Shown again: run now when the wait has passed, or let the timer finish otherwise.
    if (timer === null && !flight) {
      void tick();
    } else if (now() >= dueAt) {
      clear();
      void tick();
    }
  }

  return {
    start() {
      if (disposed || running) {
        return;
      }
      running = true;
      // The first tick is scheduled before the subscription, which may report the page's
      // state at once, as the SDK's `viewState.subscribeActive` does: a report that finds
      // no timer would run a tick now, a second request beside the one that just answered.
      schedule();
      unsubscribe ??= subscribeVisibility(onVisibility);
    },
    stop() {
      running = false;
      clear();
      flight?.abort();
      flight = null;
    },
    dispose() {
      disposed = true;
      running = false;
      clear();
      flight?.abort();
      flight = null;
      unsubscribe?.();
      unsubscribe = null;
    },
    state() {
      return { running, inFlight: flight !== null, failures, waitMs: waitMs() };
    },
  };
}

/**
 * The browser's own time, visibility, and timer for a poller.
 *
 * @returns {Pick<PollerOptions, "isVisible" | "subscribeVisibility" | "setTimer" | "clearTimer" | "now">}
 */
export function browserClock() {
  return {
    isVisible: () => document.visibilityState !== "hidden",
    subscribeVisibility(listener) {
      document.addEventListener("visibilitychange", listener);
      return () => document.removeEventListener("visibilitychange", listener);
    },
    setTimer: (callback, ms) => window.setTimeout(callback, ms),
    clearTimer: (handle) => window.clearTimeout(/** @type {number} */ (handle)),
    now: () => Date.now(),
  };
}
