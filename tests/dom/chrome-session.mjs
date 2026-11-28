// A headless Chrome over the DevTools Protocol, for the checks whose behavior is layout or
// paint: one page, `send` for protocol commands, `on` for its events, `evaluate` for page
// expressions, and a `close` that waits for Chrome to exit before removing its profile,
// since removing it while Chrome still writes there failed with ENOTEMPTY under load and
// left the process open.
//
// `profiles` is a directory the caller owns, under which each start makes a profile of
// its own. The caller runs the session in a process group of its own, stops that group
// however the session ends, Chrome included, and then removes the directory
// (tests/process_group.py), so a session cut off by its bound leaves nothing running.
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

// One start's bound: from the spawn to DevToolsActivePort's whole content, an answer on
// its port, and the page's socket open. A runner's cold first start is the run's warm-up's
// (tests/chrome_starts.py, which has the CI measurements), so a test's start is warm: a
// whole test that only drives Chrome took a median 1.5 to 3.1 s warm in CI, and 30 starts
// in a row on a 10-core Mac at a load average of 10 to 17 took 0.5 to 1.2 s each. Of the
// 90 cold first starts measured in CI, 89 finished inside this bound, the slowest 28.8 s
// slower than warm.
export const START_BOUND_MS = 30000;
// The starts one launch makes before it fails: one more, logged, after a start whose
// Chrome exited, which fails fast and leaves the session its time. A start cut off at
// START_BOUND_MS is not made again. Every such start CI has shown was a cold first one,
// and the start after it in its job ran 13 to 67 s slower than warm, so a second start
// would run past most Chrome sessions' 40 to 48 s bounds, which stop it unrecorded.
// Bead mb-sicb sizes a retry of a hang once a run's summary of starts
// (tests/chrome_starts.py) shows a warm start cut off at the bound.
export const START_ATTEMPTS = 2;
// The end of a start's stderr kept for its failure, each chunk marked with the seconds
// since the spawn it arrived at: about 20 of Chrome's log lines.
const STDERR_TAIL_CHARS = 3000;
// How long Chrome is given to exit once signalled: a session's at its close (SIGTERM,
// then, if it is still up, SIGKILL) and a failed start's (SIGKILL), before its profile is
// removed. Chrome's exit after SIGTERM is not bounded by anything it does: on a Mac at a
// load average of 110 to 230 it took 5 to 35 s, with the checks done in 4 s, and the
// session's process cannot exit while Chrome runs, so a close that only waited and gave up
// held the whole session to its test's bound (tests/test_title_prefix_chrome.py).
// SIGKILL ends it at once; nothing a test reads is left for a graceful exit to write.
const EXIT_WAIT_MS = 5000;
// How often a start looks again at DevToolsActivePort and at the port.
const POLL_MS = 50;
// The bound on a failed start's one look at every process, as tests/process_group.py's
// SCAN_S bounds its own: such a look took 20 to 40 ms on a 10-core Mac.
const LOOK_MS = 5000;

/**
 * Each start, as one JSON line appended to the file METABROWSER_CHROME_STARTS names, for
 * the suite's summary of Chrome starts (tests/chrome_starts.py). Unset outside the suite.
 * @param {Record<string, unknown>} record
 */
function noteStart(record) {
  const log = process.env.METABROWSER_CHROME_STARTS;
  if (!log) {
    return;
  }
  const test = process.env.PYTEST_CURRENT_TEST ?? null;
  try {
    fs.appendFileSync(log, `${JSON.stringify({ test, ...record })}\n`);
  } catch (error) {
    // The record is for the summary only; a session does not fail for want of it.
    console.error(`launchChrome: could not note a start in ${log}: ${error}`);
  }
}

/** @param {number} ms */
const seconds = (ms) => (ms / 1000).toFixed(1);
/** @param {number} ms */
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Wait for *exited*, at most *waitMs*. The bound is cleared once Chrome exits: left
 * pending, it held every session's process open 5 s after its last check.
 * @param {Promise<unknown>} exited
 * @param {number} [waitMs]
 */
