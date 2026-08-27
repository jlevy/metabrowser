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
const DEEP_ROUTE_MEASUREMENT_TIMEOUT_MS = 30_000;
// Keep the hydration probe bounded while allowing a moving history to put a
// suitable multi-file revision beyond the first screenful between releases.
const DEFERRED_CANDIDATE_ROWS = 64;
const DEVTOOLS_START_TIMEOUT_MS = 15_000;
const FIRST_ROW_TIMEOUT_MS = 30_000;
const GIT_ROUNDTRIP_ROW_INDEX = 4;
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
    "  --scenario NAME     Interaction scenario: git-revisions, file-views, or git-history-depth",
    "  --history-rows N    Required target row count for git-history-depth",
  ].join("\n");
}

function parseArgs(argv) {
  const options = {
    chrome: "",
    headed: false,
    height: DEFAULT_VIEWPORT.height,
    historyRows: 0,
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
    } else if (argument === "--history-rows") {
      options.historyRows = Number(value);
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
  if (
    options.scenario &&
    !["git-revisions", "file-views", "git-history-depth"].includes(options.scenario)
  ) {
    throw new Error(`unknown scenario: ${options.scenario}`);
  }
  if (options.scenario === "git-history-depth") {
    if (!Number.isInteger(options.historyRows) || options.historyRows <= 0) {
      throw new Error("--history-rows is required and must be a positive integer");
    }
  } else if (options.historyRows !== 0) {
    throw new Error("--history-rows is only valid with --scenario git-history-depth");
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

async function pointForFilePath(session, filePath) {
  return evaluate(
    session,
    `(async () => {
      const row = Array.from(document.querySelectorAll(".tree-item.tree-file[data-path]"))
        .find((candidate) => candidate instanceof HTMLElement &&
          candidate.dataset.path === ${JSON.stringify(filePath)});
      if (!(row instanceof HTMLElement)) return null;
      row.scrollIntoView({block: "center", inline: "nearest"});
      await new Promise((resolve) => requestAnimationFrame(resolve));
      const rect = row.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return null;
      return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
    })()`,
    true,
  );
}

async function dispatchTrustedClickForFilePath(session, filePath) {
  const point = await pointForFilePath(session, filePath);
  if (!point) {
    throw new Error(`could not click file row ${filePath}`);
  }
  await dispatchTrustedClickAtPoint(session, point);
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
        observer: null,
        blankDurationMs: 0,
        blankFrames: 0,
        blankStartedAt: null,
        frame: 0,
        pendingClearedAt: null,
        pendingSeenAt: null,
        running: true,
        startedAt: performance.now(),
      };
      const preview = document.querySelector("#preview-pane");
      const observePending = () => {
        const pending = preview?.classList.contains("preview-navigation-pending") === true;
        const now = performance.now();
        if (pending && state.pendingSeenAt === null) state.pendingSeenAt = now;
        if (!pending && state.pendingSeenAt !== null) state.pendingClearedAt = now;
      };
      state.observer = new MutationObserver(observePending);
      if (preview) {
        state.observer.observe(preview, {
          attributes: true,
          attributeFilter: ["aria-busy", "class", "data-preview-pending-claim"],
        });
      }
      const sample = (now) => {
        if (!state.running) return;
        observePending();
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
      observePending();
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
      state.observer?.disconnect();
      if (state.blankStartedAt !== null) {
        state.blankDurationMs += performance.now() - state.blankStartedAt;
      }
      const preview = document.querySelector("#preview-pane");
      return {
        aria_busy: preview?.getAttribute("aria-busy") === "true",
        blank_duration_ms: Number(state.blankDurationMs.toFixed(2)),
        blank_frames: state.blankFrames,
        pending_active: preview?.classList.contains("preview-navigation-pending") === true,
        pending_clear_ms: state.pendingClearedAt === null ? null :
          Number((state.pendingClearedAt - state.startedAt).toFixed(2)),
        pending_onset_ms: state.pendingSeenAt === null ? null :
          Number((state.pendingSeenAt - state.startedAt).toFixed(2)),
        pending_seen: state.pendingSeenAt !== null,
      };
    })()`,
  );
}

async function startFileBlankFrameMonitor(session) {
  return evaluate(
    session,
    `(() => {
      const key = "__metabrowserFileBlankMonitor";
      const previous = window[key];
      if (previous) {
        previous.running = false;
        cancelAnimationFrame(previous.frame || 0);
        previous.observer?.disconnect();
      }
      const state = {
        blankDurationMs: 0,
        blankFrames: 0,
        blankStartedAt: null,
        frame: 0,
        observer: null,
        pendingClearedAt: null,
        pendingSeenAt: null,
        running: true,
        startedAt: performance.now(),
      };
      const preview = document.querySelector("#preview-pane");
      const observePending = () => {
        const pending = preview?.classList.contains("preview-navigation-pending") === true;
        const now = performance.now();
        if (pending && state.pendingSeenAt === null) state.pendingSeenAt = now;
        if (!pending && state.pendingSeenAt !== null) state.pendingClearedAt = now;
      };
      state.observer = new MutationObserver(observePending);
      if (preview) {
        state.observer.observe(preview, {
          attributes: true,
          attributeFilter: ["aria-busy", "class", "data-preview-pending-claim"],
        });
      }
      const sample = (now) => {
        if (!state.running) return;
        observePending();
        const active = preview?.querySelector('[data-tab-content][data-active-view="true"]');
        const visible = active instanceof HTMLElement &&
          (active.childElementCount > 0 || Boolean(active.textContent?.trim()));
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
      observePending();
      state.frame = requestAnimationFrame(sample);
      window[key] = state;
      return true;
    })()`,
  );
}

async function stopFileBlankFrameMonitor(session) {
  return evaluate(
    session,
    `(() => {
      const state = window.__metabrowserFileBlankMonitor;
      const preview = document.querySelector("#preview-pane");
      if (!state) return null;
      state.running = false;
      cancelAnimationFrame(state.frame);
      state.observer?.disconnect();
      if (state.blankStartedAt !== null) {
        state.blankDurationMs += performance.now() - state.blankStartedAt;
      }
      const now = performance.now();
      return {
        aria_busy: preview?.getAttribute("aria-busy") === "true",
        blank_duration_ms: Number(state.blankDurationMs.toFixed(2)),
        blank_frames: state.blankFrames,
        pending_active: preview?.classList.contains("preview-navigation-pending") === true,
        pending_clear_ms: state.pendingClearedAt === null ? null :
          Number((state.pendingClearedAt - state.startedAt).toFixed(2)),
        pending_onset_ms: state.pendingSeenAt === null ? null :
          Number((state.pendingSeenAt - state.startedAt).toFixed(2)),
        pending_seen: state.pendingSeenAt !== null,
        stopped_at_ms: Number((now - state.startedAt).toFixed(2)),
      };
    })()`,
  );
}

async function fileViewCandidates(session) {
  return evaluate(
    session,
    `(() => {
      const paths = Array.from(document.querySelectorAll(".tree-item.tree-file[data-path]"))
        .filter((row) => row instanceof HTMLElement &&
          !row.classList.contains("tree-item-filter-hidden"))
        .map((row) => row.dataset.path || "");
      const markdown = paths.filter((path) => /\\.(?:md|markdown)$/i.test(path)).sort()[0] || "";
      const sources = paths.filter((path) =>
        /\\.(?:css|html?|js|jsx|mjs|py|rs|sh|toml|ts|tsx)$/i.test(path));
      const structured = paths.filter((path) => /\\.(?:json|ya?ml)$/i.test(path)).sort()[0] || "";
      return {
        markdown,
        sources: Array.from(new Set(sources)).sort().slice(0, 3),
        structured,
      };
    })()`,
  );
}

async function fileViewState(session) {
  return evaluate(
    session,
    `(() => {
      const preview = document.querySelector("#preview-pane");
      const active = preview?.querySelector('[data-tab-content][data-active-view="true"]');
      return {
        activeMounts: preview?.querySelectorAll(
          '[data-plugin-view][data-active-view="true"]'
        ).length || 0,
        activeViewNonempty: active instanceof HTMLElement &&
          (active.childElementCount > 0 || Boolean(active.textContent?.trim())),
        pendingActive: preview?.classList.contains("preview-navigation-pending") === true,
        renderedPath: preview instanceof HTMLElement ? preview.dataset.renderedPath || "" : "",
        renderedView: preview instanceof HTMLElement ? preview.dataset.activeView || "" : "",
        routePath: window.metabrowser.navigation.current()?.path || "",
        selectedPath: document.querySelector(".tree-item.selected")?.dataset.path || "",
      };
    })()`,
  );
}

async function waitForFileView(session, filePath, timeoutMs) {
  const state = await waitFor(
    async () => {
      const current = await fileViewState(session);
      return current.selectedPath === filePath &&
        current.routePath === filePath &&
        current.renderedPath === filePath &&
        current.renderedView &&
        current.activeMounts === 1 &&
        current.activeViewNonempty &&
        !current.pendingActive
        ? current
        : null;
    },
    timeoutMs,
    `file view ${filePath} to reach painted readiness`,
  );
  const paintedAt = await awaitNextPaint(session);
  return { paintedAt, state };
}

function assertFileTransitionHealth(result) {
  if (!result.path) {
    throw new Error("path is required for file-view validation");
  }
  for (const field of ["selected_path", "route_path", "rendered_path"]) {
    if (result[field] !== result.path) {
      throw new Error(
        `${field} did not converge on ${result.path}; observed ${result[field] || "none"}`,
      );
    }
  }
  if (!result.rendered_view) {
    throw new Error("rendered_view must identify the active file view");
  }
  if (result.active_mounts !== 1) {
    throw new Error(`active_mounts must remain one; observed ${result.active_mounts}`);
  }
  if (!result.active_view_nonempty) {
    throw new Error("active_view_nonempty must prove useful painted content");
  }
  if (result.blank_frames !== 0 || result.blank_duration_ms !== 0) {
    throw new Error(
      `blank_frames and blank_duration_ms must remain zero; observed ` +
        `${result.blank_frames}/${result.blank_duration_ms}`,
    );
  }
  if (!result.pending_seen) {
    throw new Error("pending_seen must prove immediate selection feedback");
  }
  if (result.pending_active) {
    throw new Error("pending_active must clear at painted readiness");
  }
  if (result.aria_busy) {
    throw new Error("aria_busy must clear at painted readiness");
  }
  if (!Number.isInteger(result.file_fetches) || result.file_fetches > 1) {
    throw new Error(`file_fetches must be at most one; observed ${result.file_fetches}`);
  }
  if (result.name?.startsWith("cached-") && result.file_fetches !== 0) {
    throw new Error(
      `file_fetches must be zero for cached navigation; observed ${result.file_fetches}`,
    );
  }
  const requiredLabels = [
    "fileNavigation:assets",
    "fileNavigation:activeView",
    "fileNavigation:paintReady",
    "fileNavigation:selectToReady",
  ];
  for (const label of requiredLabels) {
    if (!result.phase_labels?.includes(label)) {
      throw new Error(`phase_labels is missing ${label}`);
    }
  }
}

async function measureFileTransition(session, filePath, name, timeoutMs) {
  const point = await pointForFilePath(session, filePath);
  if (!point) {
    throw new Error(`could not click file row ${filePath}`);
  }
  const started = await evaluate(session, `({epoch: Date.now(), now: performance.now()})`);
  await startFileBlankFrameMonitor(session);
  await dispatchTrustedClickAtPoint(session, point);
  const ready = await waitForFileView(session, filePath, timeoutMs);
  const blank = await stopFileBlankFrameMonitor(session);
  const snapshot = await evaluate(session, `window.metabrowser.perf.snapshot()`);
  const measures = snapshot.raw_measure.filter(
    (sample) =>
      sample.ts >= started.epoch &&
      (sample.label.startsWith("fileNavigation:") || sample.label === "apiFile:json"),
  );
  const fetches = snapshot.raw_fetch.filter((sample) => sample.ts >= started.epoch);
  const fileFetches = fetches.filter((sample) => {
    const url = new URL(sample.url, "http://localhost");
    return url.pathname === "/api/file" && url.searchParams.get("path") === filePath;
  });
  const result = {
    name,
    path: filePath,
    total_ms: Number((ready.paintedAt - started.now).toFixed(2)),
    selected_path: ready.state.selectedPath,
    route_path: ready.state.routePath,
    rendered_path: ready.state.renderedPath,
    rendered_view: ready.state.renderedView,
    active_mounts: ready.state.activeMounts,
    active_view_nonempty: ready.state.activeViewNonempty,
    file_fetches: fileFetches.length,
    ...blank,
    phase_labels: Array.from(new Set(measures.map((sample) => sample.label))),
    phases: measures.map((sample) => ({
      duration_ms: Number(sample.duration_ms.toFixed(2)),
      kind: sample.meta?.kind || "",
      label: sample.label,
      path: sample.meta?.path || "",
      view: sample.meta?.view || "",
    })),
    fetches: fetches
      .filter((sample) => {
        const pathname = new URL(sample.url, "http://localhost").pathname;
        return (
          pathname === "/api/file" ||
          pathname.startsWith("/api/plugin/") ||
          pathname.startsWith("/plugin-static/")
        );
      })
      .map((sample) => ({
        duration_ms: Number(sample.duration_ms.toFixed(2)),
        server_ms: sample.server_ms,
        size_bytes: sample.size_bytes,
        status: sample.status,
        url: new URL(sample.url, "http://localhost").pathname,
      })),
  };
  assertFileTransitionHealth(result);
  return result;
}

async function runFileViewScenario(session, timeoutMs) {
  await waitFor(
    () => pointForSelector(session, '.tab-btn[data-tab="files"]'),
    timeoutMs,
    "Files navigation tab",
  );
  await dispatchTrustedClickForSelector(session, '.tab-btn[data-tab="files"]');
  const candidates = await waitFor(
    async () => {
      const value = await fileViewCandidates(session);
      return value.markdown && value.structured && value.sources.length >= 2 ? value : null;
    },
    timeoutMs,
    "one Markdown, one structured, and two source file rows",
  );

  await dispatchTrustedClickForFilePath(session, candidates.sources[0]);
  await waitForFileView(session, candidates.sources[0], timeoutMs);
  await waitForClientQuiescence(session, timeoutMs);
  await evaluate(session, `window.metabrowser.perf.reset()`);

  const transitions = [];
  transitions.push(
    await measureFileTransition(session, candidates.sources[1], "cold-source", timeoutMs),
  );
  transitions.push(
    await measureFileTransition(session, candidates.structured, "cold-structured", timeoutMs),
  );
  transitions.push(
    await measureFileTransition(session, candidates.markdown, "cold-markdown", timeoutMs),
  );
  transitions.push(
    await measureFileTransition(session, candidates.sources[1], "cached-source", timeoutMs),
  );
  await waitForClientQuiescence(session, timeoutMs);
  return {
    schema: "file-view-navigation/v1",
    generated_at: new Date().toISOString(),
    scenario: "file-views",
    warm_path: candidates.sources[0],
    transitions,
    profiler: await evaluate(session, `window.metabrowser.perf.snapshot()`),
  };
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
            Boolean(document.querySelector(".git-commit-diff .diff-root")) &&
            !document.querySelector("#preview-pane")?.classList.contains(
              "preview-navigation-pending"
            );
        })()`,
      ),
    timeoutMs,
    `Git revision ${revision} to render`,
  );
  return awaitNextPaint(session);
}

