#!/usr/bin/env node

// Dependency-free Chrome driver for one browser-performance profile.
//
// It uses Chrome DevTools Protocol directly rather than adding an automation
// library to the product or development dependency graph. Input dispatched by
// CDP enters Chromium's normal input pipeline and is trusted by the document,
// which makes Event Timing and the profiler's interaction-coverage gate usable.

const childProcess = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const DEFAULT_TIMEOUT_MS = 180_000;
const DEFAULT_VIEWPORT = { width: 1600, height: 900 };
const BROWSER_STARTUP_SETTLE_MS = 500;
const CDP_COMMAND_TIMEOUT_MS = 15_000;
const CHROME_EXIT_GRACE_MS = 2_000;
const CLIENT_COMPLETION_SETTLE_MS = 1_000;
const DEFERRED_CANDIDATE_ROWS = 32;
const DEVTOOLS_START_TIMEOUT_MS = 15_000;
const FIRST_ROW_TIMEOUT_MS = 30_000;
const INPUT_PULSE_INTERVAL_MS = 250;
const INPUT_SENTINEL_ID = "metabrowser-performance-input-sentinel";
const INTERACTION_OBSERVER_SETTLE_MS = 100;
const MAX_DEFERRED_FETCHES_IN_FLIGHT = 2;
const MIN_DEFERRED_STRESS_FILES = 3;
const PROFILE_EXPORT_ATTEMPTS = 3;
const QUIESCENCE_POLL_MS = 100;
const QUIESCENCE_STABLE_POLLS = 3;
const STDERR_RETENTION_CHARS = 32_000;
const CHROME_CANDIDATES = [
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
];

function usage() {
  return [
    "Usage: capture-browser.js --url URL --probe FILE --output FILE [options]",
    "",
    "Options:",
    "  --chrome FILE       Chrome or Chromium executable",
    "  --headed            Show the browser window instead of using new headless mode",
    "  --timeout-ms N      Application-settle timeout (default 180000)",
    "  --width N           Viewport width (default 1600)",
    "  --height N          Viewport height (default 900)",
    "  --scenario NAME     Interaction scenario: git-revisions",
  ].join("\n");
}

function parseArgs(argv) {
  const options = {
    chrome: "",
    headed: false,
    height: DEFAULT_VIEWPORT.height,
    output: "",
    probe: "",
    scenario: "",
    timeoutMs: DEFAULT_TIMEOUT_MS,
    url: "",
    width: DEFAULT_VIEWPORT.width,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--help" || argument === "-h") {
      options.help = true;
      continue;
    }
    if (argument === "--headed") {
      options.headed = true;
      continue;
    }
    const value = argv[index + 1];
    if (!value) {
      throw new Error(`missing value for ${argument}`);
    }
    index += 1;
    if (argument === "--chrome") {
      options.chrome = value;
    } else if (argument === "--height") {
      options.height = Number(value);
    } else if (argument === "--output") {
      options.output = value;
    } else if (argument === "--probe") {
      options.probe = value;
    } else if (argument === "--scenario") {
      options.scenario = value;
    } else if (argument === "--timeout-ms") {
      options.timeoutMs = Number(value);
    } else if (argument === "--url") {
      options.url = value;
    } else if (argument === "--width") {
      options.width = Number(value);
    } else {
      throw new Error(`unknown argument: ${argument}`);
    }
  }
  if (options.help) {
    return options;
  }
  for (const field of ["url", "probe", "output"]) {
    if (!options[field]) {
      throw new Error(`--${field} is required`);
    }
  }
  for (const field of ["height", "timeoutMs", "width"]) {
    if (!Number.isFinite(options[field]) || options[field] <= 0) {
      throw new Error(`--${field === "timeoutMs" ? "timeout-ms" : field} must be positive`);
    }
  }
  if (options.scenario && options.scenario !== "git-revisions") {
    throw new Error(`unknown scenario: ${options.scenario}`);
  }
  return options;
}

function chromeExecutable(requested) {
  const candidates = requested ? [requested] : CHROME_CANDIDATES;
  const found = candidates.find((candidate) => fs.existsSync(candidate));
  if (!found) {
    throw new Error("Chrome or Chromium was not found; pass --chrome FILE");
  }
  return path.resolve(found);
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function waitFor(check, timeoutMs, description) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const value = await check();
      if (value) {
        return value;
      }
    } catch (error) {
      lastError = error;
    }
    await delay(QUIESCENCE_POLL_MS);
  }
  const suffix = lastError ? `: ${String(lastError)}` : "";
  throw new Error(`timed out waiting for ${description}${suffix}`);
}