async function exitedWithin(exited, waitMs = EXIT_WAIT_MS) {
  /** @type {NodeJS.Timeout | undefined} */
  let bound;
  await Promise.race([exited, new Promise((resolve) => (bound = setTimeout(resolve, waitMs)))]);
  clearTimeout(bound);
}

/**
 * Stop a Chrome the session is done with, and leave nothing of it holding this process
 * open. SIGTERM first, so a Chrome that exits promptly closes its profile cleanly, then
 * SIGKILL after *waitMs* if it is still up, then the end of the stderr pipe: a helper that
 * outlived the browser holds that pipe's other end, and a pipe node still reads keeps
 * node from exiting. Whatever helper is left is the caller's process group to stop
 * (tests/process_group.py).
 * @param {import("node:child_process").ChildProcess} chrome
 * @param {Promise<unknown>} exited
 * @param {number} [waitMs]
 */
export async function stopChrome(chrome, exited, waitMs = EXIT_WAIT_MS) {
  chrome.kill("SIGTERM");
  await exitedWithin(exited, waitMs);
  if (chrome.exitCode === null && chrome.signalCode === null) {
    chrome.kill("SIGKILL");
    await exitedWithin(exited, waitMs);
  }
  chrome.stderr?.destroy();
}

/**
 * Kill what is left of a start that failed, then remove its profile: its browser, and any
 * helper still in this session's process group that names the profile, so a retry does
 * not share the runner with a start being abandoned. The sweep is what ends the helpers:
 * without it, tests/dom/chrome-start-retry.mjs's `hang` case left two running. Closing
 * the start's stderr pipe is what lets this process exit while such a helper still holds
 * the pipe's other end. Processes outside the group are the caller's to find
 * (tests/process_group.py).
 * @param {import("node:child_process").ChildProcess} chrome
 * @param {Promise<unknown>} exited
 * @param {string} profile
 * @param {boolean} spawned
 */
async function abandon(chrome, exited, profile, spawned) {
  if (spawned && chrome.exitCode === null && chrome.signalCode === null) {
    chrome.kill("SIGKILL");
    await exitedWithin(exited);
  }
  /** @type {string} */
  let listed = "";
  try {
    listed = execFileSync("ps", ["-A", "-ww", "-o", "pid=,pgid=,args="], {
      encoding: "utf8",
      timeout: LOOK_MS,
    });
  } catch {
    // Without the process table there is nothing to sweep; the caller's stop of the whole
    // group still ends every helper.
  }
  const rows = listed
    .split("\n")
    .map((line) => line.trim().match(/^(\d+)\s+(\d+)\s+(.*)$/))
    .filter((row) => row !== null);
  const group = rows.find((row) => Number(row[1]) === process.pid)?.[2];
  for (const [, pid, pgid, args] of rows) {
    if (pgid === group && Number(pid) !== process.pid && args.includes(profile)) {
      try {
        process.kill(Number(pid), "SIGKILL");
      } catch {
        // It exited between the listing and the signal.
      }
    }
  }
  chrome.stderr?.destroy();
  fs.rmSync(profile, { force: true, recursive: true, maxRetries: 5, retryDelay: 200 });
}

/**
 * One start: Chrome on a profile of its own, then, within *boundMs*, its port read
 * from DevToolsActivePort, an answer on it, and a socket open to its page. A start that
 * fails is abandoned and says why, with the end of what Chrome wrote to stderr.
 * @param {string} bin @param {string} profiles @param {number} width @param {number} height
 * @param {number} boundMs @param {string[]} args
 */
