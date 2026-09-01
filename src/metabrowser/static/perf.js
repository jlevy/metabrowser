// Web performance profiler — Metabrowser integration
//
// Lightweight, opt-in profiler. Records User Timing API marks/measures
// around every interesting fetch + render path so a user (or the bench
// harness) can produce a "what's actually slow on the client?" report
// without devtools open.
//
// The recorder itself has no Metabrowser DOM assumptions. App code contributes
// named spans and metadata through measure()/measureAsync(), while the runtime
// owns browser-standard loading, responsiveness, and attribution signals. The
// application publishes the recorder as `window.metabrowser.perf`.
//
// Activation:
//   * Sessions automatically record samples in a small ring buffer.
//   * Open devtools and run `metabrowser.perf.report()` to see a table.
//   * `metabrowser.perf.copy()` puts a JSON dump on the clipboard.
//   * `metabrowser.perf.download()` saves the JSON as a file.
//
// The instrumentation hooks `window.fetch` once for HTTP timings and
// exposes `metabrowser.perf.measure(label, fn, meta)` for ad-hoc spans inside
// existing render code. The production shell loads this recorder eagerly,
// before `app.js` and the other measured consumers.

(() => {
  if (typeof window === "undefined") {
    return;
  }
  if (!window.metabrowser || typeof window.metabrowser !== "object") {
    throw new Error("performance recorder requires window.metabrowser");
  }

  var MAX_SAMPLES = 500;
  var MAX_LABELS = 200;
  // The committed browser ledger peaks at 144 entries on its 241k- and
  // 300k-file runs. Five hundred leaves more than 3x measured headroom without
  // granting an endurance run unbounded storage; overflow remains invalid.
  var RESOURCE_TIMING_CAPACITY = 500;
  var WORST_FRAME_SAMPLES = 10;
  var DEFAULT_SLOW_THRESHOLD_MS = 2000;
  var fetchSamples = [];
  var measureSamples = [];
  var fetchCount = 0;
  var fetchesInFlight = 0;
  var fetchesInFlightMax = 0;
  var fetchesInFlightByKey = {};
  var fetchesInFlightMaxByKey = {};
  var fetchConcurrencyKeyOverflowed = 0;
  var fetchAbortCount = 0;
  var fetchHttp4xxCount = 0;
  var fetchHttp5xxCount = 0;
  var fetchNetworkErrorCount = 0;
  var measureCount = 0;
  var slowThresholdMs = DEFAULT_SLOW_THRESHOLD_MS;
  var resourceTimingBufferFull = null;
  var resourceTimingCapacity = null;

  // Resource Timing's browser-owned buffer is finite and silently stops
  // representing the whole navigation once full. Give progressive-load runs
  // useful headroom, but keep the limit explicit and invalidate network totals
  // if even that capacity is exceeded.
  try {
    if (typeof performance?.setResourceTimingBufferSize === "function") {
      performance.setResourceTimingBufferSize(RESOURCE_TIMING_CAPACITY);
      resourceTimingCapacity = RESOURCE_TIMING_CAPACITY;
      resourceTimingBufferFull = 0;
      var noteResourceTimingOverflow = () => {
        resourceTimingBufferFull = Number(resourceTimingBufferFull || 0) + 1;
      };
      if (typeof performance.addEventListener === "function") {
        performance.addEventListener("resourcetimingbufferfull", noteResourceTimingOverflow);
      } else {
        /** @type {any} */ (performance).onresourcetimingbufferfull = noteResourceTimingOverflow;
      }
    }
  } catch (_resourceTimingUnsupported) {
    resourceTimingBufferFull = null;
    resourceTimingCapacity = null;
  }

  // Per-label running totals that are NEVER evicted.
  //
  // The sample buffers above are ring buffers keeping the most recent
  // MAX_SAMPLES, which is right for inspecting detail and wrong for attributing
  // a load: the worst blocking is at the start, when the event rate is highest,
  // and a busy load pushes exactly those spans out before anyone looks. These
  // totals are bounded by MAX_LABELS rather than by time, so the first second
  // survives however long the session runs. Dynamic overflow collapses into
  // one named row and invalidates attribution through `labels_overflowed`.
  //
  // `max_ms` is the field to read. A total cannot tell sixty 100 ms hitches
  // from one six-second freeze, and only one of those is a broken experience.
  var labelTotals = {};
  var labelOverflowed = 0;

  function _tally(label, durationMs, finishedAtMs, meta) {
    var tallyLabel = String(label || "(unlabelled)");
    var row = labelTotals[tallyLabel];
    if (!row && Object.keys(labelTotals).length >= MAX_LABELS - 1) {
      tallyLabel = "(other labels)";
      row = labelTotals[tallyLabel];
      labelOverflowed += 1;
    }
    if (!row) {
      row = {
        label: tallyLabel,
        count: 0,
        total_ms: 0,
        max_ms: 0,
        over_200ms: 0,
        first_ts: finishedAtMs,
        first_duration_ms: durationMs,
        work_items_total: 0,
        work_items_max: 0,
        work_items_measured: false,
      };
      labelTotals[tallyLabel] = row;
    }
    row.count += 1;
    row.total_ms += durationMs;
    if (durationMs > row.max_ms) {
      row.max_ms = durationMs;
    }
    if (durationMs > 200) {
      row.over_200ms += 1;
    }
    var workItems = Number(meta?.work_items);
    if (Number.isFinite(workItems) && workItems >= 0) {
      row.work_items_measured = true;
      row.work_items_total += workItems;
      row.work_items_max = Math.max(row.work_items_max, workItems);
    }
  }

  function _now() {
    return typeof performance !== "undefined" && performance.now ? performance.now() : Date.now();
  }

  function _push(buf, sample) {
    buf.push(sample);
    if (buf.length > MAX_SAMPLES) {
      buf.shift();
    }
  }

  function _meta(meta) {
    if (meta == null) {
      return undefined;
    }
    try {
      return JSON.parse(JSON.stringify(meta));
    } catch (_e) {
      return { value: String(meta) };
    }
  }

  function _sample(base, meta) {
    var out = base;
    var safeMeta = _meta(meta);
    if (safeMeta !== undefined) {
      out.meta = safeMeta;
    }
    return out;
  }

  function _warnSlow(kind, sample) {
    if (!slowThresholdMs || sample.duration_ms < slowThresholdMs) {
      return;
    }
    if (typeof console !== "undefined" && console.warn) {
      // For fetch samples carrying a server-self-reported duration
      // (Server-Timing: srv;dur=…), make the breakdown explicit on the
      // console line so the operator sees server vs transit at a
      // glance instead of squinting at the sample object. Pure
      // diagnostic — `sample` is still passed as the second arg so
      // every detail remains inspectable.
      var headline = `[metabrowser perf] slow ${kind} (${sample.duration_ms.toFixed(0)} ms)`;
      if (kind === "fetch" && typeof sample.server_ms === "number") {
        var transit = Math.max(0, sample.duration_ms - sample.server_ms);
        headline += ` server=${sample.server_ms.toFixed(0)}ms transit=${transit.toFixed(0)}ms`;
      }
      headline += ` details=${JSON.stringify({
        label: sample.label || null,
        url: sample.url || null,
        size_bytes: sample.size_bytes ?? null,
        meta: sample.meta || null,
      })}`;
      console.warn(headline, sample);
    }
  }

  // Parse a Server-Timing header value. Returns the numeric `dur` of
  // the first metric named `srv`, or null if absent / unparsable.
  // Format is RFC-defined: ``<name>;dur=<ms>[;desc="…"], <name2>;…``.
  function _parseServerTiming(raw) {
    if (!raw || typeof raw !== "string") {
      return null;
    }
    var entries = raw.split(",");
    for (var i = 0; i < entries.length; i++) {
      var parts = entries[i].split(";");
      if (!parts.length) {
        continue;
      }
      var name = (parts[0] || "").trim();
      if (name !== "srv") {
        continue;
      }
      for (var j = 1; j < parts.length; j++) {
        var kv = parts[j].split("=");
        if (kv.length === 2 && kv[0].trim() === "dur") {
          var n = parseFloat(kv[1]);
          if (Number.isFinite(n)) {
            return n;
          }
        }
      }
    }
    return null;
  }

  function _record(buf, kind, sample) {
    _push(buf, sample);
    _warnSlow(kind, sample);
  }

  function _recordMeasure(sample) {
    measureCount += 1;
    _tally(sample.label, sample.duration_ms, sample.ts, sample.meta);
    _record(measureSamples, "span", sample);
  }

  function _fetchConcurrencyKey(rawUrl) {
    try {
      var parsed = new URL(rawUrl, "http://localhost");
      if (parsed.pathname === "/api/plugin/diff/comparison" && parsed.searchParams.has("file")) {
        return `${parsed.pathname}?file`;
      }
      return parsed.pathname;
    } catch (_error) {
      return urlKey(rawUrl);
    }
  }

  function _startFetch(concurrencyKey) {
    if (
      !(concurrencyKey in fetchesInFlightMaxByKey) &&
      Object.keys(fetchesInFlightMaxByKey).length >= MAX_LABELS - 1
    ) {
      concurrencyKey = "(other request classes)";
      fetchConcurrencyKeyOverflowed += 1;
    }
    fetchesInFlight += 1;
    fetchesInFlightMax = Math.max(fetchesInFlightMax, fetchesInFlight);
    var activeForKey = Number(fetchesInFlightByKey[concurrencyKey] || 0) + 1;
    fetchesInFlightByKey[concurrencyKey] = activeForKey;
    fetchesInFlightMaxByKey[concurrencyKey] = Math.max(
      Number(fetchesInFlightMaxByKey[concurrencyKey] || 0),
      activeForKey,
    );
    return concurrencyKey;
  }

  function _finishFetch(concurrencyKey) {
    fetchesInFlight -= 1;
    var activeForKey = Number(fetchesInFlightByKey[concurrencyKey] || 0) - 1;
    if (activeForKey > 0) {
      fetchesInFlightByKey[concurrencyKey] = activeForKey;
    } else {
      delete fetchesInFlightByKey[concurrencyKey];
    }
  }

  // Wrap the global fetch so every request gets a timing sample. The
  // wrapper preserves the original return contract — callers see the
  // same Promise<Response> shape — so existing call sites need no
  // change.
  var origFetch = window.fetch ? window.fetch.bind(window) : null;
  if (origFetch) {
    const fetchImpl = origFetch;
    window.fetch = (input, init) => {
      var t0 = _now();
      var url =
        typeof input === "string"
          ? input
          : input instanceof Request
            ? input.url
            : input instanceof URL
              ? input.href
              : "";
      var concurrencyKey = _startFetch(_fetchConcurrencyKey(url));
      var p;
      try {
        p = fetchImpl(input, init);
      } catch (error) {
        _finishFetch(concurrencyKey);
        throw error;
      }
      p.then(
        (resp) => {
          _finishFetch(concurrencyKey);
          var t1 = _now();
          var status = resp?.status;
          // Sample size from Content-Length when we can; otherwise -1.
          var size = -1;
          var serverMs = null;
          try {
            var cl = resp.headers?.get?.("content-length");
            if (cl) {
              size = parseInt(cl, 10);
            }
            // Server-Timing: srv;dur=<ms> — the server-self-reported
            // duration from middleware entry to response.start, set in
            // metabrowser.server._SlowRequestLogMiddleware. Absent for
            // long-poll endpoints (SSE / events) which are skipped by
            // the middleware; null in that case.
            var st = resp.headers?.get?.("server-timing");
            if (st) {
              serverMs = _parseServerTiming(st);
            }
          } catch (_e) {
            /* ignore */
          }
          fetchCount += 1;
          if (typeof status === "number" && status >= 500) {
            fetchHttp5xxCount += 1;
          } else if (typeof status === "number" && status >= 400) {
            fetchHttp4xxCount += 1;
          }
          _record(fetchSamples, "fetch", {
            ts: Date.now(),
            url: url,
            status: status,
            duration_ms: t1 - t0,
            size_bytes: size,
            server_ms: serverMs,
          });
        },
        (error) => {
          _finishFetch(concurrencyKey);
          var t1 = _now();
          fetchCount += 1;
          var aborted = error?.name === "AbortError";
          if (aborted) {
            fetchAbortCount += 1;
          } else {
            fetchNetworkErrorCount += 1;
          }
          _record(fetchSamples, "fetch", {
            ts: Date.now(),
            url: url,
            status: 0,
            duration_ms: t1 - t0,
            size_bytes: -1,
            error: true,
            aborted: aborted || undefined,
            error_name: error?.name || null,
          });
        },
      );
      return p;
    };
  }

  // Synchronous span helper. Use to wrap render work that isn't a
  // fetch — e.g. building the tree HTML, parsing log events, mounting
  // chart instances. Falls through invisibly if perf.js isn't loaded.
  function measure(label, fn, meta) {
    var t0 = _now();
    var threw = false;
    try {
      return fn();
    } catch (e) {
      threw = true;
      throw e;
    } finally {
      var elapsedMs = _now() - t0;
      _recordMeasure(
        _sample(
          {
            ts: Date.now(),
            label: label,
            duration_ms: elapsedMs,
            threw: threw || undefined,
          },
          meta,
        ),
      );
    }
  }

  // Async variant returning a Promise. Useful for fetch-then-render
  // chains where we want the total user-visible latency.
  function measureAsync(label, fn, meta) {
    var t0 = _now();
    var p;
    try {
      p = fn();
    } catch (e) {
      _recordMeasure(
        _sample(
          {
            ts: Date.now(),
            label: label,
            duration_ms: _now() - t0,
            threw: true,
          },
          meta,
        ),
      );
      throw e;
    }
    if (p && typeof p.then === "function") {
      return p.then(
        (v) => {
          _recordMeasure(
            _sample(
              {
                ts: Date.now(),
                label: label,
                duration_ms: _now() - t0,
              },
              meta,
            ),
          );
          return v;
        },
        (e) => {
          _recordMeasure(
            _sample(
              {
                ts: Date.now(),
                label: label,
                duration_ms: _now() - t0,
                threw: true,
              },
              meta,
            ),
          );
          throw e;
        },
      );
    }
    _recordMeasure(
      _sample(
        {
          ts: Date.now(),
          label: label,
          duration_ms: _now() - t0,
        },
        meta,
      ),
    );
    return p;
  }

  function summarize(samples, keyFn) {
    var groups = {};
    for (var i = 0; i < samples.length; i++) {
      var s = samples[i];
      var k = keyFn(s);
      if (!groups[k]) {
        groups[k] = [];
      }
      groups[k].push(s.duration_ms);
    }
    var rows = [];
    Object.keys(groups).forEach((k) => {
      var vals = groups[k].slice().sort((a, b) => a - b);
      var n = vals.length;
      var sum = 0;
      for (var j = 0; j < n; j++) {
        sum += vals[j];
      }
      rows.push({
        key: k,
        n: n,
        min_ms: +vals[0].toFixed(2),
        median_ms: +vals[Math.floor(n / 2)].toFixed(2),
        p95_ms: +vals[Math.floor(n * 0.95)].toFixed(2),
        max_ms: +vals[n - 1].toFixed(2),
        mean_ms: +(sum / n).toFixed(2),
        total_ms: +sum.toFixed(2),
      });
    });
    rows.sort((a, b) => b.total_ms - a.total_ms);
    return rows;
  }

  function urlKey(u) {
    if (!u) {
      return "";
    }
    var qIdx = u.indexOf("?");
    return qIdx >= 0 ? u.slice(0, qIdx) : u;
  }

  function slowRows(samples) {
    return samples
      .filter((s) => slowThresholdMs && s.duration_ms >= slowThresholdMs)
      .slice()
      .sort((a, b) => b.duration_ms - a.duration_ms);
  }

  function snapshot() {
    return {
      schema: "web-performance-profile/v1",
      generated_at: new Date().toISOString(),
      slow_threshold_ms: slowThresholdMs,
      sample_capacity: MAX_SAMPLES,
      fetch_samples_seen: fetchCount,
      fetch_samples_retained: fetchSamples.length,
      fetches_in_flight: fetchesInFlight,
      fetches_in_flight_max: fetchesInFlightMax,
      fetches_in_flight_max_by_key: { ...fetchesInFlightMaxByKey },
      fetch_concurrency_keys_overflowed: fetchConcurrencyKeyOverflowed,
      fetch_aborts: fetchAbortCount,
      fetch_http_4xx: fetchHttp4xxCount,
      fetch_http_5xx: fetchHttp5xxCount,
      fetch_network_errors: fetchNetworkErrorCount,
      measure_samples_seen: measureCount,
      measure_samples_retained: measureSamples.length,
      label_capacity: MAX_LABELS,
      labels_retained: Object.keys(labelTotals).length,
      labels_overflowed: labelOverflowed,
      resource_timing_capacity: resourceTimingCapacity,
      resource_timing_buffer_full: resourceTimingBufferFull,
      navigation_ms: (() => {
        try {
          var t = performance.timing;
          if (!t?.navigationStart) {
            return null;
          }
          return {
            domContentLoaded: t.domContentLoadedEventEnd - t.navigationStart,
            loadEvent: t.loadEventEnd - t.navigationStart,
          };
        } catch (_e) {
          return null;
        }
      })(),
      fetch_summary: summarize(fetchSamples, (s) => urlKey(s.url)),
      measure_summary: summarize(measureSamples, (s) => s.label),
      slow_fetch: slowRows(fetchSamples),
      slow_measure: slowRows(measureSamples),
      raw_fetch: fetchSamples.slice(),
      raw_measure: measureSamples.slice(),
      // Whole-session totals per label, immune to ring-buffer eviction. Sorted
      // by the worst single span, because that is what a reader feels.
      responsiveness: responsiveness(),
      vitals: vitals(),
      worst_animation_frames: worstAnimationFrames.slice(),
      label_totals: Object.keys(labelTotals)
        .map((k) => {
          var r = labelTotals[k];
          return {
            label: r.label,
            count: r.count,
            total_ms: Math.round(r.total_ms),
            max_ms: Math.round(r.max_ms),
            over_200ms: r.over_200ms,
            work_items_total: r.work_items_measured ? r.work_items_total : null,
            work_items_max: r.work_items_measured ? r.work_items_max : null,
            first_end_ms: Math.round(
              r.first_ts - (typeof performance !== "undefined" ? performance.timeOrigin || 0 : 0),
            ),
            first_duration_ms: Math.round(r.first_duration_ms),
          };
        })
        .sort((a, b) => b.max_ms - a.max_ms),
    };
  }

  function report() {
    var snap = snapshot();
    if (typeof console !== "undefined") {
      console.log("%cMetabrowser perf — fetch", "font-weight:bold");
      if (console.table) {
        console.table(snap.fetch_summary);
      } else {
        console.log(snap.fetch_summary);
      }
      // Responsiveness first: it is the one a reader feels, and the one that
      // says whether the rest of this report is even admissible.
      var r = snap.responsiveness;
      console.log("%cMetabrowser perf — responsiveness", "font-weight:bold");
      if (!r.measurement_valid) {
        console.warn(
          "These numbers are VOID: the tab was hidden during measurement, and a " +
            "hidden tab has different browser scheduling. Re-run in a " +
            "visible, foregrounded window.",
        );
      }
      if (console.table) {
        console.table([
          { metric: "longest block (ms)", value: r.long_task_max_ms },
          { metric: "longest block, first 5s (ms)", value: r.long_task_max_ms_first_5s },
          { metric: "blocks over 200 ms", value: r.long_tasks_over_200ms },
          { metric: "total blocking time (ms)", value: r.total_blocking_time_ms },
          { metric: "longest animation frame (ms)", value: r.animation_frame_max_ms },
          { metric: "animation frames over 200 ms", value: r.animation_frames_over_200ms },
          { metric: "forced style/layout max (ms)", value: r.forced_style_layout_ms_max },
          { metric: "blocked share (%)", value: r.main_thread_blocked_pct },
          { metric: "over window (ms)", value: r.window_ms },
          {
            metric: "interaction p50 / p95 / max (ms)",
            value: `${r.interaction_p50_ms} / ${r.interaction_p95_ms} / ${r.interaction_max_ms}`,
          },
          { metric: "measured visible", value: r.measurement_valid },
        ]);
      } else {
        console.log(r);
      }
      console.log("%cMetabrowser perf — what blocked (worst span first)", "font-weight:bold");
      if (console.table) {
        console.table(snap.label_totals);
      } else {
        console.log(snap.label_totals);
      }
      console.log("%cMetabrowser perf — render spans", "font-weight:bold");
      if (console.table) {
        console.table(snap.measure_summary);
      } else {
        console.log(snap.measure_summary);
      }
      if (snap.slow_fetch.length || snap.slow_measure.length) {
        console.warn(`Metabrowser perf — slow samples >= ${snap.slow_threshold_ms} ms`);
        if (console.table) {
          console.table(snap.slow_fetch.concat(snap.slow_measure));
        } else {
          console.log(snap.slow_fetch.concat(snap.slow_measure));
        }
      }
      if (snap.navigation_ms) {
        console.log("Navigation:", snap.navigation_ms);
      }
    }
    return snap;
  }

  function copy() {
    var snap = snapshot();
    var text = JSON.stringify(snap, null, 2);
    if (navigator?.clipboard?.writeText) {
      return navigator.clipboard.writeText(text).then(() => {
        if (console?.log) {
          console.log(`Copied perf report to clipboard (${text.length} bytes).`);
        }
      });
    }
    if (console?.log) {
      console.log(text);
    }
    return Promise.resolve(text);
  }

  function download(name) {
    var snap = snapshot();
    var text = JSON.stringify(snap, null, 2);
    var blob = new Blob([text], { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name || `metabrowser-perf-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 100);
  }

  // ── Responsiveness ────────────────────────────────────────────────
  //
  // Attached when this module loads, which is the only time that works: the
  // worst blocking is in the first seconds, when the event rate is highest and
  // the reader is deciding whether the app is alive. Anything attached later
  // has already missed it and reads a bounded browser buffer that a bad load
  // has already overrun.
  //
  // Cheap by construction. The metric observers update fixed-size state; the
  // browser was already computing these entries. Long-task aggregates stay
  // exact for the whole measurement window, while interaction percentiles use
  // the same bounded recent-sample ring as the detailed fetch/span records.
  // Event Timing emits several entries for one logical gesture (for example,
  // pointerdown, pointerup, and click). INP groups those entries by non-zero
  // `interactionId` and uses the slowest entry as that interaction's latency.
  // Keep the same unit here: one retained row is one user interaction, not one
  // DOM event. The Map covers only the bounded retained window, so detail stays
  // bounded along with the array it indexes.
  var interactions = [];
  var interactionsById = new Map();
  var observerNotes = [];
  var attributionNotes = [];
  var vitalNotes = [];
  // Performance-entry start times are navigation-relative. Start the initial
  // window at navigation too so buffered entries from before this script ran
  // remain part of the load; reset() moves the boundary to the current time.
  var measurementStartedAt = 0;
  var longTaskCount = 0;
  var longTaskTotalMs = 0;
  var longTaskBlockingTotalMs = 0;
  var longTaskMaxMs = 0;
  var longTaskMaxFirst5sMs = 0;
  var longTasksOver200Ms = 0;
  var interactionCount = 0;
  var interactionInputCount = 0;
  var interactionInputFirstMs = null;
  var interactionInputLastMs = null;
  var interactionMaxMs = 0;
  var animationFrameCount = 0;
  var animationFrameMaxMs = 0;
  var animationFramesOver200Ms = 0;
  var animationFrameBlockingTotalMs = 0;
  var animationFrameBlockingMaxMs = 0;
  var animationFramesBlockingOver200Ms = 0;
  var forcedStyleLayoutMaxMs = 0;
  var worstAnimationFrames = [];
  var firstContentfulPaintMs = null;
  var largestContentfulPaintMs = null;
  var largestContentfulPaintEntries = 0;
  var largestContentfulPaintElement = null;
  var cumulativeLayoutShift = 0;
  var cumulativeLayoutShiftEntries = 0;
  var currentLayoutShiftWindow = 0;
  var currentLayoutShiftWindowStart = null;
  var currentLayoutShiftWindowLast = null;
  // Whether the page was EVER hidden. Chromium throttles a hidden tab --
  // clamping timers and batching deferred work -- so its scheduling is not
  // comparable to a reader's visible session. A number from a run that was
  // backgrounded even briefly is void, not merely noisy, so this is recorded
  // rather than left to whoever reads the output to remember.
  var everHidden = typeof document !== "undefined" && document.visibilityState !== "visible";

  // A block past this is not jank, it is a freeze: no paint, no animation, no
  // response to a click. The project's own line is that nothing under ~50 ms
  // should flash a spinner, so half a second of frozen UI is well past what any
  // reader tolerates silently.
  var FREEZE_WARN_MS = 500;

  /**
   * Browser support has to be established before absence can mean zero.
   * Some engines accept observe({type}) for an unsupported entry type without
   * throwing, so a try/catch alone can manufacture a clean-looking empty run.
   */
  function _supportsEntryType(type) {
    if (typeof PerformanceObserver === "undefined") {
      return false;
    }
    var supported = PerformanceObserver.supportedEntryTypes;
    return supported != null && Array.from(supported).includes(type);
  }

  // Paint and stability observers belong at navigation too. A late LCP lookup
  // usually survives; a long progressive load can overflow buffered layout
  // shifts, and summing every shift is not CLS in any case. CLS is the maximum
  // session window: gaps under one second, capped at five seconds.
  try {
    if (!_supportsEntryType("paint")) {
      throw new Error("paint PerformanceObserver entries are unsupported");
    }
    var paintObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (
          entry.startTime >= measurementStartedAt &&
          entry.name === "first-contentful-paint" &&
          firstContentfulPaintMs === null
        ) {
          firstContentfulPaintMs = Math.round(entry.startTime);
        }
      }
    });
    paintObserver.observe({ type: "paint", buffered: true });
  } catch (_noPaint) {
    vitalNotes.push("paint");
  }

  try {
    if (!_supportsEntryType("largest-contentful-paint")) {
      throw new Error("largest-contentful-paint PerformanceObserver entries are unsupported");
    }
    var lcpObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.startTime < measurementStartedAt) {
          continue;
        }
        var lcpEntry = /** @type {any} */ (entry);
        largestContentfulPaintMs = Math.round(entry.startTime);
        largestContentfulPaintEntries += 1;
        var element = lcpEntry.element;
        largestContentfulPaintElement = element
          ? `${element.tagName || "?"}.${String(element.className || "").split(" ")[0]}`
          : null;
      }
    });
    lcpObserver.observe({ type: "largest-contentful-paint", buffered: true });
  } catch (_noLcp) {
    vitalNotes.push("largest-contentful-paint");
  }

  try {
    if (!_supportsEntryType("layout-shift")) {
      throw new Error("layout-shift PerformanceObserver entries are unsupported");
    }
    var layoutShiftObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        var shiftEntry = /** @type {any} */ (entry);
        if (entry.startTime < measurementStartedAt || shiftEntry.hadRecentInput) {
          continue;
        }
        var startsNewWindow =
          currentLayoutShiftWindowStart === null ||
          currentLayoutShiftWindowLast === null ||
          entry.startTime - currentLayoutShiftWindowLast >= 1000 ||
          entry.startTime - currentLayoutShiftWindowStart > 5000;
        if (startsNewWindow) {
          currentLayoutShiftWindow = Number(shiftEntry.value || 0);
          currentLayoutShiftWindowStart = entry.startTime;
        } else {
          currentLayoutShiftWindow += Number(shiftEntry.value || 0);
        }
        currentLayoutShiftWindowLast = entry.startTime;
        cumulativeLayoutShift = Math.max(cumulativeLayoutShift, currentLayoutShiftWindow);
        cumulativeLayoutShiftEntries += 1;
      }
    });
    layoutShiftObserver.observe({ type: "layout-shift", buffered: true });
  } catch (_noLayoutShift) {
    vitalNotes.push("layout-shift");
  }

  /**
   * Which measured spans were running while the thread was blocked.
   *
   * A `longtask` entry says the main thread was busy and nothing about what it
   * was busy with, which is the whole difficulty in diagnosing one. Spans record
   * when they finished and how long they took, so a span whose own interval
   * overlaps the task's is a candidate for having caused it. This is a
   * correlation and is labelled as one -- but it is the difference between "the
   * page froze for thirteen seconds" and a list of three function names.
   */
  function _spansDuring(taskStartMs, taskEndMs) {
    var origin = typeof performance !== "undefined" ? performance.timeOrigin || 0 : 0;
    var overlapping = [];
    for (var i = 0; i < measureSamples.length; i++) {
      var sample = measureSamples[i];
      // `ts` is Date.now() at the moment the span finished.
      var endedAt = sample.ts - origin;
      var startedAt = endedAt - sample.duration_ms;
      if (endedAt >= taskStartMs && startedAt <= taskEndMs) {
        overlapping.push({
          label: sample.label,
          duration_ms: Math.round(sample.duration_ms),
          meta: sample.meta || null,
        });
      }
    }
    return overlapping.sort((a, b) => b.duration_ms - a.duration_ms).slice(0, 5);
  }

  try {
    if (!_supportsEntryType("longtask")) {
      throw new Error("longtask PerformanceObserver entries are unsupported");
    }
    var taskObserver = new PerformanceObserver((list) => {
      var entries = list.getEntries();
      for (var i = 0; i < entries.length; i++) {
        var entry = entries[i];
        if (entry.startTime < measurementStartedAt) {
          continue;
        }
        var startMs = Math.round(entry.startTime);
        var durMs = Math.round(entry.duration);
        longTaskCount += 1;
        longTaskTotalMs += durMs;
        longTaskBlockingTotalMs += Math.max(0, durMs - 50);
        longTaskMaxMs = Math.max(longTaskMaxMs, durMs);
        if (entry.startTime - measurementStartedAt < 5000) {
          longTaskMaxFirst5sMs = Math.max(longTaskMaxFirst5sMs, durMs);
        }
        if (durMs > 200) {
          longTasksOver200Ms += 1;
        }
        // Say it out loud. This is the signal that took a person driving a
        // browser and pasting a console table to find; it should announce
        // itself instead.
        if (durMs >= FREEZE_WARN_MS && typeof console !== "undefined") {
          var details = {
            blocked_ms: durMs,
            at_ms: startMs,
            spans_during: _spansDuring(startMs, startMs + durMs),
            hint: "metabrowser.perf.responsiveness() for the whole picture",
          };
          console.warn(
            `[metabrowser perf] main thread blocked ${durMs} ms — the page could not ` +
              `paint or respond during this. details=${JSON.stringify(details)}`,
            details,
          );
        }
      }
    });
    taskObserver.observe({ type: "longtask", buffered: true });
  } catch (_noLongTask) {
    observerNotes.push("longtask");
  }

  // Long Animation Frames retain the browser's script attribution and forced
  // style/layout cost, which Long Tasks deliberately do not. Keep this as a
  // diagnostic alongside the portable Long Tasks total: it names the function
  // to investigate when Chromium provides the entry type, and changes no
  // validity or responsiveness metric when it does not.
  try {
    if (!_supportsEntryType("long-animation-frame")) {
      throw new Error("long-animation-frame PerformanceObserver entries are unsupported");
    }
    var frameObserver = new PerformanceObserver((list) => {
      var entries = list.getEntries();
      for (var i = 0; i < entries.length; i++) {
        var entry = /** @type {any} */ (entries[i]);
        if (entry.startTime < measurementStartedAt) {
          continue;
        }
        var durationMs = Math.round(entry.duration || 0);
        var blockingMs = Math.round(entry.blockingDuration || 0);
        var forcedStyleLayoutMs = Array.from(entry.scripts || []).reduce(
          (total, script) => total + Number(script.forcedStyleAndLayoutDuration || 0),
          0,
        );
        animationFrameCount += 1;
        animationFrameMaxMs = Math.max(animationFrameMaxMs, durationMs);
        animationFrameBlockingTotalMs += blockingMs;
        animationFrameBlockingMaxMs = Math.max(animationFrameBlockingMaxMs, blockingMs);
        forcedStyleLayoutMaxMs = Math.max(forcedStyleLayoutMaxMs, forcedStyleLayoutMs);
        if (durationMs > 200) {
          animationFramesOver200Ms += 1;
        }
        if (blockingMs > 200) {
          animationFramesBlockingOver200Ms += 1;
        }
        if (durationMs < 200) {
          continue;
        }
        var scripts = Array.from(entry.scripts || [])
          .map((script) => ({
            duration_ms: Math.round(script.duration || 0),
            forced_style_layout_ms: Math.round(script.forcedStyleAndLayoutDuration || 0),
            function: script.sourceFunctionName || "(anonymous)",
            invoker: script.invoker || script.invokerType || null,
            pause_ms: Math.round(script.pauseDuration || 0),
            source: script.sourceURL || null,
          }))
          .sort((left, right) => right.duration_ms - left.duration_ms)
          .slice(0, 10);
        var frameDetails = {
          start_ms: Math.round(entry.startTime),
          duration_ms: Math.round(entry.duration),
          blocking_ms: Math.round(entry.blockingDuration || 0),
          render_ms: Math.round(
            entry.renderStart && entry.styleAndLayoutStart
              ? entry.styleAndLayoutStart - entry.renderStart
              : 0,
          ),
          scripts: scripts,
          resources: /** @type {PerformanceResourceTiming[]} */ (
            performance.getEntriesByType("resource")
          )
            .filter(
              (resource) =>
                resource.name.includes("/api/") &&
                resource.responseEnd >= entry.startTime - 1000 &&
                resource.responseEnd <= entry.startTime + entry.duration,
            )
            .map((resource) => ({
              url: resource.name,
              response_end_ms: Math.round(resource.responseEnd),
              decoded_bytes: resource.decodedBodySize,
              transfer_bytes: resource.transferSize,
            }))
            .slice(-10),
        };
        worstAnimationFrames.push(frameDetails);
        worstAnimationFrames.sort((left, right) => right.duration_ms - left.duration_ms);
        if (worstAnimationFrames.length > WORST_FRAME_SAMPLES) {
          worstAnimationFrames.length = WORST_FRAME_SAMPLES;
        }
        if (durationMs >= FREEZE_WARN_MS && typeof console !== "undefined") {
          console.warn(
            `[metabrowser perf] long animation frame details=${JSON.stringify(frameDetails)}`,
            frameDetails,
          );
        }
      }
    });
    frameObserver.observe({ type: "long-animation-frame", buffered: true });
  } catch (_noLongAnimationFrame) {
    attributionNotes.push("long-animation-frame");
  }

  try {
    if (!_supportsEntryType("event")) {
      throw new Error("event PerformanceObserver entries are unsupported");
    }
    var eventObserver = new PerformanceObserver((list) => {
      var entries = list.getEntries();
      for (var i = 0; i < entries.length; i++) {
        var entry = entries[i];
        if (entry.startTime < measurementStartedAt) {
          continue;
        }
        var eventEntry = /** @type {any} */ (entry);
        var interactionId = Number(eventEntry.interactionId || 0);
        // Event Timing also exposes events that are not part of an INP-style
        // click, tap, or key interaction. A zero id cannot be grouped into a
        // logical user gesture and therefore does not belong in these fields.
        if (!Number.isFinite(interactionId) || interactionId <= 0) {
          continue;
        }
        var duration = Math.round(entry.duration);
        interactionMaxMs = Math.max(interactionMaxMs, duration);
        var interaction = interactionsById.get(interactionId);
        if (interaction) {
          if (duration > interaction.dur) {
            interaction.dur = duration;
            interaction.name = entry.name;
          }
          continue;
        }
        interactionCount += 1;
        interaction = { id: interactionId, name: entry.name, dur: duration };
        interactions.push(interaction);
        interactionsById.set(interactionId, interaction);
        if (interactions.length > MAX_SAMPLES) {
          var evicted = interactions.shift();
          if (evicted) {
            interactionsById.delete(evicted.id);
          }
        }
      }
    });
    // One frame. Below it an interaction cannot have missed a paint.
    // `durationThreshold` is Event Timing, which the bundled DOM lib predates;
    // the cast is about the type definition's age, not about the option.
    eventObserver.observe(
      /** @type {PerformanceObserverInit} */ ({
        type: "event",
        durationThreshold: 16,
        buffered: true,
      }),
    );
  } catch (_noEventTiming) {
    observerNotes.push("event");
  }

  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState !== "visible") {
        everHidden = true;
      }
    });
    var recordInteractionInput = (event) => {
      if (event.isTrusted) {
        var inputAtMs = _now();
        if (interactionInputFirstMs === null) {
          interactionInputFirstMs = inputAtMs;
        }
        interactionInputLastMs = inputAtMs;
        interactionInputCount += 1;
      }
    };
    document.addEventListener("click", recordInteractionInput, {
      capture: true,
      passive: true,
    });
    document.addEventListener("keydown", recordInteractionInput, true);
  }

  function _percentile(values, q) {
    if (values.length === 0) {
      return null;
    }
    var sorted = values.slice().sort((a, b) => a - b);
    return sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))];
  }

  /**
   * How responsive the page has been since it loaded.
   *
   * `long_task_max_ms` is the field to read: a total cannot tell sixty 100 ms
   * hitches from one six-second freeze, and only one of those is a broken
   * product. Read `main_thread_blocked_pct` against its window -- the same work
   * in half the time doubles the share while improving every absolute.
   */
  function responsiveness() {
    var latencies = interactions.map((i) => i.dur);
    var windowMs = Math.round(Math.max(0, _now() - measurementStartedAt));
    var interactionInputSpanMs =
      interactionInputFirstMs !== null && interactionInputLastMs !== null
        ? Math.max(0, interactionInputLastMs - interactionInputFirstMs)
        : 0;
    var frameAttributionSupported = !attributionNotes.includes("long-animation-frame");
    return {
      measurement_valid: !everHidden,
      visibility_state: typeof document !== "undefined" ? document.visibilityState : null,
      ever_hidden: everHidden,
      unsupported: observerNotes.length > 0 ? observerNotes.slice() : null,
      attribution_unsupported: attributionNotes.length > 0 ? attributionNotes.slice() : null,
      profile_started_at_ms: Math.round(measurementStartedAt),
      window_ms: windowMs,
      long_tasks: longTaskCount,
      long_task_ms_total: longTaskTotalMs,
      total_blocking_time_ms: longTaskBlockingTotalMs,
      long_task_max_ms: longTaskMaxMs,
      long_task_max_ms_first_5s: longTaskMaxFirst5sMs,
      long_tasks_over_200ms: longTasksOver200Ms,
      main_thread_blocked_pct:
        windowMs > 0 ? Math.round((1000 * longTaskTotalMs) / windowMs) / 10 : null,
      interactions: interactionCount,
      interaction_inputs: interactionInputCount,
      interaction_input_first_ms:
        interactionInputFirstMs === null
          ? null
          : Math.round(interactionInputFirstMs - measurementStartedAt),
      interaction_input_last_ms:
        interactionInputLastMs === null
          ? null
          : Math.round(interactionInputLastMs - measurementStartedAt),
      interaction_input_span_ms: Math.round(interactionInputSpanMs),
      interaction_input_coverage_pct:
        windowMs > 0 ? Math.round((1000 * interactionInputSpanMs) / windowMs) / 10 : 0,
      interaction_samples_retained: interactions.length,
      interaction_percentile_scope:
        interactionCount > interactions.length ? `most-recent-${MAX_SAMPLES}` : "all",
      interaction_p50_ms: _percentile(latencies, 0.5),
      interaction_p95_ms: _percentile(latencies, 0.95),
      interaction_max_ms: interactionMaxMs,
      animation_frames: frameAttributionSupported ? animationFrameCount : null,
      animation_frame_max_ms: frameAttributionSupported ? animationFrameMaxMs : null,
      animation_frames_over_200ms: frameAttributionSupported ? animationFramesOver200Ms : null,
      animation_frame_blocking_ms_total: frameAttributionSupported
        ? animationFrameBlockingTotalMs
        : null,
      animation_frame_blocking_ms_max: frameAttributionSupported
        ? animationFrameBlockingMaxMs
        : null,
      animation_frames_blocking_over_200ms: frameAttributionSupported
        ? animationFramesBlockingOver200Ms
        : null,
      forced_style_layout_ms_max: frameAttributionSupported
        ? Math.round(forcedStyleLayoutMaxMs)
        : null,
    };
  }

  function vitals() {
    return {
      unsupported: vitalNotes.length > 0 ? vitalNotes.slice() : null,
      fcp_ms: firstContentfulPaintMs,
      lcp_ms: largestContentfulPaintMs,
      lcp_entries: vitalNotes.includes("largest-contentful-paint")
        ? null
        : largestContentfulPaintEntries,
      lcp_element: largestContentfulPaintElement,
      cls: vitalNotes.includes("layout-shift") ? null : Number(cumulativeLayoutShift.toFixed(4)),
      cls_shifts: vitalNotes.includes("layout-shift") ? null : cumulativeLayoutShiftEntries,
    };
  }

  function reset() {
    measurementStartedAt = _now();
    fetchSamples.length = 0;
    measureSamples.length = 0;
    interactions.length = 0;
    interactionsById.clear();
    if (resourceTimingCapacity !== null) {
      performance.clearResourceTimings?.();
      performance.setResourceTimingBufferSize?.(resourceTimingCapacity);
      resourceTimingBufferFull = 0;
    }
    labelTotals = {};
    fetchCount = 0;
    fetchesInFlightMax = fetchesInFlight;
    fetchesInFlightMaxByKey = { ...fetchesInFlightByKey };
    fetchConcurrencyKeyOverflowed = 0;
    fetchAbortCount = 0;
    fetchHttp4xxCount = 0;
    fetchHttp5xxCount = 0;
    fetchNetworkErrorCount = 0;
    measureCount = 0;
    labelOverflowed = 0;
    longTaskCount = 0;
    longTaskTotalMs = 0;
    longTaskBlockingTotalMs = 0;
    longTaskMaxMs = 0;
    longTaskMaxFirst5sMs = 0;
    longTasksOver200Ms = 0;
    interactionCount = 0;
    interactionInputCount = 0;
    interactionInputFirstMs = null;
    interactionInputLastMs = null;
    interactionMaxMs = 0;
    animationFrameCount = 0;
    animationFrameMaxMs = 0;
    animationFramesOver200Ms = 0;
    animationFrameBlockingTotalMs = 0;
    animationFrameBlockingMaxMs = 0;
    animationFramesBlockingOver200Ms = 0;
    forcedStyleLayoutMaxMs = 0;
    worstAnimationFrames.length = 0;
    firstContentfulPaintMs = null;
    largestContentfulPaintMs = null;
    largestContentfulPaintEntries = 0;
    largestContentfulPaintElement = null;
    cumulativeLayoutShift = 0;
    cumulativeLayoutShiftEntries = 0;
    currentLayoutShiftWindow = 0;
    currentLayoutShiftWindowStart = null;
    currentLayoutShiftWindowLast = null;
    everHidden = typeof document !== "undefined" && document.visibilityState !== "visible";
  }

  function setSlowThreshold(ms) {
    var next = Number(ms);
    if (!Number.isFinite(next) || next < 0) {
      throw new Error("slow threshold must be a non-negative number of milliseconds");
    }
    slowThresholdMs = next;
    return slowThresholdMs;
  }

  var profiler = {
    measure: measure,
    measureAsync: measureAsync,
    responsiveness: responsiveness,
    setSlowThreshold: setSlowThreshold,
    snapshot: snapshot,
    report: report,
    copy: copy,
    download: download,
    reset: reset,
  };
  window.metabrowser.perf = Object.freeze(profiler);
})();
