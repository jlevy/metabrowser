// Metabrowser — frontend perf instrumentation
//
// Lightweight, opt-in profiler. Records User Timing API marks/measures
// around every interesting fetch + render path so a user (or the bench
// harness) can produce a "what's actually slow on the client?" report
// without devtools open.
//
// Activation:
//   * Sessions automatically record samples in a small ring buffer.
//   * Open devtools and run `metabrowserPerf.report()` to see a table.
//   * `metabrowserPerf.copy()` puts a JSON dump on the clipboard.
//   * `metabrowserPerf.download()` saves the JSON as a file.
//
// The instrumentation hooks `window.fetch` once for HTTP timings and
// exposes `metabrowserPerf.measure(label, fn, meta)` for ad-hoc spans inside
// existing render code. `app.js` opts in with `metabrowserPerf.measure(...)`
// calls; if `perf.js` is missing those calls fall through to plain
// invocation.

(() => {
  if (typeof window === "undefined") {
    return;
  }

  var MAX_SAMPLES = 500;
  var DEFAULT_SLOW_THRESHOLD_MS = 2000;
  var fetchSamples = [];
  var measureSamples = [];
  var slowThresholdMs = DEFAULT_SLOW_THRESHOLD_MS;

  // Per-label running totals that are NEVER evicted.
  //
  // The sample buffers above are ring buffers keeping the most recent
  // MAX_SAMPLES, which is right for inspecting detail and wrong for attributing
  // a load: the worst blocking is at the start, when the event rate is highest,
  // and a busy load pushes exactly those spans out before anyone looks. These
  // totals are bounded by the number of distinct labels — about twenty — rather
  // than by time, so the first second survives however long the session runs.
  //
  // `max_ms` is the field to read. A total cannot tell sixty 100 ms hitches
  // from one six-second freeze, and only one of those is a broken experience.
  var labelTotals = {};

  function _tally(label, durationMs) {
    var row = labelTotals[label];
    if (!row) {
      row = { label: label, count: 0, total_ms: 0, max_ms: 0, over_200ms: 0, first_ts: Date.now() };
      labelTotals[label] = row;
    }
    row.count += 1;
    row.total_ms += durationMs;
    if (durationMs > row.max_ms) {
      row.max_ms = durationMs;
    }
    if (durationMs > 200) {
      row.over_200ms += 1;
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
      var p = fetchImpl(input, init);
      p.then((resp) => {
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
        _record(fetchSamples, "fetch", {
          ts: Date.now(),
          url: url,
          status: status,
          duration_ms: t1 - t0,
          size_bytes: size,
          server_ms: serverMs,
        });
      }).catch(() => {
        var t1 = _now();
        _record(fetchSamples, "fetch", {
          ts: Date.now(),
          url: url,
          status: 0,
          duration_ms: t1 - t0,
          size_bytes: -1,
          error: true,
        });
      });
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
      _tally(label, elapsedMs);
      _record(
        measureSamples,
        "span",
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
      _record(
        measureSamples,
        "span",
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
          _record(
            measureSamples,
            "span",
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
          _record(
            measureSamples,
            "span",
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
    _record(
      measureSamples,
      "span",
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
      schema: "metabrowser-perf/v1",
      generated_at: new Date().toISOString(),
      slow_threshold_ms: slowThresholdMs,
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
      label_totals: Object.keys(labelTotals)
        .map((k) => {
          var r = labelTotals[k];
          return {
            label: r.label,
            count: r.count,
            total_ms: Math.round(r.total_ms),
            max_ms: Math.round(r.max_ms),
            over_200ms: r.over_200ms,
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
            "hidden tab is throttled into manufacturing long tasks. Re-run in a " +
            "visible, foregrounded window.",
        );
      }
      if (console.table) {
        console.table([
          { metric: "longest block (ms)", value: r.long_task_max_ms },
          { metric: "longest block, first 5s (ms)", value: r.long_task_max_ms_first_5s },
          { metric: "blocks over 200 ms", value: r.long_tasks_over_200ms },
          { metric: "blocked share (%)", value: r.main_thread_blocked_pct },
          { metric: "over window (ms)", value: r.window_ms },
          {
            metric: "interaction p50 / max (ms)",
            value: `${r.interaction_p50_ms} / ${r.interaction_max_ms}`,
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
  // Cheap by construction. Two observers, and the callbacks only push small
  // records; the browser was already computing these entries.
  var longTasks = [];
  var interactions = [];
  var observerNotes = [];
  // Whether the page was EVER hidden. Chromium throttles a hidden tab --
  // clamping timers and batching deferred work -- which manufactures
  // multi-second tasks no reader would meet. A number from a run that was
  // backgrounded even briefly is void, not merely noisy, so this is recorded
  // rather than left to whoever reads the output to remember.
  var everHidden = typeof document !== "undefined" && document.visibilityState !== "visible";

  try {
    var taskObserver = new PerformanceObserver((list) => {
      var entries = list.getEntries();
      for (var i = 0; i < entries.length; i++) {
        longTasks.push({
          start: Math.round(entries[i].startTime),
          dur: Math.round(entries[i].duration),
        });
      }
    });
    taskObserver.observe({ type: "longtask", buffered: true });
  } catch (_noLongTask) {
    observerNotes.push("longtask");
  }

  try {
    var eventObserver = new PerformanceObserver((list) => {
      var entries = list.getEntries();
      for (var i = 0; i < entries.length; i++) {
        interactions.push({ name: entries[i].name, dur: Math.round(entries[i].duration) });
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
    var durations = longTasks.map((t) => t.dur);
    var blocked = durations.reduce((total, d) => total + d, 0);
    var latencies = interactions.map((i) => i.dur);
    var windowMs = Math.round(_now());
    return {
      measurement_valid: !everHidden,
      visibility_state: typeof document !== "undefined" ? document.visibilityState : null,
      ever_hidden: everHidden,
      unsupported: observerNotes.length > 0 ? observerNotes.slice() : null,
      window_ms: windowMs,
      long_tasks: longTasks.length,
      long_task_ms_total: blocked,
      long_task_max_ms: durations.reduce((worst, d) => Math.max(worst, d), 0),
      long_task_max_ms_first_5s: longTasks
        .filter((t) => t.start < 5000)
        .reduce((worst, t) => Math.max(worst, t.dur), 0),
      long_tasks_over_200ms: durations.filter((d) => d > 200).length,
      main_thread_blocked_pct: windowMs > 0 ? Math.round((1000 * blocked) / windowMs) / 10 : null,
      interactions: interactions.length,
      interaction_p50_ms: _percentile(latencies, 0.5),
      interaction_p95_ms: _percentile(latencies, 0.95),
      interaction_max_ms: latencies.reduce((worst, d) => Math.max(worst, d), 0),
    };
  }

  function reset() {
    fetchSamples.length = 0;
    measureSamples.length = 0;
    longTasks.length = 0;
    interactions.length = 0;
    labelTotals = {};
  }

  function setSlowThreshold(ms) {
    var next = Number(ms);
    if (!Number.isFinite(next) || next < 0) {
      throw new Error("slow threshold must be a non-negative number of milliseconds");
    }
    slowThresholdMs = next;
    return slowThresholdMs;
  }

  window.metabrowserPerf = {
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
})();
