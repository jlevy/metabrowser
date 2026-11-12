// The gate's child processes and their cleanup. Each process is owned from the moment it
// starts, by a Cleanup that run.mjs runs however the run ends, so a failure anywhere,
// startup included, leaves nothing running and nothing holding the command open.
// processes.test.mjs covers it with shell scripts standing in for metab.
import { spawn } from "node:child_process";
import http from "node:http";
import path from "node:path";

// This checkout's metab announced its URL 433 to 508 ms after it was spawned, and exited
// 2 to 3 ms after its stdin closed (5 runs) or after SIGTERM (5 runs), at load averages
// of 6.6, 7.9, and 12.6 over 1, 5, and 15 minutes (2026-11-11). Both bounds are far past
// that, for a machine under heavier load.
const METAB_START_TIMEOUT_MS = 60_000;
const STOP_GRACE_MS = 5_000;

/**
 * @typedef {import("node:child_process").ChildProcess} ChildProcess
 * @typedef {import("node:net").AddressInfo} AddressInfo
 */

/** Things to stop, run newest first, once. */
export class Cleanup {
  /** @type {(() => unknown)[]} */
  #steps = [];

  /**
   * Adds `step`, a function that stops one thing, to run when `run` is called.
   * @param {() => unknown} step
   */
  add(step) {
    this.#steps.push(step);
  }

  /**
   * Runs every step, even after one fails, and returns the errors the steps threw.
   * @returns {Promise<unknown[]>}
   */
  async run() {
    /** @type {unknown[]} */
    const errors = [];
    for (let step = this.#steps.pop(); step !== undefined; step = this.#steps.pop()) {
      try {
        await step();
      } catch (error) {
        errors.push(error);
      }
    }
    return errors;
  }
}

/**
 * Resolves true if `promise` settles within `ms`, else false, and clears its timer.
 * @param {Promise<unknown>} promise
 * @param {number} ms
 * @returns {Promise<boolean>}
 */
export async function within(promise, ms) {
  /** @type {NodeJS.Timeout | undefined} */
  let timer;
  /** @type {Promise<boolean>} */
  const expired = new Promise((resolve) => {
    timer = setTimeout(resolve, ms, false);
  });
  try {
    return await Promise.race([promise.then(() => true), expired]);
  } finally {
    clearTimeout(timer);
  }
}

/** @param {ChildProcess} child */
const hasExited = (child) => child.exitCode !== null || child.signalCode !== null;

/**
 * Stops `child` and resolves once it has exited: its stdin closed first, if it has one,
 * which ends a server started with `--exit-on-eof`, then SIGTERM, then SIGKILL, each
 * given `graceMs`.
 * A child that never started (its spawn failed) has nothing to stop.
 * @param {ChildProcess} child
 * @param {{ graceMs?: number }} [options]
 */
export async function terminate(child, { graceMs = STOP_GRACE_MS } = {}) {
  if (child.pid === undefined || hasExited(child)) {
    return;
  }
  const exited = new Promise((resolve) => child.once("exit", resolve));
  const stdin = child.stdin;
  /** @type {(() => unknown)[]} */
  const steps = [];
  if (stdin) {
    steps.push(() => stdin.end());
  }
  steps.push(
    () => child.kill("SIGTERM"),
    () => child.kill("SIGKILL"),
  );
  for (const step of steps) {
    if (hasExited(child)) {
      return;
    }
    step();
    if (await within(exited, graceMs)) {
      return;
    }
  }
  throw new Error(`pid ${child.pid} did not exit after SIGKILL`);
}

/**
 * `metab ROOT` on a free port, with its own cache and configuration directories, owned by
 * `cleanup` from the moment it is spawned. It runs with `--exit-on-eof` and its stdin
 * held open here, so it stops when this process ends, even when it is killed outright.
 * A server that exits or misses `timeoutMs` before announcing its URL is stopped before
 * this rejects.
 * @param {string} binary
 * @param {string} root
 * @param {string} scratch
 * @param {{ cleanup: Cleanup, timeoutMs?: number }} options
 */
export async function startMetab(
  binary,
  root,
  scratch,
  { cleanup, timeoutMs = METAB_START_TIMEOUT_MS },
) {
  const port = await freePort();
  const child = spawn(
    binary,
    [
      root,
      "--port",
      String(port),
      "--no-open",
      "--exit-on-eof",
      "--cache-dir",
      path.join(scratch, "cache"),
      "--config-dir",
      path.join(scratch, "config"),
    ],
    { stdio: ["pipe", "pipe", "pipe"] },
  );
  cleanup.add(() => terminate(child));
  // Nothing is written to stdin; an EPIPE as it closes after the server has gone is the
  // stop that was wanted.
  child.stdin.on("error", () => {});
  let log = "";
  /** @type {(data: Buffer) => void} */
  let onData = () => {};
  /** @type {NodeJS.Timeout | undefined} */
  let timer;
  try {
    /** @type {string} */
    const origin = await new Promise((resolve, reject) => {
      onData = (data) => {
        log += data;
        const match = /Serving .* at (http:\/\/127\.0\.0\.1:\d+)\/view\//.exec(log);
        if (match) {
          resolve(match[1]);
        }
      };
      child.stdout.on("data", onData);
      child.stderr.on("data", onData);
      child.on("error", (error) =>
        reject(new Error(`metab did not start: ${error.message}`, { cause: error })),
      );
      child.on("exit", (code, signal) =>
        reject(new Error(`metab exited with ${code ?? signal} before serving:\n${log}`)),
      );
      timer = setTimeout(
        () => reject(new Error(`metab did not announce a URL in ${timeoutMs / 1000} s:\n${log}`)),
        timeoutMs,
      );
    });
    return { origin, child };
  } catch (error) {
    await terminate(child);
    throw error;
  } finally {
    clearTimeout(timer);
    // The streams keep flowing, so the server never blocks on a full pipe, and what it
    // writes after its banner is dropped rather than kept for the whole run.
    child.stdout.off("data", onData);
    child.stderr.off("data", onData);
  }
}

/** @returns {Promise<number>} */
export function freePort() {
  return new Promise((resolve, reject) => {
    const server = http.createServer();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      // A server listening on a TCP port reports its address as an AddressInfo.
      const { port } = /** @type {AddressInfo} */ (server.address());
      server.close(() => resolve(port));
    });
  });
}