function launchChrome(executable, options, profileDirectory) {
  const chromeArgs = [
    `--user-data-dir=${profileDirectory}`,
    "--remote-debugging-port=0",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-sync",
    `--window-size=${options.width},${options.height}`,
  ];
  if (!options.headed) {
    chromeArgs.push("--headless=new", "--hide-scrollbars");
  }
  chromeArgs.push("about:blank");
  return childProcess.spawn(executable, chromeArgs, {
    stdio: ["ignore", "ignore", "pipe"],
  });
}

function activateHeadedChrome(executable, headed) {
  if (!headed || process.platform !== "darwin") {
    return;
  }
  const application = executable.includes("Chromium.app") ? "Chromium" : "Google Chrome";
  const result = childProcess.spawnSync("open", ["-a", application], { stdio: "ignore" });
  if (result.error || result.status !== 0) {
    throw new Error(
      `could not foreground ${application}: ${String(result.error || result.status)}`,
    );
  }
}

async function devtoolsEndpoint(process, timeoutMs) {
  let stderr = "";
  process.stderr.setEncoding("utf8");
  process.stderr.on("data", (chunk) => {
    stderr = `${stderr}${chunk}`.slice(-STDERR_RETENTION_CHARS);
  });
  return waitFor(
    () => {
      if (process.exitCode !== null) {
        throw new Error(`Chrome exited ${process.exitCode}: ${stderr.trim()}`);
      }
      const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      return match ? match[1] : null;
    },
    timeoutMs,
    "Chrome DevTools endpoint",
  );
}

class CdpSession {
  constructor(webSocketUrl) {
    this.listeners = new Map();
    this.nextId = 1;
    this.pending = new Map();
    this.socket = new WebSocket(webSocketUrl);
    this.opened = new Promise((resolve, reject) => {
      this.socket.addEventListener("open", resolve, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
    });
    this.socket.addEventListener("message", (event) => {
      const message = JSON.parse(String(event.data));
      if (!message.id) {
        for (const listener of this.listeners.get(message.method) || []) {
          listener(message.params || {});
        }
        return;
      }
      const pending = this.pending.get(message.id);
      if (!pending) {
        return;
      }
      this.pending.delete(message.id);
      clearTimeout(pending.timeout);
      if (message.error) {
        pending.reject(new Error(`${pending.method}: ${message.error.message}`));
      } else {
        pending.resolve(message.result || {});
      }
    });
    this.socket.addEventListener("close", () => {
      for (const pending of this.pending.values()) {
        clearTimeout(pending.timeout);
        pending.reject(new Error(`${pending.method}: Chrome DevTools connection closed`));
      }
      this.pending.clear();
    });
  }

  async send(method, params = {}) {
    await this.opened;
    const id = this.nextId;
    this.nextId += 1;
    const result = new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`${method}: Chrome DevTools command timed out`));
      }, CDP_COMMAND_TIMEOUT_MS);
      this.pending.set(id, { method, reject, resolve, timeout });
    });
    this.socket.send(JSON.stringify({ id, method, params }));
    return result;
  }

  on(method, listener) {
    const listeners = this.listeners.get(method) || [];
    listeners.push(listener);
    this.listeners.set(method, listeners);
  }

  close() {
    this.socket.close();
  }
}

async function pageTarget(browserEndpoint, url) {
  const endpoint = new URL(browserEndpoint);
  const base = `http://${endpoint.host}`;
  const response = await fetch(`${base}/json/new?${encodeURIComponent(url)}`, { method: "PUT" });
  if (!response.ok) {
    throw new Error(`could not create Chrome target: HTTP ${response.status}`);
  }
  return response.json();
}

async function evaluate(session, expression, awaitPromise = false) {
  const result = await session.send("Runtime.evaluate", {
    awaitPromise,
    expression,
    returnByValue: true,
    userGesture: true,
  });
  if (result.exceptionDetails) {
    const detail = result.exceptionDetails.exception?.description || result.exceptionDetails.text;
    throw new Error(`page evaluation failed: ${detail}`);
  }
  return result.result?.value;
}

