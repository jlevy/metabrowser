// A headless Chrome over the DevTools Protocol, for the checks whose behavior is layout or
// paint: one page, `send` for protocol commands, `evaluate` for page expressions, and a
// `close` that waits for Chrome to exit before removing its profile, since removing it
// while Chrome still writes there failed with ENOTEMPTY under load and left the process
// open.
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

/** @param {string} bin @param {{width?: number, height?: number}} [options] */
export async function launchChrome(bin, { width = 1280, height = 900 } = {}) {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "mb-chrome-"));
  const chrome = spawn(
    bin,
    [
      "--headless=new",
      "--remote-debugging-port=0",
      "--no-first-run",
      "--no-default-browser-check",
      "--force-device-scale-factor=1",
      `--window-size=${width},${height}`,
      `--user-data-dir=${profile}`,
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"] },
  );
  chrome.stderr.on("data", () => {});
  const exited = new Promise((resolve) => chrome.once("exit", resolve));
  // Chrome writes DevToolsActivePort, the port and then the browser's path, and answers on
  // the port a moment later. A first start on a CI runner was slow enough to be read
  // between the two: the list's fetch failed, the throw left Chrome running, and Chrome
  // held the session open until its test's bound killed it. So wait, within one bound,
  // for the whole file and an answer, and stop Chrome on any failure to start.
  const portFile = path.join(profile, "DevToolsActivePort");
  const deadline = Date.now() + 30000;
  const pause = () => new Promise((resolve) => setTimeout(resolve, 50));
  /** @type {WebSocket} */
  let socket;
  try {
    let port = null;
    while (port === null) {
      const lines = fs.existsSync(portFile) ? fs.readFileSync(portFile, "utf8").split("\n") : [];
      if (lines.length >= 2 && /^\d+$/.test(lines[0])) {
        port = lines[0];
      } else if (Date.now() > deadline || chrome.exitCode !== null) {
        throw new Error("Chrome wrote no DevTools port");
      } else {
        await pause();
      }
    }
    let targets = null;
    while (targets === null) {
      try {
        targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      } catch (error) {
        if (Date.now() > deadline || chrome.exitCode !== null) {
          throw error;
        }
        await pause();
      }
    }
    socket = new WebSocket(targets.find((target) => target.type === "page").webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      socket.onopen = resolve;
      socket.onerror = reject;
    });
  } catch (error) {
    chrome.kill();
    fs.rmSync(profile, { force: true, recursive: true, maxRetries: 5, retryDelay: 200 });
    throw error;
  }
  let next = 0;
  const pending = new Map();
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    pending.get(message.id)?.(message);
    pending.delete(message.id);
  };
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
  const waitFor = async (expression, timeoutMs = 20000) => {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (await evaluate(expression)) {
        return true;
      }
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
    throw new Error(`timed out waiting for ${expression}`);
  };
  const close = async () => {
    socket.close();
    chrome.kill();
    // The 5 s bound on Chrome's exit is cleared once it exits: left pending, it held every
    // session's process open 5 s after its last check.
    let bound;
    await Promise.race([exited, new Promise((resolve) => (bound = setTimeout(resolve, 5000)))]);
    clearTimeout(bound);
    fs.rmSync(profile, { force: true, recursive: true, maxRetries: 5, retryDelay: 200 });
  };
  return { close, evaluate, send, waitFor };
}