async function startChrome(bin, profiles, width, height, boundMs, args) {
  const began = Date.now();
  const deadline = began + boundMs;
  const profile = fs.mkdtempSync(path.join(profiles, "chrome-"));
  const chrome = spawn(
    bin,
    [
      "--headless=new",
      "--remote-debugging-port=0",
      "--no-first-run",
      "--no-default-browser-check",
      // A new profile installs Google Chrome's default apps from two CRX files, which it
      // copies into the system temporary directory a few seconds after it starts and
      // leaves there, stopped by SIGTERM or SIGKILL alike: 401 KiB a session. That
      // directory held 2,958 of them, 576 MiB, on 2026-11-24. A test in
      // tests/test_chrome_starts.py holds this.
      "--disable-default-apps",
      "--force-device-scale-factor=1",
      `--window-size=${width},${height}`,
      `--user-data-dir=${profile}`,
      ...args,
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"] },
  );
  /** @type {Error | null} */
  let spawnError = null;
  chrome.once("error", (error) => {
    spawnError = error;
  });
  let tail = "";
  chrome.stderr?.on("data", (chunk) => {
    tail = `${tail}[+${seconds(Date.now() - began)} s] ${chunk}`.slice(-STDERR_TAIL_CHARS);
  });
  const exited = new Promise((resolve) => chrome.once("exit", resolve));
  const ended = () =>
    chrome.exitCode !== null || chrome.signalCode !== null
      ? `exited (${chrome.exitCode ?? chrome.signalCode}) after ${seconds(Date.now() - began)} s`
      : null;
  // Chrome writes DevToolsActivePort, the port and then the browser's path, and answers on
  // the port a moment later. A first start on a CI runner was slow enough to be read
  // between the two: the list's fetch failed, the throw left Chrome running, and Chrome
  // held the session open until its test's bound killed it. So wait, within one bound,
  // for the whole file and an answer, and stop Chrome on any failure to start.
  const portFile = path.join(profile, "DevToolsActivePort");
  /** @type {string | null} */
  let port = null;
  /** @type {string | null} */
  let failure = null;
  /** @type {WebSocket | null} */
  let socket = null;
  while (port === null && failure === null) {
    const lines = fs.existsSync(portFile) ? fs.readFileSync(portFile, "utf8").split("\n") : [];
    if (lines.length >= 2 && /^\d+$/.test(lines[0])) {
      port = lines[0];
    } else if (spawnError !== null) {
      failure = `could not be spawned: ${/** @type {Error} */ (spawnError).message}`;
    } else if (ended() !== null) {
      failure = `wrote no DevTools port: ${ended()}`;
    } else if (Date.now() > deadline) {
      failure = `wrote no DevTools port in ${seconds(boundMs)} s, still running`;
    } else {
      await pause(POLL_MS);
    }
  }
  /** @type {{type: string, webSocketDebuggerUrl: string} | undefined} */
  let page;
  while (failure === null && page === undefined) {
    /** @type {unknown} */
    let error = "it listed no page";
    try {
      // Bounded too: a port that takes the connection and never answers would otherwise
      // hold the fetch to undici's own 300 s.
      const signal = AbortSignal.timeout(Math.max(deadline - Date.now(), POLL_MS));
      /** @type {Array<{type: string, webSocketDebuggerUrl: string}>} */
      const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`, { signal })).json();
      page = targets.find((target) => target.type === "page");
    } catch (thrown) {
      error = thrown;
    }
    if (page !== undefined) {
      break;
    }
    if (ended() !== null || Date.now() > deadline) {
      failure =
        `wrote DevTools port ${port} but gave no page to drive (${error}): ` +
        (ended() ?? `still running at ${seconds(boundMs)} s`);
    } else {
      await pause(POLL_MS);
    }
  }
  if (failure === null && page !== undefined) {
    const opening = new WebSocket(page.webSocketDebuggerUrl);
    /** @type {NodeJS.Timeout | undefined} */
    let bound;
    const opened = await new Promise((resolve) => {
      opening.onopen = () => resolve(true);
      opening.onerror = () => resolve(false);
      bound = setTimeout(() => resolve(false), Math.max(deadline - Date.now(), POLL_MS));
    });
    clearTimeout(bound);
    if (opened) {
      socket = opening;
    } else {
      opening.close();
      failure =
        `opened no socket to its page on DevTools port ${port}: ` +
        (ended() ?? `still running at ${seconds(boundMs)} s`);
    }
  }
  const ms = Date.now() - began;
  if (failure !== null || socket === null) {
    // Only a start whose Chrome exited is made again (START_ATTEMPTS), read before the
    // abandon kills it. A binary that cannot be spawned fails the same way every time.
    const retryable = spawnError === null && ended() !== null;
    await abandon(chrome, exited, profile, spawnError === null);
    return { ok: false, failure: failure ?? "opened no socket", retryable, ms, tail };
  }
  return { ok: true, chrome, exited, profile, socket, ms };
}

/**
 * A headless Chrome with one page, started in at most `attempts` tries: a start whose
 * Chrome exited is abandoned, written to stderr with the end of Chrome's, and made again,
 * and the last failure, or a start cut off at its bound, throws with every start's reason
 * and the last one's stderr. The suite's warm-up (tests/dom/chrome-warm-up.mjs) makes one
 * long start, and the test of the starts (tests/dom/chrome-start-retry.mjs) short ones;
 * other sessions use the default retry timing.
 * @param {string} bin
 * @param {{profiles: string, width?: number, height?: number, startBoundMs?: number,
 *   attempts?: number, args?: string[]}} options
 */
export async function launchChrome(
  bin,
  {
    profiles,
    width = 1280,
    height = 900,
    startBoundMs = START_BOUND_MS,
    attempts = START_ATTEMPTS,
    args = [],
  },
) {
  /** @type {string[]} */
  const failures = [];
  for (let attempt = 1; ; attempt += 1) {
    const start = await startChrome(bin, profiles, width, height, startBoundMs, args);
    if (start.ok) {
      noteStart({ attempt, ok: true, ms: start.ms });
      return session(start);
    }
    noteStart({ attempt, ok: false, ms: start.ms, failure: start.failure, tail: start.tail });
    failures.push(`start ${attempt} ${start.failure}`);
    const stderr = start.tail.trimEnd() || "(nothing)";
    if (!start.retryable || attempt >= attempts) {
      throw new Error(
        `Chrome did not start in ${attempt} ${attempt === 1 ? "try" : "tries"}: ` +
          `${failures.join("; ")}\n` +
          `Chrome's stderr, the end, from start ${attempt}:\n${stderr}`,
      );
    }
    console.error(
      `launchChrome: start ${attempt} of ${attempts} ${start.failure}; starting Chrome ` +
        `again. Its stderr, the end:\n${stderr}`,
    );
  }
}