async function installInputSentinel(session) {
  return evaluate(
    session,
    `(() => {
      const existing = document.getElementById(${JSON.stringify(INPUT_SENTINEL_ID)});
      existing?.remove();
      const target = document.createElement("span");
      target.id = ${JSON.stringify(INPUT_SENTINEL_ID)};
      target.setAttribute("aria-hidden", "true");
      Object.assign(target.style, {
        backgroundColor: "rgba(0, 0, 0, 0.001)",
        height: "3px",
        left: "0",
        pointerEvents: "auto",
        position: "fixed",
        top: "0",
        width: "3px",
        zIndex: "2147483647",
      });
      target.addEventListener("click", (event) => {
        target.dataset.pulse = target.dataset.pulse === "a" ? "b" : "a";
        target.style.backgroundColor = target.dataset.pulse === "a"
          ? "rgba(0, 0, 0, 0.001)"
          : "rgba(255, 255, 255, 0.001)";
        event.stopPropagation();
      });
      document.body.append(target);
      const rect = target.getBoundingClientRect();
      return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
    })()`,
  );
}

async function dispatchTrustedClickAtPoint(session, point) {
  if (!point) {
    throw new Error("could not install the trusted-input sentinel");
  }
  await session.send("Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x: point.x,
    y: point.y,
  });
  await session.send("Input.dispatchMouseEvent", {
    button: "left",
    buttons: 1,
    clickCount: 1,
    type: "mousePressed",
    x: point.x,
    y: point.y,
  });
  await session.send("Input.dispatchMouseEvent", {
    button: "left",
    buttons: 0,
    clickCount: 1,
    type: "mouseReleased",
    x: point.x,
    y: point.y,
  });
}

async function pointForSelector(session, selector, index = 0) {
  return evaluate(
    session,
    `(() => {
      const element = document.querySelectorAll(${JSON.stringify(selector)})[${index}];
      if (!(element instanceof HTMLElement)) return null;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return null;
      return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
    })()`,
  );
}

async function dispatchTrustedClickForSelector(session, selector, index = 0) {
  const point = await pointForSelector(session, selector, index);
  if (!point) {
    throw new Error(`could not click ${selector}[${index}]`);
  }
  await dispatchTrustedClickAtPoint(session, point);
}

async function dispatchTrustedPointerForSelector(session, selector, index = 0) {
  const point = await pointForSelector(session, selector, index);
  if (!point) {
    throw new Error(`could not point at ${selector}[${index}]`);
  }
  await session.send("Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x: point.x,
    y: point.y,
  });
}

async function awaitNextPaint(session) {
  return evaluate(
    session,
    `new Promise((resolve) => requestAnimationFrame(() =>
      requestAnimationFrame(() => resolve(performance.now()))))`,
    true,
  );
}

async function startGitBlankFrameMonitor(session) {
  return evaluate(
    session,
    `(() => {
      const key = "__metabrowserGitBlankMonitor";
      cancelAnimationFrame(window[key]?.frame || 0);
      const state = {
        blankDurationMs: 0,
        blankFrames: 0,
        blankStartedAt: null,
        frame: 0,
        running: true,
      };
      const sample = (now) => {
        if (!state.running) return;
        const visible = Boolean(document.querySelector("#preview-pane .git-commit-view"));
        if (visible) {
          if (state.blankStartedAt !== null) {
            state.blankDurationMs += now - state.blankStartedAt;
            state.blankStartedAt = null;
          }
        } else {
          state.blankFrames += 1;
          if (state.blankStartedAt === null) state.blankStartedAt = now;
        }
        state.frame = requestAnimationFrame(sample);
      };
      state.frame = requestAnimationFrame(sample);
      window[key] = state;
      return true;
    })()`,
  );
}

async function stopGitBlankFrameMonitor(session) {
  return evaluate(
    session,
    `(() => {
      const state = window.__metabrowserGitBlankMonitor;
      if (!state) return null;
      state.running = false;
      cancelAnimationFrame(state.frame);
      if (state.blankStartedAt !== null) {
        state.blankDurationMs += performance.now() - state.blankStartedAt;
      }
      return {
        blank_duration_ms: Number(state.blankDurationMs.toFixed(2)),
        blank_frames: state.blankFrames,
      };
    })()`,
  );
}