function assertGitTransitionHealth(result) {
  if (!result.revision) {
    throw new Error("revision is required for Git transition validation");
  }
  for (const field of ["selected_revision", "route_revision", "rendered_revision"]) {
    if (result[field] !== result.revision) {
      throw new Error(
        `${field} did not converge on ${result.revision}; observed ${result[field] || "none"}`,
      );
    }
  }
  if (result.mounted_comparisons !== 1) {
    throw new Error(`mounted_comparisons must remain one; observed ${result.mounted_comparisons}`);
  }
  if (result.blank_frames !== 0 || result.blank_duration_ms !== 0) {
    throw new Error(
      `blank_frames and blank_duration_ms must remain zero; observed ` +
        `${result.blank_frames}/${result.blank_duration_ms}`,
    );
  }
  if (!result.pending_seen) {
    throw new Error("pending_seen must prove immediate Git selection feedback");
  }
  if (result.pending_active) {
    throw new Error("pending_active must clear at Git painted readiness");
  }
  if (result.aria_busy) {
    throw new Error("aria_busy must clear at Git painted readiness");
  }
  if (!Number.isFinite(result.pending_onset_ms)) {
    throw new Error("pending_onset_ms must record Git selection acknowledgement");
  }
  if (!Number.isFinite(result.pending_clear_ms)) {
    throw new Error("pending_clear_ms must record Git painted readiness");
  }
  if (result.pending_clear_ms < result.pending_onset_ms) {
    throw new Error("pending_clear_ms must not precede pending_onset_ms");
  }
  const requiredLabels = [
    "gitRevision:selectionFeedback",
    "gitRevision:selectToReady",
    "gitRevision:rowAnchor",
  ];
  for (const label of requiredLabels) {
    if (!result.phase_labels?.includes(label)) {
      throw new Error(`phase_labels is missing ${label}`);
    }
  }
}