/**
 * The protocol over a started Chrome's page socket, and the session's close.
 * @param {{chrome: import("node:child_process").ChildProcess, exited: Promise<unknown>, profile: string, socket: WebSocket}} start
 */
function session({ chrome, exited, profile, socket }) {
  let next = 0;
  /** @type {Map<number, (message: any) => void>} */
  const pending = new Map();
  /** @type {Map<string, Array<(params: any) => void>>} */
  const listeners = new Map();
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.method) {
      for (const listener of listeners.get(message.method) ?? []) {
        listener(message.params);
      }
      return;
    }
    pending.get(message.id)?.(message);
    pending.delete(message.id);
  };
  /**
   * A protocol event: call *listener* with the params of each *method* event.
   * @param {string} method @param {(params: any) => void} listener
   */
  const on = (method, listener) => {
    listeners.set(method, [...(listeners.get(method) ?? []), listener]);
  };
  /** @param {string} method @param {Record<string, unknown>} [params] @returns {Promise<any>} */
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      next += 1;
      pending.set(next, (message) =>
        message.error
          ? reject(new Error(`${method}: ${message.error.message}`))
          : resolve(message.result),
      );
      socket.send(JSON.stringify({ id: next, method, params }));
    });
  /** @param {string} expression */
  const evaluate = async (expression) => {
    const result = await send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails) {
      throw new Error(JSON.stringify(result.exceptionDetails).slice(0, 800));
    }
    return result.result.value;
  };
  /** @param {string} expression */
  const waitFor = async (expression, timeoutMs = 20000) => {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (await evaluate(expression)) {
        return true;
      }
      await pause(20);
    }
    throw new Error(`timed out waiting for ${expression}`);
  };
  const close = async () => {
    socket.close();
    await stopChrome(chrome, exited);
    fs.rmSync(profile, { force: true, recursive: true, maxRetries: 5, retryDelay: 200 });
  };
  return { close, evaluate, on, send, waitFor };
}