async function gitRow(session, index) {
  return evaluate(
    session,
    `(() => {
      const row = document.querySelectorAll(".git-graph-row")[${index}];
      if (!(row instanceof HTMLElement)) return null;
      return {revision: row.dataset.revision || "", subject: row.textContent || ""};
    })()`,
  );
}

async function waitForGitRevision(session, revision, timeoutMs) {
  await waitFor(
    async () =>
      evaluate(
        session,
        `(() => {
          const selected = document.querySelector(".git-graph-row.selected");
          const sha = document.querySelector("#preview-pane .git-commit-sha")?.textContent?.trim();
          return selected instanceof HTMLElement && selected.dataset.revision ===
            ${JSON.stringify(revision)} && Boolean(sha) &&
            ${JSON.stringify(revision)}.startsWith(sha) &&
            Boolean(document.querySelector(".git-commit-diff .diff-root"));
        })()`,
      ),
    timeoutMs,
    `Git revision ${revision} to render`,
  );
  return awaitNextPaint(session);
}

async function measureGitTransition(session, rowIndex, name, timeoutMs) {
  const row = await gitRow(session, rowIndex);
  if (!row?.revision) {
    throw new Error(`Git row ${rowIndex} is unavailable`);
  }
  const started = await evaluate(session, `({epoch: Date.now(), now: performance.now()})`);
  await startGitBlankFrameMonitor(session);
  await dispatchTrustedClickForSelector(session, ".git-graph-row", rowIndex);
  const paintedAt = await waitForGitRevision(session, row.revision, timeoutMs);
  const blank = await stopGitBlankFrameMonitor(session);
  const snapshot = await evaluate(session, `window.metabrowser.perf.snapshot()`);
  const fetches = snapshot.raw_fetch.filter((sample) => sample.ts >= started.epoch);
  return {
    name,
    revision: row.revision,
    total_ms: Number((paintedAt - started.now).toFixed(2)),
    ...blank,
    fetches: fetches
      .filter(
        (sample) =>
          sample.url.includes("/api/git/commit/") ||
          sample.url.includes("/api/plugin/diff/comparison"),
      )
      .map((sample) => ({
        duration_ms: Number(sample.duration_ms.toFixed(2)),
        server_ms: sample.server_ms,
        size_bytes: sample.size_bytes,
        status: sample.status,
        url: new URL(sample.url, "http://localhost").pathname,
      })),
  };
}

function assertDeferredHydrationHealth(result) {
  if (!result.candidate_revision) {
    throw new Error("candidate_revision is required for deferred hydration validation");
  }
  if (!result.target_revision) {
    throw new Error("target_revision is required for deferred hydration validation");
  }
  if (!Number.isInteger(result.pending_files) || result.pending_files < MIN_DEFERRED_STRESS_FILES) {
    throw new Error(
      `pending_files must exercise active and queued hydration; observed ${result.pending_files}`,
    );
  }
  if (
    !Number.isInteger(result.max_deferred_fetches_in_flight) ||
    result.max_deferred_fetches_in_flight > MAX_DEFERRED_FETCHES_IN_FLIGHT
  ) {
    throw new Error(
      "max_deferred_fetches_in_flight exceeded the deferred hydration bound: " +
        result.max_deferred_fetches_in_flight,
    );
  }
  if (result.fetch_concurrency_keys_overflowed !== 0) {
    throw new Error(
      "fetch_concurrency_keys_overflowed must be zero for complete attribution; observed " +
        result.fetch_concurrency_keys_overflowed,
    );
  }
  if (!Number.isInteger(result.obsolete_successes) || result.obsolete_successes !== 0) {
    throw new Error(
      `obsolete_successes must be zero after revision selection; observed ${result.obsolete_successes}`,
    );
  }
  if (!Number.isInteger(result.aborted_requests) || result.aborted_requests < 1) {
    throw new Error("aborted_requests must prove active retained work was canceled");
  }
  if (result.mounted_comparisons !== 1) {
    throw new Error(`mounted_comparisons must remain one; observed ${result.mounted_comparisons}`);
  }
  for (const field of ["selected_revision", "route_revision", "rendered_revision"]) {
    if (result[field] !== result.target_revision) {
      throw new Error(
        `${field} did not converge on ${result.target_revision}; observed ${result[field] || "none"}`,
      );
    }
  }
}

