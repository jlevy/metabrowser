// What a page tells the event log it saw, and the Details a failure or a late wait offers.
//
// The server records every request and the work each starts (metabrowser/event_log.py),
// but only the page knows what it waited for. This module reports to
// POST /api/event-log/client (metabrowser/event_log_reports.py), which writes each report
// as a `browser` record:
//
// - a request to this server slower than `slow_ms`, when it answers, and one still
//   pending at `slow_ms`, then again as `never_completed` if the page is left first;
// - a frame that blocked the main thread for `freeze_ms` or more, with the script the
//   browser blames for it, where the browser says (Long Animation Frames, else Long Tasks;
//   WebKit, the macOS app's engine, has neither, so the app reports no freezes);
// - a wait the page shows as loading that has run `late_ms` while the page was shown, then
//   when it ends, or as `never_completed` if the page is left first. A wait under
//   `late_ms` reports nothing. Time the page spent hidden does not count: the page stops
//   polling while hidden, so a wait would be late for no fault of the work; it is sent as
//   `hidden_ms`.
//
// Every request it sends to /api/ carries the page's ID for it in a header
// (`x-metabrowser-client`, `<page>-<n>`), which the server's record of the request, and
// of the jobs and processes it starts, carries as `client`. So
// `/api/event-log?client=<page>` is everything one page asked for and saw, and a report
// names the request it is about. The thresholds and bounds are the server's
// (`METABROWSER_SETTINGS.EVENT_REPORTS`, from event_log_reports.browser_settings), and a
// server that writes no log gets no header and no report; a late wait still says so.
//
// It is the `event-reports` on-demand bundle and the last script of `shell-tools`, so it
// loads after the first usable tree; a page that waits before then asks for it by name.
// A request answered before it loaded is read from Resource Timing. The fast path costs a
// header and two Map writes per request; reports are batched for `flush_ms` and sent with
// `keepalive`, so the last ones leave with the page (sendBeacon cannot send the JSON type
// the same-origin guard requires).
//
// `describeDetails` turns the log routes' answers into what the Details panel says, and
// `showDetails` paints it; tests/dom/event-reports-session.js runs both, and the reporter,
// against the production code without a browser.

