// Metabrowser — the half of the probe that has to be there from the start.
//
// `probe.js` is pasted once, after the tree settles, and reports what it can
// see from the end. That is the wrong vantage point for responsiveness, for
// two reasons that both understate the problem:
//
//   * The browser's `longtask` buffer is bounded. A load bad enough to be worth
//     measuring overruns it, and the paste reports the survivors as if they
//     were the total.
//   * The worst blocking is at the START, when discovery is fastest and the
//     reader is deciding whether the app feels alive. A probe that attaches
//     after settle has already missed it.
//
// So this half attaches at navigation and observes continuously. Paste it as
// soon as the page begins loading — a devtools snippet set to run on load, or
// straight into the console on a slow tree. `probe.js` reads what it collected
// and says in its output whether it got boot data or fell back.
//
// Two things are recorded, and they answer different questions:
//
//   LONG TASKS answer "was the thread free to paint". The maximum matters more
//   than the total: sixty 100 ms hitches and one six-second freeze cost the
//   same total and are not the same product.
//
//   EVENT LATENCY answers "did the app respond when touched" — the browser's
//   own measurement of interaction to next paint, which is the thing a reader
//   actually experiences and the only one that survives a change of transport.
//   A UI decoupled from its backend keeps this flat whether the server answers
//   in 6 ms over a loopback or 600 ms over a tunnel.
(() => {
  const boot = {
    attached_at_ms: Math.round(performance.now()),
    longTasks: /** @type {{start: number, dur: number}[]} */ ([]),
    interactions: /** @type {{name: string, dur: number, start: number}[]} */ ([]),
    observers: /** @type {PerformanceObserver[]} */ ([]),
    unsupported: /** @type {string[]} */ ([]),
  };

  try {
    const tasks = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        boot.longTasks.push({
          start: Math.round(entry.startTime),
          dur: Math.round(entry.duration),
        });
      }
    });
    tasks.observe({ type: "longtask", buffered: true });
    boot.observers.push(tasks);
  } catch (_noLongTask) {
    boot.unsupported.push("longtask");
  }

  try {
    const events = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        boot.interactions.push({
          name: entry.name,
          // Interaction to next paint for this event, in the browser's own
          // accounting: input delay, handler, and the paint that follows.
          dur: Math.round(entry.duration),
          start: Math.round(entry.startTime),
        });
      }
    });
    // 16 ms is one frame. Below that an interaction cannot have missed a paint.
    events.observe({ type: "event", durationThreshold: 16, buffered: true });
    boot.observers.push(events);
  } catch (_noEventTiming) {
    boot.unsupported.push("event");
  }

  /** Percentile over a sorted-in-place copy, or null when nothing was seen. */
  const at = (/** @type {number[]} */ values, /** @type {number} */ q) => {
    if (values.length === 0) {
      return null;
    }
    const sorted = [...values].sort((a, b) => a - b);
    return sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))];
  };

  boot.summarize = () => {
    for (const observer of boot.observers) {
      const pending = observer.takeRecords();
      if (pending.length > 0) {
        // Drain rather than drop: entries delivered between the last callback
        // and this call are the ones nearest the moment of interest.
        for (const entry of pending) {
          if (entry.entryType === "longtask") {
            boot.longTasks.push({
              start: Math.round(entry.startTime),
              dur: Math.round(entry.duration),
            });
          } else {
            boot.interactions.push({
              name: entry.name,
              dur: Math.round(entry.duration),
              start: Math.round(entry.startTime),
            });
          }
        }
      }
    }
    const window_ms = Math.round(performance.now());
    const durations = boot.longTasks.map((t) => t.dur);
    const blocked = durations.reduce((total, d) => total + d, 0);
    const latencies = boot.interactions.map((i) => i.dur);
    return {
      boot_probe: true,
      boot_attached_at_ms: boot.attached_at_ms,
      // The precondition. A responsiveness number from a run that was ever
      // hidden is void, not merely noisy.
      visibility_state: document.visibilityState,
      ever_hidden: boot.ever_hidden,
      measurement_valid: !boot.ever_hidden,
      boot_unsupported: boot.unsupported.length > 0 ? boot.unsupported : null,
      long_task_window_ms: window_ms,
      long_tasks: boot.longTasks.length,
      long_task_ms_total: blocked,
      // The one a reader feels. See H58.
      long_task_max_ms: durations.reduce((worst, d) => Math.max(worst, d), 0),
      long_tasks_over_200ms: durations.filter((d) => d > 200).length,
      main_thread_blocked_pct: window_ms > 0 ? Math.round((1000 * blocked) / window_ms) / 10 : null,
      // Worst blocking inside the first five seconds, reported separately
      // because that is when the reader decides whether the app is alive and
      // when the event rate is highest.
      long_task_max_ms_first_5s: boot.longTasks
        .filter((t) => t.start < 5000)
        .reduce((worst, t) => Math.max(worst, t.dur), 0),
      interactions: boot.interactions.length,
      interaction_p50_ms: at(latencies, 0.5),
      interaction_p95_ms: at(latencies, 0.95),
      interaction_max_ms: latencies.reduce((worst, d) => Math.max(worst, d), 0),
    };
  };

  // Whether the page was EVER hidden while measuring, which is stronger than
  // asking at the end. Chromium throttles a hidden tab into manufacturing
  // multi-second tasks, so a run that was backgrounded even briefly cannot be
  // compared against one that was not, and a run that cannot say either way is
  // not evidence. See the precondition in README.md.
  boot.hidden_at_start = document.visibilityState !== "visible";
  boot.ever_hidden = boot.hidden_at_start;
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") {
      boot.ever_hidden = true;
    }
  });

  window.__mbBoot = boot;
  return { attached: true, at_ms: boot.attached_at_ms, unsupported: boot.unsupported };
})();