async function deferredDiffState(session) {
  return evaluate(
    session,
    `(() => {
      const bodies = Array.from(document.querySelectorAll(".diff-file-body"));
      const pendingFiles = bodies.filter((body) =>
        body.children.length === 0 || Boolean(body.querySelector(".diff-progress"))
      ).length;
      const snapshot = window.metabrowser.perf.snapshot();
      return {
        pendingFiles,
        progressFiles: document.querySelectorAll(".diff-progress").length,
        fetchesInFlight: snapshot.fetches_in_flight,
        maxDeferredFetchesInFlight:
          snapshot.fetches_in_flight_max_by_key["/api/plugin/diff/comparison?file"] || 0,
      };
    })()`,
  );
}

async function findDeferredRevision(session, timeoutMs) {
  const rowCount = await evaluate(session, `document.querySelectorAll(".git-graph-row").length`);
  const candidateRows = Math.min(rowCount, DEFERRED_CANDIDATE_ROWS);
  for (let rowIndex = 0; rowIndex < candidateRows; rowIndex += 1) {
    const row = await gitRow(session, rowIndex);
    if (!row?.revision) {
      continue;
    }
    await evaluate(session, `window.metabrowser.perf.reset()`);
    await dispatchTrustedClickForSelector(session, ".git-graph-row", rowIndex);
    await waitForGitRevision(session, row.revision, timeoutMs);
    const state = await deferredDiffState(session);
    if (state.maxDeferredFetchesInFlight > MAX_DEFERRED_FETCHES_IN_FLIGHT) {
      throw new Error(
        `Git revision ${row.revision} launched ${state.maxDeferredFetchesInFlight} ` +
          "simultaneous deferred fetches",
      );
    }
    if (state.pendingFiles >= MIN_DEFERRED_STRESS_FILES) {
      return { rowCount, rowIndex, revision: row.revision, pendingFiles: state.pendingFiles };
    }
    await waitForClientQuiescence(session, timeoutMs);
  }
  throw new Error(
    `Git scenario found no revision with ${MIN_DEFERRED_STRESS_FILES} deferred files ` +
      `in its first ${candidateRows} rows`,
  );
}

async function runDeferredHydrationScenario(session, timeoutMs) {
  const candidate = await findDeferredRevision(session, timeoutMs);
  await waitForClientQuiescence(session, timeoutMs);
  await evaluate(session, `window.metabrowser.perf.reset()`);
  await evaluate(
    session,
    `document.querySelector("#preview-pane")?.scrollTo({
      top: document.querySelector("#preview-pane")?.scrollHeight || 0,
      behavior: "instant"
    })`,
  );
  await waitFor(
    async () => {
      const state = await deferredDiffState(session);
      return state.progressFiles > 0 && state.fetchesInFlight > 0 ? state : null;
    },
    timeoutMs,
    "deferred Git file hydration to start",
  );

  const targetIndex =
    candidate.rowIndex + 1 < candidate.rowCount ? candidate.rowIndex + 1 : candidate.rowIndex - 1;
  const target = await gitRow(session, targetIndex);
  if (!target?.revision) {
    throw new Error("Git deferred hydration scenario has no adjacent target revision");
  }
  const selectedAt = await evaluate(session, `Date.now()`);
  await dispatchTrustedClickForSelector(session, ".git-graph-row", targetIndex);
  await waitForGitRevision(session, target.revision, timeoutMs);
  await waitForClientQuiescence(session, timeoutMs);

  const snapshot = await evaluate(session, `window.metabrowser.perf.snapshot()`);
  const candidateFileFetches = snapshot.raw_fetch.filter((sample) => {
    const url = new URL(sample.url, "http://localhost");
    return (
      url.pathname === "/api/plugin/diff/comparison" &&
      url.searchParams.get("revision") === candidate.revision &&
      url.searchParams.has("file")
    );
  });
  const convergence = await evaluate(
    session,
    `(() => ({
      selected: document.querySelector(".git-graph-row.selected")?.dataset.revision || "",
      rendered: document.querySelector(".git-commit-view")?.dataset.revision || "",
      route: location.pathname.split("/").pop() || "",
      mounts: document.querySelectorAll(".git-commit-diff .diff-root").length
    }))()`,
  );
  return {
    candidate_revision: candidate.revision,
    target_revision: target.revision,
    pending_files: candidate.pendingFiles,
    max_deferred_fetches_in_flight:
      snapshot.fetches_in_flight_max_by_key["/api/plugin/diff/comparison?file"] || 0,
    max_application_fetches_in_flight: snapshot.fetches_in_flight_max,
    fetch_concurrency_keys_overflowed: snapshot.fetch_concurrency_keys_overflowed,
    obsolete_successes: candidateFileFetches.filter(
      (sample) => sample.ts >= selectedAt && sample.status >= 200,
    ).length,
    aborted_requests: candidateFileFetches.filter((sample) => sample.aborted).length,
    mounted_comparisons: convergence.mounts,
    selected_revision: convergence.selected,
    route_revision: convergence.route,
    rendered_revision: convergence.rendered,
  };
}