(() => {
  /** A name for the page, eight letters and digits: unique enough among one server's pages. */
  function newPageId() {
    const bytes = new Uint8Array(8);
    globalThis.crypto.getRandomValues(bytes);
    return Array.from(bytes, (byte) => (byte % 36).toString(36)).join("");
  }

  /** @param {number} value */
  const tenths = (value) => Math.round(value * 10) / 10;

  /**
   * The `srv` duration of a Server-Timing header value, or null.
   *
   * @param {string | null | undefined} raw
   */
  function serverMs(raw) {
    if (!raw) {
      return null;
    }
    for (const entry of raw.split(",")) {
      const [name, ...parts] = entry.split(";").map((part) => part.trim());
      if (name !== "srv") {
        continue;
      }
      for (const part of parts) {
        const [key, value] = part.split("=");
        const number = Number.parseFloat(value ?? "");
        if (key === "dur" && Number.isFinite(number)) {
          return number;
        }
      }
    }
    return null;
  }

  /**
   * The reporter: tags requests, notices slow and pending ones, keeps the page's named
   * waits, and sends what is late in batches. Everything it touches is injected.
   *
   * @param {MetabrowserEventReportsEnvironment} env
   * @returns {MetabrowserEventReporter}
   */
  function createReporter(env) {
    const settings = env.settings;
    const page = env.pageId ?? newPageId();
    let sequence = 0;
    /** @type {MetabrowserEventReport[]} */
    const queue = [];
    let dropped = 0;
    /** @type {unknown} */
    let flushTimer = null;
    let windowStart = Number.NEGATIVE_INFINITY;
    let windowCount = 0;
    /** @type {Map<string, {name: string, at: number, reported: boolean}>} */
    const pending = new Map();
    /** @type {unknown} */
    let sweepTimer = null;
    /** @typedef {{name: string, at: number, late: boolean, done: boolean, timer: unknown, hiddenMs: number, hiddenSince: number | null, detail: Record<string, string | number | boolean | null> | undefined, onLate: ((ms: number) => void) | undefined}} WaitState */
    /** @type {Set<WaitState>} */
    const waits = new Set();
    let hidden = env.hidden?.() ?? false;

    /** @param {MetabrowserEventReport} report */
    function enqueue(report) {
      if (!settings.log) {
        return false;
      }
      const now = env.now();
      if (now - windowStart >= 60_000) {
        windowStart = now;
        windowCount = 0;
      }
      if (windowCount >= settings.per_minute) {
        dropped += 1;
        return false;
      }
      windowCount += 1;
      queue.push(report);
      if (queue.length >= settings.max_batch) {
        void flush();
      } else if (flushTimer === null) {
        flushTimer = env.setTimeout(() => {
          flushTimer = null;
          void flush();
        }, settings.flush_ms);
      }
      return true;
    }

    /**
     * Send what is queued now, in bodies of at most `max_batch` reports. Resolves when the
     * server has answered them, or they failed: the Details wait for it, so the page's own
     * reports are in the log they read. Nothing else waits on a report.
     *
     * @returns {Promise<void>}
     */
    function flush() {
      if (flushTimer !== null) {
        env.clearTimeout(flushTimer);
        flushTimer = null;
      }
      /** @type {Promise<unknown>[]} */
      const sent = [];
      while (queue.length > 0 || dropped > 0) {
        const reports = queue.splice(0, settings.max_batch);
        const body = JSON.stringify({ page, path: env.path(), reports, dropped });
        dropped = 0;
        try {
          sent.push(Promise.resolve(env.send(settings.route, body)).catch(() => {}));
        } catch {
          // A report that cannot be sent is lost; the page's work never waits on one.
        }
      }
      return Promise.all(sent).then(() => {});
    }

    /**
     * The request's ID and the init that names it, for a request this page sends to its
     * own server's /api/; null for any other.
     *
     * @param {string} url
     * @param {string} method
     */
    function tag(url, method) {
      if (!settings.log) {
        return null;
      }
      let parsed;
      try {
        parsed = new URL(url, env.origin);
      } catch {
        return null;
      }
      const path = parsed.pathname;
      if (
        parsed.origin !== env.origin ||
        !path.startsWith("/api/") ||
        path === settings.route ||
        settings.long_lived.some((prefix) => path.startsWith(prefix))
      ) {
        return null;
      }
      sequence += 1;
      return { id: `${page}-${sequence}`, name: `${method.toUpperCase()} ${path}` };
    }

    function armSweep() {
      if (sweepTimer !== null) {
        return;
      }
      let due = Number.POSITIVE_INFINITY;
      for (const entry of pending.values()) {
        if (!entry.reported) {
          due = Math.min(due, entry.at + settings.slow_ms);
        }
      }
      if (due !== Number.POSITIVE_INFINITY) {
        sweepTimer = env.setTimeout(sweep, Math.max(0, due - env.now()));
      }
    }

    function sweep() {
      sweepTimer = null;
      const now = env.now();
      for (const [id, entry] of pending) {
        if (!entry.reported && now - entry.at >= settings.slow_ms) {
          entry.reported = true;
          enqueue({
            type: "fetch",
            event: "open",
            name: entry.name,
            client: id,
            dur_ms: tenths(now - entry.at),
            attrs: { threshold_ms: settings.slow_ms },
          });
        }
      }
      armSweep();
    }

    /**
     * A tagged request has been sent.
     *
     * @param {{id: string, name: string}} request
     */
    function started(request) {
      pending.set(request.id, { name: request.name, at: env.now(), reported: false });
      armSweep();
    }

    /**
     * A tagged request answered or failed: reported when it was slow.
     *
     * @param {{id: string, name: string}} request
     * @param {{status?: number, serverTiming?: string | null, error?: {name?: string} | null}} result
     */
    function settled(request, result) {
      const entry = pending.get(request.id);
      if (entry === undefined) {
        return;
      }
      pending.delete(request.id);
      if (pending.size === 0 && sweepTimer !== null) {
        env.clearTimeout(sweepTimer);
        sweepTimer = null;
      }
      const duration = env.now() - entry.at;
      if (duration < settings.slow_ms) {
        return;
      }
      const error = result.error ?? null;
      const status = result.status ?? 0;
      /** @type {MetabrowserEventReport["attrs"]} */
      const attrs = { status, threshold_ms: settings.slow_ms };
      const fromServer = serverMs(result.serverTiming);
      if (fromServer !== null) {
        attrs.server_ms = tenths(fromServer);
      }
      if (error !== null) {
        attrs.error = String(error.name || "Error").slice(0, 200);
      }
      enqueue({
        type: "fetch",
        event: "end",
        name: entry.name,
        client: request.id,
        dur_ms: tenths(duration),
        outcome:
          error !== null
            ? error.name === "AbortError"
              ? "cancelled"
              : "failed"
            : status >= 500
              ? "failed"
              : "ok",
        attrs,
      });
    }

    /**
     * How long *state* has run while the page was shown, at *now*.
     *
     * @param {WaitState} state
     * @param {number} now
     */
    function shownFor(state, now) {
      return now - state.at - hiddenFor(state, now);
    }

    /**
     * How long *state* has been hidden, at *now*.
     *
     * @param {WaitState} state
     * @param {number} now
     */
    function hiddenFor(state, now) {
      return state.hiddenMs + (state.hiddenSince === null ? 0 : now - state.hiddenSince);
    }

    /**
     * Run *state*'s late timer for the shown time it has left; none while the page is
     * hidden, or once it is late or over.
     *
     * @param {WaitState} state
     */
    function arm(state) {
      if (state.timer !== null) {
        env.clearTimeout(state.timer);
        state.timer = null;
      }
      if (state.done || state.late || hidden) {
        return;
      }
      state.timer = env.setTimeout(
        () => {
          state.timer = null;
          if (state.done || hidden) {
            return;
          }
          if (shownFor(state, env.now()) < settings.late_ms) {
            arm(state);
            return;
          }
          state.late = true;
          const age = env.now() - state.at;
          enqueue({
            type: "wait",
            event: "open",
            name: state.name,
            client: page,
            dur_ms: tenths(age),
            attrs: waitAttrs(state),
          });
          try {
            state.onLate?.(age);
          } catch (error) {
            env.warn?.("event reports: a late wait's handler failed", error);
          }
        },
        Math.max(0, settings.late_ms - shownFor(state, env.now())),
      );
    }

    /**
     * Something the page shows as loading. Silent unless it has run `late_ms` while the
     * page was shown; then it is reported, `onLate` is told, and its end is reported too.
     *
     * @param {string} name
     * @param {{startedAt?: number, detail?: Record<string, string | number | boolean | null>, onLate?: (ms: number) => void}} [options]
     * @returns {MetabrowserEventWait}
     */
    function wait(name, options = {}) {
      const at = options.startedAt ?? env.now();
      /** @type {WaitState} */
      const state = {
        name,
        at,
        late: false,
        done: false,
        timer: null,
        hiddenMs: 0,
        hiddenSince: hidden ? env.now() : null,
        detail: options.detail,
        onLate: options.onLate,
      };
      waits.add(state);
      arm(state);
      return Object.freeze({
        startedAt: at,
        isLate: () => state.late,
        /** @param {"ok" | "failed" | "cancelled" | "never_completed"} [outcome] */
        end(outcome = "ok") {
          if (state.done) {
            return;
          }
          state.done = true;
          waits.delete(state);
          if (state.timer !== null) {
            env.clearTimeout(state.timer);
            state.timer = null;
          }
          if (state.late) {
            enqueue({
              type: "wait",
              event: "end",
              name,
              client: page,
              dur_ms: tenths(env.now() - state.at),
              outcome,
              attrs: waitAttrs(state),
            });
          }
        },
      });
    }

    /**
     * The page was hidden, or shown again: the waits' late timers stop while it is hidden
     * and go on, for the shown time each has left, when it is shown.
     *
     * @param {boolean} nowHidden
     */
    function visibility(nowHidden) {
      if (nowHidden === hidden) {
        return;
      }
      hidden = nowHidden;
      const now = env.now();
      for (const state of waits) {
        if (hidden) {
          state.hiddenSince = now;
        } else if (state.hiddenSince !== null) {
          state.hiddenMs += now - state.hiddenSince;
          state.hiddenSince = null;
        }
        arm(state);
      }
    }

    /** @param {WaitState} state */
    function waitAttrs(state) {
      /** @type {MetabrowserEventReport["attrs"]} */
      const attrs = { threshold_ms: settings.late_ms };
      const hiddenMs = hiddenFor(state, env.now());
      if (hiddenMs > 0) {
        attrs.hidden = true;
        attrs.hidden_ms = tenths(hiddenMs);
      }
      if (state.detail !== undefined) {
        attrs.detail = state.detail;
      }
      return attrs;
    }

    /**
     * A frame or task that blocked the main thread, as the browser reported it.
     *
     * @param {{duration: number, startTime: number, blockingDuration?: number, scripts?: ReadonlyArray<{duration?: number, sourceFunctionName?: string, sourceURL?: string, invoker?: string}>}} entry
     */
    function blocked(entry) {
      if (entry.duration < settings.freeze_ms) {
        return;
      }
      /** @type {Record<string, string | number | boolean | null>} */
      const detail = { at_ms: Math.round(entry.startTime) };
      if (typeof entry.blockingDuration === "number") {
        detail.blocking_ms = Math.round(entry.blockingDuration);
      }
      const scripts = [...(entry.scripts ?? [])].sort(
        (left, right) => (right.duration ?? 0) - (left.duration ?? 0),
      );
      const worst = scripts[0];
      if (worst !== undefined) {
        detail.function = String(worst.sourceFunctionName || "(anonymous)").slice(0, 200);
        if (worst.sourceURL) {
          try {
            detail.source = new URL(worst.sourceURL, env.origin).pathname.slice(0, 200);
          } catch {
            // A source the browser names oddly is left out.
          }
        }
        if (worst.invoker) {
          detail.invoker = String(worst.invoker).slice(0, 200);
        }
      }
      enqueue({
        type: "render",
        event: "end",
        name: "blocked",
        client: page,
        dur_ms: tenths(entry.duration),
        outcome: "ok",
        attrs: { threshold_ms: settings.freeze_ms, detail },
      });
    }

    /**
     * Requests to /api/ that answered before the reporter was there, from Resource
     * Timing: those slower than `slow_ms` are reported, with no client ID.
     *
     * @param {ReadonlyArray<{name: string, initiatorType: string, duration: number, responseStatus?: number, serverTiming?: ReadonlyArray<{name: string, duration: number}>}>} entries
     */
    function earlier(entries) {
      for (const entry of entries) {
        if (entry.duration < settings.slow_ms) {
          continue;
        }
        if (entry.initiatorType !== "fetch" && entry.initiatorType !== "xmlhttprequest") {
          continue;
        }
        let path;
        try {
          const url = new URL(entry.name, env.origin);
          if (url.origin !== env.origin) {
            continue;
          }
          path = url.pathname;
        } catch {
          continue;
        }
        if (
          !path.startsWith("/api/") ||
          path === settings.route ||
          settings.long_lived.some((prefix) => path.startsWith(prefix))
        ) {
          continue;
        }
        /** @type {MetabrowserEventReport["attrs"]} */
        const attrs = { threshold_ms: settings.slow_ms, detail: { source: "resource_timing" } };
        if (typeof entry.responseStatus === "number" && entry.responseStatus > 0) {
          attrs.status = entry.responseStatus;
        }
        const srv = entry.serverTiming?.find((timing) => timing.name === "srv");
        if (srv !== undefined) {
          attrs.server_ms = tenths(srv.duration);
        }
        enqueue({
          type: "fetch",
          event: "end",
          name: path,
          client: page,
          dur_ms: tenths(entry.duration),
          outcome: "ok",
          attrs,
        });
      }
    }

    /** The page is being left: what is late and still open never completed. */
    function leaving() {
      const now = env.now();
      for (const state of waits) {
        if (state.late && !state.done) {
          state.done = true;
          enqueue({
            type: "wait",
            event: "end",
            name: state.name,
            client: page,
            dur_ms: tenths(now - state.at),
            outcome: "never_completed",
            attrs: waitAttrs(state),
          });
        }
      }
      for (const [id, entry] of pending) {
        if (entry.reported) {
          enqueue({
            type: "fetch",
            event: "end",
            name: entry.name,
            client: id,
            dur_ms: tenths(now - entry.at),
            outcome: "never_completed",
            attrs: { threshold_ms: settings.slow_ms },
          });
        }
      }
      pending.clear();
      if (sweepTimer !== null) {
        env.clearTimeout(sweepTimer);
        sweepTimer = null;
      }
      void flush();
    }

    return Object.freeze({
      page,
      settings,
      tag,
      started,
      settled,
      wait,
      visibility,
      blocked,
      earlier,
      leaving,
      flush,
      /** What is queued and not yet sent: for the browserless session. */
      queued: () => queue.slice(),
    });
  }

  /**
   * Wrap *fetch* so every request the reporter tags carries its ID and is timed. A
   * request it does not tag goes to *fetch* untouched.
   *
   * @param {typeof fetch} fetchImpl
   * @param {MetabrowserEventReporter} reporter
   * @returns {typeof fetch}
   */
  function wrapFetch(fetchImpl, reporter) {
    const header = reporter.settings.header;
    return (input, init) => {
      const isRequest = typeof Request !== "undefined" && input instanceof Request;
      const url = typeof input === "string" ? input : isRequest ? input.url : String(input);
      const method = init?.method ?? (isRequest ? input.method : "GET");
      const request = init?.mode === "no-cors" ? null : reporter.tag(url, method);
      if (request === null) {
        return fetchImpl(input, init);
      }
      const headers = new Headers(init?.headers ?? (isRequest ? input.headers : undefined));
      headers.set(header, request.id);
      const sent = fetchImpl(input, { ...init, headers });
      reporter.started(request);
      sent.then(
        (response) =>
          reporter.settled(request, {
            status: response.status,
            serverTiming: response.headers?.get?.("server-timing") ?? null,
          }),
        (error) => reporter.settled(request, { error: error ?? { name: "Error" } }),
      );
      return sent;
    };
  }

  // ── Details ─────────────────────────────────────────────────────────────

  /** The most lines each part of the panel shows; the JSON links have the rest. */
  const DETAIL_LINES = 5;

  /**
   * @param {string} route
   * @param {Record<string, string | number | undefined>} params
   */
  function withQuery(route, params) {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") {
        search.set(key, String(value));
      }
    }
    const text = search.toString();
    return text ? `${route}?${text}` : route;
  }

  /**
   * Where the panel reads from: the failures around *query*'s window, and the page's
   * own records and what the server is running now.
   *
   * @param {MetabrowserEventDetailsQuery} query
   */
  function detailRoutes(query) {
    return {
      failures: withQuery("/api/event-log/failures", { since: query.since, until: query.until }),
      page: withQuery("/api/event-log", { client: query.client, limit: 200 }),
    };
  }

  /** @param {unknown} value */
  const record = (value) =>
    value !== null && typeof value === "object"
      ? /** @type {Record<string, unknown>} */ (value)
      : {};
  /** @param {unknown} value */
  const list = (value) => (Array.isArray(value) ? /** @type {unknown[]} */ (value) : []);
  /** @param {unknown} value */
  const words = (value) => (typeof value === "string" ? value : "");
  /** @param {unknown} value */
  const number = (value) => (typeof value === "number" && Number.isFinite(value) ? value : null);

  /**
   * What the Details panel says, from the answers of `/api/event-log/failures` and
   * `/api/event-log?client=<page>`: what the server is still running, the failures by
   * cause with their addresses and latest calls, the last probe of GitHub, and the
   * page's own slow, failed, or unfinished records. Either answer may be null, when its
   * request failed.
   *
   * @param {unknown} failures
   * @param {unknown} pageLog
   * @param {{slowMs: number, page?: string}} options
   * @returns {MetabrowserEventDetails}
   */
  function describeDetails(failures, pageLog, options) {
    const page = options.page ?? "";
    /** @param {unknown} client */
    const ours = (client) =>
      page !== "" &&
      typeof client === "string" &&
      (client === page || client.startsWith(`${page}-`));
    const failed = record(failures);
    const logged = record(pageLog);
    const running = list(logged.open)
      .map(record)
      .filter((span) => span.kind !== "loop")
      .map((span) => ({
        kind: words(span.kind),
        name: words(span.name),
        age_ms: number(span.age_ms) ?? 0,
        mine: ours(span.client),
      }))
      .sort((left, right) => Number(right.mine) - Number(left.mine) || right.age_ms - left.age_ms)
      .slice(0, DETAIL_LINES);
    const causes = list(failed.causes)
      .map(record)
      .slice(0, DETAIL_LINES)
      .map((group) => ({
        cause: words(group.cause),
        count: number(group.count) ?? 0,
        last: words(group.last),
        message: words(group.message),
        addresses: list(group.addresses).map(words).filter(Boolean),
        examples: list(group.examples)
          .map(record)
          .map((example) => ({
            kind: words(example.kind),
            name: words(example.name),
            outcome: words(example.outcome),
            dur_ms: number(example.dur_ms),
            ts: words(example.ts),
          })),
      }));
    const probeRecord = failed.probe === null ? null : record(failed.probe);
    const probe =
      probeRecord === null || Object.keys(probeRecord).length === 0
        ? null
        : {
            target: words(probeRecord.target),
            verdict: words(probeRecord.verdict),
            ts: words(probeRecord.ts),
            addresses: list(probeRecord.addresses)
              .map(record)
              .map((address) => ({
                address: words(address.address),
                result: words(address.result),
                ms: number(address.ms),
              })),
          };
    const mine = list(logged.events)
      .map(record)
      .filter((event) => {
        const outcome = words(event.outcome);
        const duration = number(event.dur_ms) ?? 0;
        // A page reports only what was slow, late, or frozen, at its own threshold, so
        // each of its reports is listed; the server's records, past the slow threshold.
        return (
          (event.kind === "browser" && event.event !== "mark") ||
          (event.event === "end" && outcome !== "ok" && outcome !== "") ||
          (event.event === "open" && duration >= options.slowMs) ||
          (event.event === "end" && duration >= options.slowMs)
        );
      })
      .slice(0, DETAIL_LINES)
      .map((event) => {
        const attrs = record(event.attrs);
        return {
          event: words(event.event),
          kind: words(event.kind),
          name: words(event.name),
          outcome: words(event.outcome) || null,
          dur_ms: number(event.dur_ms),
          cause: words(attrs.cause) || null,
          ts: words(event.ts),
        };
      });
    const absent = failed.state === "absent" && logged.state === "absent";
    return {
      log: absent ? "absent" : failures === null && pageLog === null ? "unreadable" : "present",
      running,
      causes,
      failures: number(failed.failures) ?? 0,
      since: words(failed.since),
      probe,
      mine,
    };
  }

  /** @param {number | null} ms */
  function duration(ms) {
    if (ms === null) {
      return "";
    }
    return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
  }

  /** @param {string} stamp */
  function clock(stamp) {
    const moment = Date.parse(stamp);
    return Number.isFinite(moment)
      ? new Date(moment).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      : "";
  }

  /**
   * @param {string} tag
   * @param {string} className
   * @param {Array<Node | string>} children
   */
  function element(tag, className, children = []) {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    node.append(...children);
    return node;
  }

  /** @param {Array<string>} parts */
  const joined = (parts) => parts.filter(Boolean).join(" · ");

  /**
   * The lines of *details*, as the panel shows them: each a heading and its items.
   *
   * @param {MetabrowserEventDetails} details
   * @returns {Array<{heading: string, items: string[]}>}
   */
  function detailLines(details) {
    /** @type {Array<{heading: string, items: string[]}>} */
    const parts = [];
    if (details.log === "off") {
      return [
        {
          heading: "The event log is off on this server",
          items: [
            "Nothing this server does is recorded, so there is nothing to show here.",
            ...(details.reason ? [`Why: ${details.reason}`] : []),
          ],
        },
      ];
    }
    if (details.log === "absent") {
      return [{ heading: "The event log is off on this server", items: [] }];
    }
    if (details.log === "unreadable") {
      return [{ heading: "The event log could not be read", items: [] }];
    }
    if (details.running.length > 0) {
      parts.push({
        heading: "Still running",
        items: details.running.map((span) => joined([span.name, `for ${duration(span.age_ms)}`])),
      });
    }
    for (const group of details.causes) {
      parts.push({
        heading: `${group.cause.replaceAll("_", " ")}: ${group.count} in the window`,
        items: [
          group.message,
          group.addresses.length > 0 ? `Addresses: ${group.addresses.join(", ")}` : "",
          ...group.examples.map((example) =>
            joined([example.name, example.outcome, duration(example.dur_ms), clock(example.ts)]),
          ),
        ].filter(Boolean),
      });
    }
    if (details.probe !== null) {
      parts.push({
        heading: `Probe of ${details.probe.target}: ${details.probe.verdict.replaceAll("_", " ")}`,
        items: details.probe.addresses.map((address) =>
          joined([address.address, address.result, duration(address.ms)]),
        ),
      });
    }
    if (details.mine.length > 0) {
      parts.push({
        heading: "This page’s slow or unfinished work",
        items: details.mine.map((event) =>
          joined([
            event.name,
            event.event === "open" ? "still running" : (event.outcome ?? ""),
            event.cause?.replaceAll("_", " ") ?? "",
            duration(event.dur_ms),
            clock(event.ts),
          ]),
        ),
      });
    }
    if (parts.length === 0) {
      parts.push({ heading: "Nothing slow or failed is on record for this", items: [] });
    }
    return parts;
  }

  /**
   * What the panel says on a server that writes no log.
   *
   * @type {MetabrowserEventDetails}
   */
  const OFF = Object.freeze({
    log: "off",
    running: [],
    causes: [],
    failures: 0,
    since: "",
    probe: null,
    mine: [],
  });

  /** @param {Array<{heading: string, items: string[]}>} parts */
  function detailSections(parts) {
    return parts.map((part) =>
      element("div", "event-log-details-part", [
        element("p", "event-log-details-heading", [part.heading]),
        ...(part.items.length === 0
          ? []
          : [
              element(
                "ul",
                "event-log-details-items",
                part.items.map((item) => element("li", "", [item])),
              ),
            ]),
      ]),
    );
  }

  /**
   * Fill *panel* with the Details for *query*: a note while the log is read, then its
   * lines and links to the records as JSON. Resolves when painted; an aborted *signal*
   * leaves the panel as it is.
   *
   * @param {HTMLElement} panel
   * @param {MetabrowserEventDetailsQuery} query
   * @param {{fetch?: typeof fetch, signal?: AbortSignal, slowMs?: number, log?: boolean, offReason?: string | null, openCommand?: string, openMenu?: string | null}} [options]
   *   `log` false: this server writes no log, so the panel says so, with *offReason* (the
   *   server's own words for why) and reads nothing, since what a log directory still holds
   *   is from an earlier server and not about this.
   */
  async function showDetails(panel, query, options = {}) {
    if (options.log === false) {
      panel.replaceChildren(
        ...detailSections(detailLines({ ...OFF, reason: options.offReason ?? null })),
      );
      return;
    }
    const fetchImpl = options.fetch ?? globalThis.fetch.bind(globalThis);
    const routes = detailRoutes(query);
    panel.replaceChildren(element("p", "event-log-details-note", ["Reading the event log…"]));
    /** @param {string} route */
    const read = async (route) => {
      try {
        const response = await fetchImpl(route, {
          headers: { accept: "application/json" },
          signal: options.signal,
        });
        return response.ok ? /** @type {unknown} */ (await response.json()) : null;
      } catch {
        return null;
      }
    };
    const [failures, pageLog] = await Promise.all([read(routes.failures), read(routes.page)]);
    if (options.signal?.aborted) {
      return;
    }
    const details = describeDetails(failures, pageLog, {
      slowMs: options.slowMs ?? window.METABROWSER_SETTINGS?.EVENT_REPORTS?.slow_ms ?? 2000,
      page: query.client,
    });
    const sections = detailSections(detailLines(details));
    /** @param {string} href @param {string} label */
    const link = (href, label) => {
      const anchor = element("a", "", [label]);
      anchor.setAttribute("href", href);
      anchor.setAttribute("target", "_blank");
      anchor.setAttribute("rel", "noopener");
      return anchor;
    };
    const links = element("p", "event-log-details-links", [
      link(routes.failures, "Failures as JSON"),
      ...(query.client ? [" · ", link(routes.page, "This page’s records as JSON")] : []),
    ]);
    // The whole log is a Metabrowser window on a directory of the server's machine, which a
    // page cannot open, so the panel names what does: the app's menu item where the app
    // started this server, and the command otherwise.
    const reports = window.METABROWSER_SETTINGS?.EVENT_REPORTS;
    const menu = options.openMenu !== undefined ? options.openMenu : (reports?.open_menu ?? null);
    const command = options.openCommand ?? reports?.open_command;
    const how = menu
      ? element("span", "", [menu])
      : command
        ? element("code", "", [command])
        : null;
    panel.replaceChildren(
      ...sections,
      links,
      ...(how
        ? [element("p", "event-log-details-open", ["Browse the whole log in Metabrowser: ", how])]
        : []),
    );
  }

  /** The reporter this page runs, or null where there is no namespace to attach to. */
  function install() {
    const settings = window.METABROWSER_SETTINGS?.EVENT_REPORTS;
    const mb = window.metabrowser;
    if (!settings || !mb || mb.eventReports) {
      return null;
    }
    const send = window.fetch.bind(window);
    const reporter = createReporter({
      settings,
      origin: window.location.origin,
      path: () => window.location.pathname,
      now: () => performance.now(),
      setTimeout: (callback, ms) => window.setTimeout(callback, ms),
      clearTimeout: (id) => window.clearTimeout(/** @type {number} */ (id)),
      send: (route, body) =>
        send(route, {
          method: "POST",
          keepalive: true,
          credentials: "same-origin",
          headers: { "content-type": "application/json" },
          body,
        }),
      warn: (...args) => console.warn(...args),
      hidden: () => document.visibilityState === "hidden",
    });
    // A hidden page's waits are not late for being hidden, with or without a log: the late
    // line the page shows is told by the same timer.
    document.addEventListener("visibilitychange", () => {
      const hiddenNow = document.visibilityState === "hidden";
      reporter.visibility(hiddenNow);
      if (hiddenNow) {
        void reporter.flush();
      }
    });
    if (settings.log) {
      window.fetch = wrapFetch(send, reporter);
      try {
        reporter.earlier(
          /** @type {ReadonlyArray<PerformanceResourceTiming>} */ (
            /** @type {unknown} */ (performance.getEntriesByType("resource"))
          ),
        );
      } catch {
        // No Resource Timing: requests before the reporter go unreported.
      }
      const supported = globalThis.PerformanceObserver?.supportedEntryTypes ?? [];
      const type = supported.includes("long-animation-frame")
        ? "long-animation-frame"
        : supported.includes("longtask")
          ? "longtask"
          : null;
      if (type !== null) {
        try {
          new PerformanceObserver((entries) => {
            for (const entry of entries.getEntries()) {
              reporter.blocked(
                /** @type {Parameters<MetabrowserEventReporter["blocked"]>[0]} */ (
                  /** @type {unknown} */ (entry)
                ),
              );
            }
          }).observe({ type, buffered: true });
        } catch {
          // An engine that lists the type and refuses it reports no freezes.
        }
      }
      // A page kept in the back/forward cache is not left: its waits may still end when it
      // is restored, so only what is queued is sent. One that is unloaded is left.
      window.addEventListener("pagehide", (event) => {
        if (/** @type {PageTransitionEvent} */ (event).persisted) {
          void reporter.flush();
        } else {
          reporter.leaving();
        }
      });
    }
    const slowMs = settings.slow_ms;
    /**
     * @param {HTMLElement} panel
     * @param {MetabrowserEventDetailsQuery} query
     * @param {{signal?: AbortSignal}} [options]
     */
    const details = async (panel, query, options) => {
      // What this page has queued is sent first, so its own late waits are in what is read.
      await reporter.flush();
      return showDetails(panel, query, {
        ...options,
        slowMs,
        log: settings.log,
        offReason: settings.off_reason ?? null,
      });
    };
    mb.eventReports = Object.freeze({
      page: reporter.page,
      lateMs: settings.late_ms,
      failureWindowS: settings.failure_window_s,
      wait: reporter.wait,
      showDetails: details,
    });
    return reporter;
  }

  window.MetabrowserEventReports = Object.freeze({
    createReporter,
    wrapFetch,
    describeDetails,
    detailLines,
    detailRoutes,
    showDetails,
    serverMs,
  });
  install();
})();
