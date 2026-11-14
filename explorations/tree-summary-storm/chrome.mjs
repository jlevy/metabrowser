// node chrome-run.mjs URL PROBE OUT.json — headless Chrome, probe injected at document start.
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const [url, probePath, outPath] = process.argv.slice(2);
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "storm-chrome-"));
const child = spawn(
  CHROME,
  [
    "--headless=new",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-sync",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--use-mock-keychain",
    "--window-size=1200,820",
    `--user-data-dir=${profile}`,
    "--remote-debugging-port=0",
    "about:blank",
  ],
  { stdio: "ignore" },
);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws;
try {
  const portFile = path.join(profile, "DevToolsActivePort");
  for (let waited = 0; !fs.existsSync(portFile); waited += 100) {
    if (waited > 30000) {
      throw new Error("no devtools port");
    }
    await sleep(100);
  }
  await sleep(200);
  const [port, wsPath] = fs.readFileSync(portFile, "utf8").trim().split("\n");
  ws = new WebSocket(`ws://127.0.0.1:${port}${wsPath}`);
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });
  let id = 0;
  const pending = new Map();
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) {
        reject(new Error(JSON.stringify(msg.error)));
      } else {
        resolve(msg.result);
      }
    }
  };
  const send = (method, params = {}, sessionId) =>
    new Promise((resolve, reject) => {
      id += 1;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
  const { targetInfos } = await send("Target.getTargets");
  const target = targetInfos.find((info) => info.type === "page");
  const { sessionId } = await send("Target.attachToTarget", {
    targetId: target.targetId,
    flatten: true,
  });
  await send("Page.enable", {}, sessionId);
  await send(
    "Page.addScriptToEvaluateOnNewDocument",
    { source: fs.readFileSync(probePath, "utf8") },
    sessionId,
  );
  await send("Page.navigate", { url }, sessionId);
  await sleep(1000);
  const evaluated = await send(
    "Runtime.evaluate",
    {
      expression: "globalThis.__webkitGate.done.then((record) => JSON.stringify(record))",
      awaitPromise: true,
      returnByValue: true,
    },
    sessionId,
  );
  const record = JSON.parse(evaluated.result.value);
  const version = await send("Browser.getVersion");
  record.engine = { name: "Chrome", product: version.product };
  fs.writeFileSync(outPath, JSON.stringify(record, null, 1));
  try {
    await send("Browser.close");
  } catch {}
} finally {
  ws?.close();
  await sleep(500);
  child.kill("SIGKILL");
  fs.rmSync(profile, { recursive: true, force: true });
}