async function measureGitTransition(session, rowIndex, name, timeoutMs) {
  const row = await gitRow(session, rowIndex);
  if (!row?.revision) {
    throw new Error(`Git row ${rowIndex} is unavailable`);
  }
  const point = await pointForSelector(session, ".git-graph-row", rowIndex);
  if (!point) {
    throw new Error(`could not click .git-graph-row[${rowIndex}]`);
  }
  const started = await evaluate(session, `({epoch: Date.now(), now: performance.now()})`);
  await startGitBlankFrameMonitor(session);
  await dispatchTrustedClickAtPoint(session, point);
  const paintedAt = await waitForGitRevision(session, row.revision, timeoutMs);
  const blank = await stopGitBlankFrameMonitor(session);
  const snapshot = await evaluate(session, `window.metabrowser.perf.snapshot()`);
  const measures = snapshot.raw_measure.filter(
    (sample) => sample.ts >= started.epoch && sample.label.startsWith("gitRevision:"),
  );
  const fetches = snapshot.raw_fetch.filter((sample) => sample.ts >= started.epoch);
  const state = await evaluate(
    session,
    `(() => ({
      selectedRevision: document.querySelector(".git-graph-row.selected")?.dataset.revision || "",
      routeRevision: location.pathname.split("/").pop() || "",
      renderedRevision: document.querySelector(".git-commit-view")?.dataset.revision || "",
      mountedComparisons: document.querySelectorAll(".git-commit-diff .diff-root").length
    }))()`,
  );
  const result = {
    name,
    revision: row.revision,
    total_ms: Number((paintedAt - started.now).toFixed(2)),
    selected_revision: state.selectedRevision,
    route_revision: state.routeRevision,
    rendered_revision: state.renderedRevision,
    mounted_comparisons: state.mountedComparisons,
    ...blank,
    phase_labels: Array.from(new Set(measures.map((sample) => sample.label))),
    phases: measures.map((sample) => ({
      duration_ms: Number(sample.duration_ms.toFixed(2)),
      label: sample.label,
      revision: sample.meta?.revision || "",
    })),
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
  assertGitTransitionHealth(result);
  return result;
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

function assertGitFilesCollapsedFolderHealth(state) {
  if (!state?.row_collapsed || state.row_expanded || !state.group_collapsed) {
    throw new Error("folder must begin with one coherent collapsed state");
  }
  if (state.aria_expanded !== "false") {
    throw new Error("collapsed folder must expose aria-expanded=false");
  }
  if (state.group_inline_display === "none") {
    throw new Error("collapsed folder must not retain an inline display:none override");
  }
  if (state.group_visibility !== "hidden") {
    throw new Error("collapsed folder child group must be hidden by the shared class");
  }
}

function assertGitFilesRoundTripHealth(result) {
  if (!result.path) {
    throw new Error("path is required for Git-to-Files round-trip validation");
  }
  if (!Number.isFinite(result.return_to_files_ms) || !Number.isFinite(result.folder_expand_ms)) {
    throw new Error("Git-to-Files round-trip timings must be finite");
  }
  assertGitFilesCollapsedFolderHealth(result.before);
  if (!result.after?.row_expanded || result.after.row_collapsed || result.after.group_collapsed) {
    throw new Error("folder must become visibly expanded on the first open action");
  }
  if (result.after.aria_expanded !== "true") {
    throw new Error("expanded folder must expose aria-expanded=true");
  }
  if (
    result.after.group_inline_display === "none" ||
    result.after.group_display === "none" ||
    result.after.group_visibility === "hidden"
  ) {
    throw new Error("expanded folder child group remained hidden");
  }
}

async function gitFilesFolderState(session, rowIndex) {
  return evaluate(
    session,
    `(() => {
      const row = document.querySelectorAll(
        "#tab-files .tree-folder:not(.tree-item-empty)"
      )[${rowIndex}];
      const group = row?.nextElementSibling;
      if (!(row instanceof HTMLElement) ||
          !(group instanceof HTMLElement) ||
          !group.classList.contains("tree-children")) return null;
      const groupStyle = getComputedStyle(group);
      return {
        aria_expanded: row.getAttribute("aria-expanded"),
        group_collapsed: group.classList.contains("tree-children-collapsed"),
        group_display: groupStyle.display,
        group_inline_display: group.style.display,
        group_visibility: groupStyle.visibility,
        path: row.dataset.path || "",
        row_collapsed: row.classList.contains("collapsed"),
        row_expanded: row.classList.contains("expanded")
      };
    })()`,
  );
}

// Run before the inventory completion wait. A large root can populate Files
// through live inserts while Git owns the nav panel; returning from a rendered
// diff must leave those folders interactive without a page reload.
async function runGitFilesRoundTrip(session, timeoutMs) {
  await waitFor(
    () => pointForSelector(session, '.tab-btn[data-tab="git"]'),
    timeoutMs,
    "Git navigation tab during indexing",
  );
  await dispatchTrustedClickForSelector(session, '.tab-btn[data-tab="git"]');
  await waitFor(
    async () =>
      evaluate(
        session,
        `document.querySelectorAll(".git-graph-row").length > ${GIT_ROUNDTRIP_ROW_INDEX}`,
      ),
    timeoutMs,
    "Git history rows during indexing",
  );
  // Leave row zero untouched for the settled scenario's warm transition. The
  // round trip changes the route to a folder; re-clicking an already-selected
  // revision is not a representative revision transition and can retain the
  // intentionally replaced preview instead of reloading it.
  const revision = await gitRow(session, GIT_ROUNDTRIP_ROW_INDEX);
  await dispatchTrustedClickForSelector(session, ".git-graph-row", GIT_ROUNDTRIP_ROW_INDEX);
  await waitForGitRevision(session, revision.revision, timeoutMs);

  const folderCandidate = await waitFor(
    async () =>
      evaluate(
        session,
        `(() => {
          const rows = Array.from(document.querySelectorAll(
            "#tab-files .tree-folder:not(.tree-item-empty)"
          ));
          const index = rows.findIndex((row) =>
            row.nextElementSibling?.classList.contains("tree-children")
          );
          return index >= 0 ? {index} : null;
        })()`,
      ),
    timeoutMs,
    "a Files folder while the Git diff is visible",
  );
  const folderIndex = folderCandidate.index;

  const returnStarted = await evaluate(session, `performance.now()`);
  await dispatchTrustedClickForSelector(session, '.tab-btn[data-tab="files"]');
  const returnedAt = await awaitNextPaint(session);
  let before = await gitFilesFolderState(session, folderIndex);
  if (!before) {
    throw new Error("Files folder disappeared during the Git round trip");
  }
  // A regular fetched tree may have opened this row through the viewport-bound
  // default planner. Normalize that healthy state to collapsed before testing
  // the one-click open contract. A corrupted live insert is already marked
  // collapsed but has an uncollapsed, inline-hidden group, so it fails below
  // without being normalized away.
  if (
    before.row_expanded &&
    !before.group_collapsed &&
    before.group_display !== "none" &&
    before.group_visibility !== "hidden"
  ) {
    await dispatchTrustedClickForSelector(
      session,
      "#tab-files .tree-folder:not(.tree-item-empty)",
      folderIndex,
    );
    before = await waitFor(
      async () => {
        const state = await gitFilesFolderState(session, folderIndex);
        return state?.row_collapsed && state.group_collapsed ? state : null;
      },
      timeoutMs,
      "the round-trip folder to collapse",
    );
  }

  const expandStarted = await evaluate(session, `performance.now()`);
  const partial = {
    path: before.path,
    return_to_files_ms: Number((returnedAt - returnStarted).toFixed(2)),
    before,
  };
  // Reject incoherent disclosure before clicking: this is the exact frozen
  // shape produced by the former live-insert markup.
  assertGitFilesCollapsedFolderHealth(before);
  await dispatchTrustedClickForSelector(
    session,
    "#tab-files .tree-folder:not(.tree-item-empty)",
    folderIndex,
  );
  const after = await waitFor(
    async () => {
      const state = await gitFilesFolderState(session, folderIndex);
      return state?.row_expanded &&
        !state.group_collapsed &&
        state.group_display !== "none" &&
        state.group_visibility !== "hidden"
        ? state
        : null;
    },
    timeoutMs,
    "the round-trip folder to expand",
  );
  const expandedAt = await awaitNextPaint(session);
  const result = {
    ...partial,
    folder_expand_ms: Number((expandedAt - expandStarted).toFixed(2)),
    after,
  };
  assertGitFilesRoundTripHealth(result);
  return result;
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

async function gitHistoryMountedStats(session) {
  return evaluate(
    session,
    `(() => {
      const content = document.getElementById("tree-content");
      const list = document.querySelector(".git-graph-list");
      if (!(content instanceof HTMLElement) || !(list instanceof HTMLElement)) return null;
      const rows = Array.from(list.querySelectorAll(".git-graph-row"));
      return {
        document_dom_nodes: document.querySelectorAll("*").length,
        first_ordinal: Number(rows[0]?.dataset.ordinal ?? -1),
        first_revision: rows[0]?.dataset.revision || "",
        history_end: list.dataset.historyEnd === "true",
        last_revision: rows.at(-1)?.dataset.revision || "",
        last_ordinal: Number(rows.at(-1)?.dataset.ordinal ?? -1),
        list_dom_nodes: list.querySelectorAll("*").length + 1,
        list_html_bytes: new TextEncoder().encode(list.outerHTML).byteLength,
        logical_row_count: Number(list.dataset.historyRows || 0),
        max_mounted_rows: Number(window.METABROWSER_SETTINGS.GIT_HISTORY_WINDOW_MAX_ROWS),
        row_count: rows.length,
        scroll_height_px: content.scrollHeight,
        viewport_height_px: content.clientHeight,
      };
    })()`,
  );
}

async function gitHistoryRowCount(session) {
  return evaluate(session, 'document.querySelectorAll(".git-graph-row").length');
}

async function gitHistoryLogicalState(session) {
  return evaluate(
    session,
    `(() => {
      const list = document.querySelector(".git-graph-list");
      const rows = Array.from(document.querySelectorAll(".git-graph-row"));
      if (!(list instanceof HTMLElement)) return null;
      return {
        end: list.dataset.historyEnd === "true",
        first_ordinal: Number(rows[0]?.dataset.ordinal ?? -1),
        last_ordinal: Number(rows.at(-1)?.dataset.ordinal ?? -1),
        logical_rows: Number(list.dataset.historyRows || 0),
        mounted_rows: rows.length,
      };
    })()`,
  );
}

async function loadGitHistoryDepth(session, targetRows, timeoutMs) {
  await waitFor(
    () => pointForSelector(session, '.tab-btn[data-tab="git"]'),
    timeoutMs,
    "Git navigation tab",
  );
  await dispatchTrustedClickForSelector(session, '.tab-btn[data-tab="git"]');
  await waitFor(
    async () => ((await gitHistoryRowCount(session)) > 0 ? true : null),
    timeoutMs,
    "the first Git history page",
  );

  // Give the deepest-row transition a real retained preview to replace. The
  // established revision scenario uses the same warm handoff; an empty preview
  // would measure first render instead of navigation continuity.
  const warm = await gitRow(session, 0);
  await dispatchTrustedClickForSelector(session, ".git-graph-row", 0);
  await waitForGitRevision(session, warm.revision, timeoutMs);
  await waitForClientQuiescence(session, timeoutMs);

  const pageAppends = [];
  while (true) {
    const before = await gitHistoryLogicalState(session);
    if (!before) {
      throw new Error("Git history list disappeared during depth measurement");
    }
    if (before.logical_rows >= targetRows) {
      if (before.logical_rows !== targetRows || !before.end) {
        throw new Error(
          `Git history reached ${before.logical_rows} logical rows without its expected end`,
        );
      }
      await evaluate(
        session,
        `(() => {
          const content = document.getElementById("tree-content");
          if (!(content instanceof HTMLElement)) return false;
          content.scrollTop = content.scrollHeight;
          content.dispatchEvent(new Event("scroll"));
          return true;
        })()`,
      );
      await waitFor(
        async () => {
          const state = await gitHistoryLogicalState(session);
          return state?.last_ordinal === targetRows - 1 ? state : null;
        },
        timeoutMs,
        "the terminal Git history window",
      );
      const stats = await gitHistoryMountedStats(session);
      if (!stats) {
        throw new Error("Git history list disappeared during depth measurement");
      }
      return { pageAppends, stats };
    }
    const started = await evaluate(session, "performance.now()");
    await evaluate(
      session,
      `(() => {
        const content = document.getElementById("tree-content");
        if (!(content instanceof HTMLElement)) return false;
        content.scrollTop = content.scrollHeight;
        content.dispatchEvent(new Event("scroll"));
        return true;
      })()`,
    );
    const afterRows = await waitFor(
      async () => {
        const failure = await evaluate(
          session,
          `document.querySelector(".git-graph-more-failed")?.textContent || ""`,
        );
        if (failure) {
          throw new Error(failure);
        }
        const state = await gitHistoryLogicalState(session);
        if (!state) {
          return null;
        }
        return state.logical_rows > before.logical_rows || state.end ? state : null;
      },
      timeoutMs,
      `Git history page after row ${before.logical_rows}`,
    );
    const paintedAt = await awaitNextPaint(session);
    pageAppends.push({
      from_rows: before.logical_rows,
      mounted_rows: afterRows.mounted_rows,
      to_rows: afterRows.logical_rows,
      total_ms: Number((paintedAt - started).toFixed(2)),
    });
  }
}

async function measureGitHistoryScrolling(session) {
  return evaluate(
    session,
    `(async () => {
      const content = document.getElementById("tree-content");
      if (!(content instanceof HTMLElement)) return null;
      const maximum = Math.max(0, content.scrollHeight - content.clientHeight);
      const positions = [0, 0.25, 0.5, 0.75, 1, 0.5, 0];
      const samples = [];
      for (const fraction of positions) {
        const started = performance.now();
        content.scrollTop = Math.round(maximum * fraction);
        content.dispatchEvent(new Event("scroll"));
        content.getBoundingClientRect();
        const deadline = performance.now() + 10000;
        while (true) {
          await new Promise((resolve) => requestAnimationFrame(() =>
            requestAnimationFrame(resolve)));
          const list = document.querySelector(".git-graph-list");
          if (!(list instanceof HTMLElement)) break;
          if (!list.querySelector(".git-history-page-placeholder") &&
              list.getAttribute("aria-busy") !== "true") break;
          if (performance.now() >= deadline) break;
        }
        const rows = Array.from(document.querySelectorAll(".git-graph-row"));
        samples.push({
          complete: !document.querySelector(".git-history-page-placeholder"),
          fraction,
          first_ordinal: Number(rows[0]?.dataset.ordinal ?? -1),
          last_ordinal: Number(rows.at(-1)?.dataset.ordinal ?? -1),
          mounted_rows: rows.length,
          duration_ms: Number((performance.now() - started).toFixed(2)),
          scroll_top_px: content.scrollTop,
        });
      }
      return {maximum_scroll_top_px: maximum, samples};
    })()`,
    true,
  );
}

async function measureBrowserHeightClamp(session) {
  return evaluate(
    session,
    `(() => {
      const probe = document.createElement("div");
      Object.assign(probe.style, {
        height: "100000000px",
        left: "-10000px",
        position: "absolute",
        top: "0",
        width: "1px",
      });
      document.body.append(probe);
      const height = probe.getBoundingClientRect().height;
      probe.remove();
      return height;
    })()`,
  );
}

function assertGitHistoryDepthHealth(result) {
  if (result.stats.logical_row_count !== result.target_rows || !result.stats.history_end) {
    throw new Error(
      `Git history reached ${result.stats.logical_row_count} rows without its expected end`,
    );
  }
  if (result.stats.row_count > result.stats.max_mounted_rows) {
    throw new Error(
      `Git history mounted ${result.stats.row_count} rows; bound is ${result.stats.max_mounted_rows}`,
    );
  }
  if (result.stats.last_ordinal !== result.target_rows - 1) {
    throw new Error(
      `Git history final window ended at ordinal ${result.stats.last_ordinal}; ` +
        `expected ${result.target_rows - 1}`,
    );
  }
  if (!result.stats.first_revision || !result.stats.last_revision) {
    throw new Error("Git history depth scenario did not mount its final window revisions");
  }
  if (result.selection.revision !== result.stats.last_revision) {
    throw new Error("Git history depth scenario did not select its deepest mounted revision");
  }
  if (result.scrolling.samples.some((sample) => !sample.complete)) {
    throw new Error("Git history scrolling left a replay placeholder unresolved");
  }
  if (!result.deep_route.restored) {
    throw new Error(
      `deep route did not restore the selected revision: ${JSON.stringify(result.deep_route)}`,
    );
  }
  for (const field of ["selected_revision", "route_revision", "rendered_revision"]) {
    if (result.deep_route[field] !== result.selection.revision) {
      throw new Error(`deep route ${field} did not restore the selected revision`);
    }
  }
  if (result.deep_route.mounted_comparisons !== 1) {
    throw new Error("deep route must retain exactly one mounted comparison");
  }
}

async function runGitHistoryDepthScenario(
  session,
  targetRows,
  timeoutMs,
  baseUrl,
  consoleMessages,
) {
  await evaluate(session, "window.metabrowser.perf.reset()");
  const loaded = await loadGitHistoryDepth(session, targetRows, timeoutMs);
  await waitForClientQuiescence(session, timeoutMs);
  const scrolling = await measureGitHistoryScrolling(session);
  const browserHeightClampPx = await measureBrowserHeightClamp(session);
  const profiler = await evaluate(session, "window.metabrowser.perf.snapshot()");
  const logFetches = profiler.raw_fetch
    .filter((sample) => new URL(sample.url, "http://localhost").pathname === "/api/git/log")
    .map((sample) => ({
      duration_ms: Number(sample.duration_ms.toFixed(2)),
      server_ms: sample.server_ms,
      size_bytes: sample.size_bytes,
      status: sample.status,
      url: new URL(sample.url, "http://localhost").pathname,
    }));

  await session.send("HeapProfiler.enable");
  await session.send("HeapProfiler.collectGarbage");
  const loadedHeap = await session.send("Runtime.getHeapUsage");

  await evaluate(
    session,
    `(() => {
      const content = document.getElementById("tree-content");
      if (!(content instanceof HTMLElement)) return false;
      content.scrollTop = content.scrollHeight;
      content.dispatchEvent(new Event("scroll"));
      return true;
    })()`,
  );
  await waitFor(
    async () => {
      const state = await gitHistoryLogicalState(session);
      return state?.last_ordinal === targetRows - 1 ? state : null;
    },
    timeoutMs,
    "the final virtual Git history window",
  );
  await awaitNextPaint(session);
  const mountedRows = await gitHistoryRowCount(session);
  const selection = await measureGitTransition(
    session,
    mountedRows - 1,
    "deepest-mounted-row",
    timeoutMs,
  );
  await waitForClientQuiescence(session, timeoutMs);

  const priorTimeOrigin = await evaluate(session, "performance.timeOrigin");
  const deepUrl = new URL(`/commit/${selection.revision}`, baseUrl).href;
  const deepRouteStarted = Date.now();
  await session.send(`Page.navigate`, { url: deepUrl });
  let deepRouteRestored = true;
  let deepRouteError = "";
  try {
    await waitFor(
      async () =>
        evaluate(
          session,
          `(() => {
            if (performance.timeOrigin === ${JSON.stringify(priorTimeOrigin)}) return false;
            const revision = ${JSON.stringify(selection.revision)};
            return document.querySelector(".git-commit-view")?.dataset.revision === revision &&
              location.pathname.endsWith(revision) &&
              !document.querySelector("#preview-pane")?.classList.contains(
                "preview-navigation-pending"
              );
          })()`,
        ),
      Math.min(timeoutMs, DEEP_ROUTE_MEASUREMENT_TIMEOUT_MS),
      "deep Git commit route restoration",
    );
    await awaitNextPaint(session);
    await waitForClientQuiescence(session, timeoutMs);
  } catch (error) {
    deepRouteRestored = false;
    deepRouteError = String(error);
  }
  const deepRouteState = await evaluate(
    session,
    `(() => ({
      selected_revision: document.querySelector(".git-graph-row.selected")?.dataset.revision ||
        ${JSON.stringify(selection.revision)},
      route_revision: location.pathname.split("/").pop() || "",
      rendered_revision: document.querySelector(".git-commit-view")?.dataset.revision || "",
      mounted_comparisons: document.querySelectorAll(".git-commit-diff .diff-root").length,
      preview_pending: document.querySelector("#preview-pane")?.classList.contains(
        "preview-navigation-pending"
      ) || false,
      preview_owner: document.querySelector("#preview-pane")?.dataset.previewOwner || "",
      preview_owners: window.__metabrowserPreviewOwners || [],
      fetches: (window.__metabrowserFetches || []).slice(-20),
      plugin_assets: Array.from(document.querySelectorAll(
        "[data-metabrowser-plugin-asset]"
      )).map((element) => ({
        asset: element.getAttribute("data-metabrowser-plugin-asset") || "",
        connected: element.isConnected,
        href: element instanceof HTMLLinkElement ? element.href : "",
        sheet: element instanceof HTMLLinkElement ? Boolean(element.sheet) : undefined,
        src: element instanceof HTMLScriptElement ? element.src : "",
      })),
      performance_resources: performance.getEntriesByType("resource")
        .filter((entry) => entry.name.includes("/plugins/") || entry.name.includes("/api/git/commit") ||
          entry.name.includes("/api/plugin/diff/comparison"))
        .map((entry) => ({
          duration_ms: Number(entry.duration.toFixed(1)),
          initiator_type: entry.initiatorType,
          name: entry.name,
          transfer_size: entry.transferSize,
        })),
      preview_text: document.querySelector("#preview-pane")?.textContent?.trim().slice(0, 500) || "",
      git_panel_text: document.querySelector("#tab-git")?.textContent?.trim().slice(0, 500) || "",
      document_ready_state: document.readyState,
    }))()`,
  );

  const result = {
    schema: "git-history-depth/v2",
    generated_at: new Date().toISOString(),
    scenario: "git-history-depth",
    target_rows: targetRows,
    stats: loaded.stats,
    page_appends: loaded.pageAppends,
    log_fetches: logFetches,
    log_payload_bytes: logFetches.reduce((total, sample) => total + (sample.size_bytes || 0), 0),
    loaded_js_heap_after_gc_mb: Number((loadedHeap.usedSize / (1024 * 1024)).toFixed(1)),
    browser_height_clamp_px: browserHeightClampPx,
    scrolling,
    selection,
    deep_route: {
      ...deepRouteState,
      console_messages: consoleMessages.slice(-20),
      error: deepRouteError,
      restored: deepRouteRestored,
      total_ms: Date.now() - deepRouteStarted,
    },
    profiler,
  };
  assertGitHistoryDepthHealth(result);
  return result;
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
    const consoleMessages = [];
    session.on("Runtime.exceptionThrown", () => {
      pageExceptions += 1;
    });
    session.on("Runtime.consoleAPICalled", (event) => {
      if (event.type !== "error" && event.type !== "warning") {
        return;
      }
      consoleMessages.push({
        type: event.type,
        values: event.args.map((argument) => argument.value ?? argument.description ?? ""),
      });
    });
    await session.send("Page.enable");
    await session.send("Runtime.enable");
    await session.send("Emulation.setDeviceMetricsOverride", {
      deviceScaleFactor: 1,
      height: options.height,
      mobile: false,
      width: options.width,
    });
    if (options.scenario === "git-history-depth") {
      await session.send("Page.addScriptToEvaluateOnNewDocument", {
        source: `(() => {
          const nativeFetch = window.fetch.bind(window);
          window.__metabrowserPreviewOwners = [];
          window.__metabrowserFetches = [];
          window.addEventListener("DOMContentLoaded", () => {
            const preview = document.getElementById("preview-pane");
            if (!(preview instanceof HTMLElement)) return;
            const record = () => window.__metabrowserPreviewOwners.push({
              owner: preview.dataset.previewOwner || "",
              timestamp_ms: Number(performance.now().toFixed(1)),
            });
            record();
            new MutationObserver(record).observe(preview, {
              attributeFilter: ["data-preview-owner"],
            });
          }, {once: true});
          window.fetch = (input, init) => {
            const rawUrl = input instanceof Request ? input.url : String(input);
            const url = new URL(rawUrl, location.href);
            if (url.pathname === "/api/git/log") {
              url.searchParams.set("scope", "all");
              input = input instanceof Request ? new Request(url, input) : url.href;
            }
            const entry = {
              method: init?.method || (input instanceof Request ? input.method : "GET"),
              started_ms: Number(performance.now().toFixed(1)),
              status: "pending",
              url: url.pathname + url.search,
            };
            window.__metabrowserFetches.push(entry);
            return nativeFetch(input, init).then(
              (response) => {
                entry.ended_ms = Number(performance.now().toFixed(1));
                entry.status = response.status;
                return response;
              },
              (error) => {
                entry.ended_ms = Number(performance.now().toFixed(1));
                entry.status = String(error);
                throw error;
              },
            );
          };
        })();`,
      });
    }
    await session.send("Page.navigate", { url: options.url });
    await waitFor(
      async () =>
        evaluate(
          session,
          `document.readyState === "complete" &&
            typeof window.metabrowser?.perf?.snapshot === "function"`,
        ),
      FIRST_ROW_TIMEOUT_MS,
      "application shell and performance recorder",
    );
    let gitFilesRoundTrip = null;
    if (options.scenario === "git-revisions") {
      gitFilesRoundTrip = await runGitFilesRoundTrip(session, options.timeoutMs);
      // The preflight deliberately navigates away from Git into Files while the
      // index is active. Reload the application document before the established
      // revision timing and deferred-hydration gates so its prepared-comparison
      // and mounted-view state cannot warm or otherwise perturb those samples.
      const preflightTimeOrigin = await evaluate(session, `performance.timeOrigin`);
      await session.send("Page.navigate", { url: options.url });
      await waitFor(
        async () =>
          evaluate(
            session,
            `performance.timeOrigin !== ${JSON.stringify(preflightTimeOrigin)} &&
              document.readyState === "complete" &&
              typeof window.metabrowser?.perf?.snapshot === "function" &&
              Boolean(document.querySelector('[role="treeitem"]'))`,
          ),
        FIRST_ROW_TIMEOUT_MS,
        "fresh application row after the Git-to-Files preflight",
      );
    } else {
      await waitFor(
        async () => evaluate(session, `Boolean(document.querySelector('[role="treeitem"]'))`),
        FIRST_ROW_TIMEOUT_MS,
        "application first row",
      );
    }
    if (options.scenario) {
      await waitForIndex(options.url, options.timeoutMs);
      await delay(CLIENT_COMPLETION_SETTLE_MS);
      await waitForClientQuiescence(session, options.timeoutMs);
      let payload;
      if (options.scenario === "git-revisions") {
        payload = await runGitRevisionScenario(session, options.timeoutMs);
      } else if (options.scenario === "git-history-depth") {
        payload = await runGitHistoryDepthScenario(
          session,
          options.historyRows,
          options.timeoutMs,
          options.url,
          consoleMessages,
        );
      } else {
        payload = await runFileViewScenario(session, options.timeoutMs);
      }
      if (gitFilesRoundTrip) {
        payload.git_files_roundtrip = gitFilesRoundTrip;
      }
      payload.page_exceptions = pageExceptions;
      if (pageExceptions !== 0) {
        throw new Error(
          `${options.scenario} scenario observed ${pageExceptions} uncaught page exception(s)`,
        );
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
  assertFileTransitionHealth,
  assertGitFilesRoundTripHealth,
  assertGitHistoryDepthHealth,
  assertGitTransitionHealth,
  capture,
  chromeExecutable,
  dispatchTrustedClickAtPoint,
  dispatchTrustedClickForSelector,
  parseArgs,
  runFileViewScenario,
  runGitFilesRoundTrip,
  runGitHistoryDepthScenario,
  runGitRevisionScenario,
  startTrustedInputPulse,
  usage,
  waitForClientQuiescence,
};