async function runGitRevisionScenario(session, timeoutMs) {
  await waitFor(
    () => pointForSelector(session, '.tab-btn[data-tab="git"]'),
    timeoutMs,
    "Git navigation tab",
  );
  await dispatchTrustedClickForSelector(session, '.tab-btn[data-tab="git"]');
  await waitFor(
    async () => evaluate(session, `document.querySelectorAll(".git-graph-row").length >= 4`),
    timeoutMs,
    "four Git history rows",
  );

  // Warm the renderer and its on-demand assets before measuring revision-to-revision
  // navigation. Startup asset cost belongs to the load profile, not this scenario.
  const warm = await gitRow(session, 0);
  await dispatchTrustedClickForSelector(session, ".git-graph-row", 0);
  await waitForGitRevision(session, warm.revision, timeoutMs);
  await waitForClientQuiescence(session, timeoutMs);
  await evaluate(session, `window.metabrowser.perf.reset()`);

  const transitions = [];
  transitions.push(await measureGitTransition(session, 1, "cold-1", timeoutMs));
  transitions.push(await measureGitTransition(session, 2, "cold-2", timeoutMs));

  const prepared = await gitRow(session, 3);
  const prefetchStartedAt = await evaluate(session, `Date.now()`);
  await dispatchTrustedPointerForSelector(session, ".git-graph-row", 3);
  await delay(450);
  const preparedTransition = await measureGitTransition(session, 3, "pointer-prepared", timeoutMs);
  transitions.push(preparedTransition);
  await waitForClientQuiescence(session, timeoutMs);
  const profiler = await evaluate(session, `window.metabrowser.perf.snapshot()`);
  const prefetchFetches = profiler.raw_fetch.filter(
    (sample) =>
      sample.ts >= prefetchStartedAt &&
      sample.ts < prefetchStartedAt + 450 &&
      (sample.url.includes("/api/git/commit/") ||
        sample.url.includes("/api/plugin/diff/comparison")),
  );
  const mountedComparisons = await evaluate(
    session,
    `document.querySelectorAll(".git-commit-diff .diff-root").length`,
  );
  if (mountedComparisons !== 1) {
    throw new Error(`Git scenario retained ${mountedComparisons} mounted comparisons`);
  }
  const deferredHydration = await runDeferredHydrationScenario(session, timeoutMs);
  assertDeferredHydrationHealth(deferredHydration);
  return {
    schema: "git-revision-navigation/v1",
    generated_at: new Date().toISOString(),
    scenario: "git-revisions",
    prepared_revision: prepared.revision,
    transitions,
    prefetch_fetches: prefetchFetches,
    mounted_comparisons: mountedComparisons,
    deferred_hydration: deferredHydration,
    profiler,
  };
}

async function removeInputSentinel(session) {
  await evaluate(
    session,
    `document.getElementById(${JSON.stringify(INPUT_SENTINEL_ID)})?.remove()`,
  );
}

