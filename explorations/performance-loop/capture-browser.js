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
const DEVTOOLS_START_TIMEOUT_MS = 15_000;
const FIRST_ROW_TIMEOUT_MS = 30_000;
const INPUT_PULSE_INTERVAL_MS = 250;
const INPUT_SENTINEL_ID = "metabrowser-performance-input-sentinel";
const INTERACTION_OBSERVER_SETTLE_MS = 100;
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
  ].join("\n");
}

function parseArgs(argv) {
  const options = {
    chrome: "",
    headed: false,
    height: DEFAULT_VIEWPORT.height,
    output: "",
    probe: "",
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
      await removeInputSentinel(session);
      if (pulseError) {
        throw pulseError;
      }
      return count;
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
    await delay(INTERACTION_OBSERVER_SETTLE_MS);
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
  capture,
  chromeExecutable,
  dispatchTrustedClickAtPoint,
  parseArgs,
  startTrustedInputPulse,
  usage,
  waitForClientQuiescence,
};
