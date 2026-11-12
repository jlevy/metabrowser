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
  const portFile = path.join(profile, "DevToolsActivePort");
  for (let attempt = 0; attempt < 300 && !fs.existsSync(portFile); attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  const port = fs.readFileSync(portFile, "utf8").split("\n")[0];
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const socket = new WebSocket(
    targets.find((target) => target.type === "page").webSocketDebuggerUrl,
  );
  await new Promise((resolve, reject) => {
    socket.onopen = resolve;
    socket.onerror = reject;
  });
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
    await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 5000))]);
    fs.rmSync(profile, { force: true, recursive: true, maxRetries: 5, retryDelay: 200 });
  };
  return { close, evaluate, send, waitFor };
}