async function startTrustedInputPulse(session) {
  const point = await installInputSentinel(session);
  let count = 0;
  let running = true;
  let pulseError = null;
  const completion = (async () => {
    try {
      while (running) {
        await dispatchTrustedClickAtPoint(session, point);
        count += 1;
        await delay(INPUT_PULSE_INTERVAL_MS);
      }
    } catch (error) {
      pulseError = error;
    }
  })();
  return {
    async stop() {
      running = false;
      await completion;
      try {
        if (pulseError) {
          throw pulseError;
        }
        // A fast application can settle during the interval sleep. Send one
        // last controlled paint at the boundary so the stability polls do not
        // create an untested tail in the responsiveness window.
        await dispatchTrustedClickAtPoint(session, point);
        count += 1;
        await delay(INTERACTION_OBSERVER_SETTLE_MS);
        return count;
      } finally {
        await removeInputSentinel(session);
      }
    },
  };
}

async function waitForIndex(url, timeoutMs) {
  const progressUrl = new URL("/api/index/progress", url);
  return waitFor(
    async () => {
      const response = await fetch(progressUrl);
      if (!response.ok) {
        return null;
      }
      const payload = await response.json();
      return payload.status === "done" || payload.status === "truncated" ? payload : null;
    },
    timeoutMs,
    "Metabrowser index completion",
  );
}

async function waitForClientQuiescence(session, timeoutMs) {
  let previousWork = null;
  let stablePolls = 0;
  return waitFor(
    async () => {
      const state = await evaluate(
        session,
        `(() => {
          const snapshot = window.metabrowser?.perf?.snapshot?.();
          if (!snapshot) return null;
          const delivery = snapshot.label_totals
            .filter((row) => row.label === "fileStoreApplySnapshot" ||
              row.label === "fileStoreApplyChange" ||
              row.label === "knownFileCatalog:applyBulkSnapshot" ||
              row.label === "knownFileCatalog:applyCatalogChange")
            .reduce((total, row) => total + row.count, 0);
          return {
            fetchesInFlight: snapshot.fetches_in_flight,
            work: snapshot.measure_samples_seen + delivery,
          };
        })()`,
      );
      if (state?.fetchesInFlight !== 0) {
        stablePolls = 0;
        previousWork = state?.work ?? null;
        return null;
      }
      if (state.work === previousWork) {
        stablePolls += 1;
      } else {
        stablePolls = 0;
      }
      previousWork = state.work;
      return stablePolls >= QUIESCENCE_STABLE_POLLS ? state : null;
    },
    timeoutMs,
    "browser fetch and inventory-delivery quiescence",
  );
}

function assertControlledInputCount(observed, expected) {
  if (observed !== expected) {
    throw new Error("trusted input count differs from the controlled CDP pulse count");
  }
}

async function capture(options) {
  if (typeof WebSocket !== "function") {
    throw new Error("this Node runtime does not provide WebSocket");
  }
  const executable = chromeExecutable(options.chrome);
  const profileDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "metabrowser-chrome-"));
  const chrome = launchChrome(executable, options, profileDirectory);
  let session = null;
  try {
    const browserEndpoint = await devtoolsEndpoint(chrome, DEVTOOLS_START_TIMEOUT_MS);
    // The browser process is not the application. Let Chrome finish its own
    // first blank frame before creating the measured target; otherwise Long
    // Animation Frame attributes process startup to the new page with no
    // scripts, rendering, or resources attached to explain it.
    await delay(BROWSER_STARTUP_SETTLE_MS);
    const target = await pageTarget(browserEndpoint, "about:blank");
    activateHeadedChrome(executable, options.headed);
    session = new CdpSession(target.webSocketDebuggerUrl);
    let pageExceptions = 0;
    session.on("Runtime.exceptionThrown", () => {
      pageExceptions += 1;
    });
    await session.send("Page.enable");
    await session.send("Runtime.enable");
    await session.send("Emulation.setDeviceMetricsOverride", {
      deviceScaleFactor: 1,
      height: options.height,
      mobile: false,
      width: options.width,
    });
    await session.send("Page.navigate", { url: options.url });
    await waitFor(
      async () =>
        evaluate(
          session,
          `document.readyState === "complete" &&
            typeof window.metabrowser?.perf?.snapshot === "function" &&
            Boolean(document.querySelector('[role="treeitem"]'))`,
        ),
      FIRST_ROW_TIMEOUT_MS,
      "application first row and performance recorder",
    );
    if (options.scenario) {
      await waitForIndex(options.url, options.timeoutMs);
      await delay(CLIENT_COMPLETION_SETTLE_MS);
      await waitForClientQuiescence(session, options.timeoutMs);
      const payload = await runGitRevisionScenario(session, options.timeoutMs);
      payload.page_exceptions = pageExceptions;
      if (pageExceptions !== 0) {
        throw new Error(`Git scenario observed ${pageExceptions} uncaught page exception(s)`);
      }
      await session.send("HeapProfiler.enable");
      await session.send("HeapProfiler.collectGarbage");
      const heapUsage = await session.send("Runtime.getHeapUsage");
      payload.js_heap_after_gc_mb = Number((heapUsage.usedSize / (1024 * 1024)).toFixed(1));
      fs.mkdirSync(path.dirname(options.output), { recursive: true });
      fs.writeFileSync(options.output, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
      process.stdout.write(`${options.output}\n`);
      return payload;
    }
    // A single early interaction can miss the exact update storm this loop is
    // meant to catch. Pulse a one-pixel, non-product sentinel from first usable
    // state through client quiescence. The click toggles only its own paint, so
    // Event Timing samples input-to-next-paint latency without changing the
    // application state or adding application work to one side of a comparison.
    const inputPulse = await startTrustedInputPulse(session);
    let inputPulseCount;
    try {
      await waitForIndex(options.url, options.timeoutMs);
      // Completion can arm idle and timeout work (subtree warming, optional
      // assets). Let those callbacks become observable before declaring the
      // client quiet, then require a stable zero-in-flight window.
      await delay(CLIENT_COMPLETION_SETTLE_MS);
      await waitForClientQuiescence(session, options.timeoutMs);
    } finally {
      inputPulseCount = await inputPulse.stop();
    }
    const probe = fs.readFileSync(options.probe, "utf8");
    let payload = null;
    for (let attempt = 0; attempt < PROFILE_EXPORT_ATTEMPTS; attempt += 1) {
      const result = await evaluate(session, probe, true);
      if (typeof result !== "string") {
        throw new Error("browser probe did not return a JSON string");
      }
      payload = JSON.parse(result);
      if (payload.fetches_in_flight === 0) {
        break;
      }
      await waitForClientQuiescence(session, options.timeoutMs);
    }
    if (payload?.fetches_in_flight !== 0) {
      throw new Error("browser did not remain fetch-idle through profile export");
    }
    if (payload.interaction_inputs < 1) {
      throw new Error("CDP interaction did not reach the page as trusted input");
    }
    assertControlledInputCount(payload.interaction_inputs, inputPulseCount);
    payload.page_exceptions = pageExceptions;
    // Close the responsiveness profile before forcing collection. Otherwise
    // measurement-only GC extends the profile after the input pulse stops,
    // dilutes its loading-window coverage, and can appear as product blocking.
    // The retained-heap field is a separate controlled sample by definition.
    await session.send("HeapProfiler.enable");
    await session.send("HeapProfiler.collectGarbage");
    const heapUsage = await session.send("Runtime.getHeapUsage");
    payload.js_heap_after_gc_mb = Number((heapUsage.usedSize / (1024 * 1024)).toFixed(1));
    fs.mkdirSync(path.dirname(options.output), { recursive: true });
    fs.writeFileSync(options.output, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
    process.stdout.write(`${options.output}\n`);
    return payload;
  } finally {
    session?.close();
    chrome.kill("SIGTERM");
    await Promise.race([
      new Promise((resolve) => chrome.once("exit", resolve)),
      delay(CHROME_EXIT_GRACE_MS),
    ]);
    if (chrome.exitCode === null) {
      chrome.kill("SIGKILL");
      await new Promise((resolve) => chrome.once("exit", resolve));
    }
    fs.rmSync(profileDirectory, { force: true, recursive: true });
  }
}

async function main(argv) {
  const options = parseArgs(argv);
  if (options.help) {
    process.stdout.write(`${usage()}\n`);
    return;
  }
  await capture(options);
}

if (require.main === module) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(`${String(error?.stack || error)}\n`);
    process.exitCode = 1;
  });
}

module.exports = {
  assertControlledInputCount,
  assertDeferredHydrationHealth,
  capture,
  chromeExecutable,
  dispatchTrustedClickAtPoint,
  dispatchTrustedClickForSelector,
  parseArgs,
  runGitRevisionScenario,
  startTrustedInputPulse,
  usage,
  waitForClientQuiescence,
};
