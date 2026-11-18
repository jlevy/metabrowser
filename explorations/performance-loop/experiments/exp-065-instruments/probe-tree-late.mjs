// H92(b) pilot instrument: a selected pull request's file tree whose list is not cached.
// Each run starts a fresh server on the corpus with empty cache and configuration
// directories, so the selected row's list comes from a GitHub refresh seconds after the
// click; it then records what the Pulls panel did with no input. Not committed product
// code: the round commits this script's output and names it in the artifact.
//
// node probe-tree-late.mjs --pairs 3 --control METAB --candidate METAB --corpus DIR \
//   --number 353 --out FILE
import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";

const args = Object.fromEntries(
  process.argv
    .slice(2)
    .join(" ")
    .split("--")
    .filter(Boolean)
    .map((part) => {
      const [key, ...rest] = part.trim().split(" ");
      return [key, rest.join(" ")];
    }),
);
const PAIRS = Number(args.pairs ?? 3);
const NUMBER = Number(args.number ?? 353);
const CORPUS = args.corpus;
const OUT = args.out;
const CONDITIONS = { control: args.control, candidate: args.candidate };
const SERVER_PORTS = [8930, 8936];
const CDP_PORT = 8938;
const CHROME =
  process.env.CHROME_BIN ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const WATCH_MS = 12000;
const LATE_MS = 500;
const HERE = path.dirname(new URL(import.meta.url).pathname);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const free = (port) =>
  new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.listen(port, "127.0.0.1", () => server.close(() => resolve(true)));
  });
async function pickPort() {
  for (let port = SERVER_PORTS[0]; port <= SERVER_PORTS[1]; port += 1) {
    if (await free(port)) {
      return port;
    }
  }
  throw new Error("no free port in 8930-8936");
}

async function startServer(metab, home) {
  const cache = path.join(home, "cache");
  const config = path.join(home, "config");
  fs.mkdirSync(cache, { recursive: true, mode: 0o700 });
  fs.mkdirSync(config, { recursive: true, mode: 0o700 });
  const port = await pickPort();
  const log = fs.openSync(path.join(home, "server.log"), "w");
  const child = spawn(
    metab,
    [CORPUS, "--no-open", "--port", String(port), "--cache-dir", cache, "--config-dir", config],
    {
      cwd: home,
      detached: true,
      stdio: ["ignore", log, log],
      env: { ...process.env, METABROWSER_CACHE_DIR: cache, METABROWSER_CONFIG_DIR: config },
    },
  );
  fs.closeSync(log);
  const base = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 180000;
  while (Date.now() < deadline) {
    try {
      const progress = await (await fetch(`${base}/api/index/progress`)).json();
      if (progress.complete) {
        const html = await (await fetch(`${base}/view/`)).text();
        const version = html.match(/<div class="menu-version">([^<]*)<\/div>/)?.[1] ?? null;
        return { child, base, port, version };
      }
    } catch {
      // Not listening yet.
    }
    await sleep(200);
  }
  process.kill(-child.pid, "SIGTERM");
  throw new Error("server did not finish its inventory");
}

async function launchChrome(profile) {
  const proc = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${CDP_PORT}`,
      `--user-data-dir=${profile}`,
      "--window-size=1440,900",
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-background-networking",
      "about:blank",
    ],
    { stdio: "ignore" },
  );
  let page;
  for (let i = 0; i < 100 && !page; i += 1) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json();
      page = list.find((t) => t.type === "page");
    } catch {
      await sleep(100);
    }
  }
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve) => ws.addEventListener("open", resolve, { once: true }));
  let id = 0;
  const pending = new Map();
  const exceptions = [];
  ws.addEventListener("message", (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id !== undefined && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) {
        reject(new Error(JSON.stringify(msg.error)));
      } else {
        resolve(msg.result);
      }
    } else if (msg.method === "Runtime.exceptionThrown") {
      exceptions.push(
        msg.params.exceptionDetails?.exception?.description?.slice(0, 200) ?? "exception",
      );
    }
  });
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      id += 1;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  const evaluate = async (expression) => {
    const result = await send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails) {
      throw new Error(JSON.stringify(result.exceptionDetails).slice(0, 400));
    }
    return result.result.value;
  };
  const click = async (x, y) => {
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
    await send("Input.dispatchMouseEvent", {
      type: "mousePressed",
      x,
      y,
      button: "left",
      clickCount: 1,
    });
    await sleep(40);
    await send("Input.dispatchMouseEvent", {
      type: "mouseReleased",
      x,
      y,
      button: "left",
      clickCount: 1,
    });
  };
  return {
    send,
    evaluate,
    click,
    exceptions,
    async close() {
      ws.close();
      proc.kill("SIGTERM");
      await sleep(500);
      fs.rmSync(profile, { recursive: true, force: true });
    },
  };
}

const center = (selector) => `(() => {
  const el = document.querySelector(${JSON.stringify(selector)});
  if (!el) { return null; }
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.left + Math.min(60, r.width / 2)), y: Math.round(r.top + r.height / 2) };
})()`;

async function until(b, expression, ms) {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    if (await b.evaluate(expression)) {
      return true;
    }
    await sleep(200);
  }
  return false;
}

async function oneRun(label, pair, order) {
  const home = fs.mkdtempSync(path.join(HERE, `tree-late-${label}-`));
  const startLoad = os.loadavg()[0];
  const server = await startServer(CONDITIONS[label], home);
  const b = await launchChrome(path.join(home, "chrome"));
  const row = `#tab-pulls a.github-pulls-row[data-number="${NUMBER}"]`;
  const result = {
    condition: label,
    pair,
    order,
    number: NUMBER,
    version: server.version,
    port: server.port,
    load: [startLoad],
  };
  try {
    await b.send("Page.enable");
    await b.send("Runtime.enable");
    await b.send("Page.navigate", { url: `${server.base}/pulls` });
    if (
      !(await until(
        b,
        "document.querySelectorAll('#tab-pulls a.github-pulls-row').length > 0",
        90000,
      ))
    ) {
      throw new Error("the Pulls list did not load");
    }
    const chip = await b.evaluate(center('.github-pulls-filters .chip[data-chip-value="closed"]'));
    if (chip === null) {
      throw new Error("no Closed chip");
    }
    await b.click(chip.x, chip.y);
    if (
      !(await until(
        b,
        `!!document.querySelector('#tab-pulls ul.github-pulls-list[data-filter="closed"]') && !!document.querySelector(${JSON.stringify(row)})`,
        90000,
      ))
    ) {
      throw new Error(`#${NUMBER} not in the Closed list`);
    }
    await b.evaluate(
      `document.querySelector(${JSON.stringify(row)}).scrollIntoView({ block: "center" })`,
    );
    await sleep(1500);
    // What the panel does from here: layout shifts, the reader's input, and the selected
    // row's tree, read once a frame.
    await b.evaluate(`(() => {
      const R = (window.__treeLate = { shifts: [], inputs: [], frames: [] });
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) {
          R.shifts.push({
            t: e.startTime, v: e.value, input: e.hadRecentInput,
            inPulls: (e.sources || []).some((s) => s.node && s.node.closest && s.node.closest('#tab-pulls')),
          });
        }
      }).observe({ type: "layout-shift" });
      for (const type of ["pointerdown", "keydown"]) {
        addEventListener(type, (e) => { if (e.isTrusted) { R.inputs.push(e.timeStamp); } }, true);
      }
      const rowSel = ${JSON.stringify(row)};
      const sample = () => {
        const link = document.querySelector(rowSel);
        const group = link && link.parentNode && link.parentNode.querySelector(':scope > .github-pull-files');
        const open = !!group && !group.classList.contains('tree-children-collapsed');
        const rows = open ? group.querySelectorAll('.github-pull-files-rows > *').length : 0;
        const offer = group && [...group.querySelectorAll('button.github-pull-text-action')].find((b) => !b.hidden);
        const last = R.frames.at(-1);
        const now = { t: performance.now(), open, rows, offer: offer ? offer.textContent : null };
        if (!last || last.open !== now.open || last.rows !== now.rows || last.offer !== now.offer) {
          R.frames.push(now);
        }
        requestAnimationFrame(sample);
      };
      requestAnimationFrame(sample);
      return true;
    })()`);
    const target = await b.evaluate(center(row));
    result.loadAtClick = os.loadavg()[0];
    await b.click(target.x, target.y);
    await sleep(WATCH_MS);
    const R = await b.evaluate("window.__treeLate");
    const clickAt = R.inputs[0] ?? null;
    const lastInput = R.inputs.at(-1) ?? null;
    const rel = (t) => (clickAt === null ? null : Math.round(t - clickAt));
    const lateFrom = lastInput === null ? null : lastInput + LATE_MS;
    const rowsAt = (t) => {
      let rows = 0;
      for (const f of R.frames) {
        if (f.t <= t) {
          rows = f.rows;
        }
      }
      return rows;
    };
    const end = R.frames.at(-1)?.rows ?? 0;
    const firstRows = R.frames.find((f) => f.rows > 0);
    const firstOffer = R.frames.find((f) => f.offer !== null);
    Object.assign(result, {
      inputs: R.inputs.length,
      panelShiftNoInput:
        Math.round(
          R.shifts.filter((s) => !s.input && s.inPulls).reduce((a, s) => a + s.v, 0) * 1e4,
        ) / 1e4,
      panelShiftInput:
        Math.round(
          R.shifts.filter((s) => s.input && s.inPulls).reduce((a, s) => a + s.v, 0) * 1e4,
        ) / 1e4,
      panelShiftsNoInput: R.shifts.filter((s) => !s.input && s.inPulls).length,
      rowsAtLate: lateFrom === null ? null : rowsAt(lateFrom),
      rowsAtEnd: end,
      rowsDrawnWithoutInput: lateFrom === null ? null : Math.max(0, end - rowsAt(lateFrom)),
      firstRowsMs: firstRows ? rel(firstRows.t) : null,
      firstOfferMs: firstOffer ? rel(firstOffer.t) : null,
      offer: firstOffer?.offer ?? null,
      treeFrames: R.frames.map((f) => [rel(f.t), f.open ? f.rows : "closed", f.offer]).slice(0, 30),
      exceptions: b.exceptions.slice(0, 5),
    });
  } catch (error) {
    result.error = String(error.message ?? error).slice(0, 300);
  } finally {
    await b.close();
    try {
      process.kill(-server.child.pid, "SIGTERM");
    } catch {
      // Gone.
    }
    await sleep(1500);
    result.load.push(os.loadavg()[0]);
    fs.rmSync(home, { recursive: true, force: true });
  }
  return result;
}

const rows = [];
if (args.only) {
  const result = await oneRun(args.only, 0, "smoke");
  console.log(JSON.stringify(result, null, 1));
  process.exit(0);
}
// The load rule, before any result is read: a pair is excluded when one of its runs saw a
// one-minute load above 12 at its start or at the click; pairs are added, up to MAX_PAIRS,
// until MIN_VALID pairs are left.
const LOAD_LIMIT = 12;
// Before each pair, the lock's gate: five load samples 30 s apart under the limit, at most an hour.
async function quiet() {
  const samples = [];
  const deadline = Date.now() + 60 * 60 * 1000;
  while (Date.now() < deadline) {
    samples.push(os.loadavg()[0]);
    if (samples.length >= 5 && samples.slice(-5).every((v) => v < LOAD_LIMIT)) {
      return;
    }
    await sleep(30000);
  }
}
const MIN_VALID = Number(args["min-valid"] ?? 3);
const MAX_PAIRS = Number(args["max-pairs"] ?? 6);
let validPairs = 0;
for (let pair = 1; pair <= MAX_PAIRS && (pair <= PAIRS || validPairs < MIN_VALID); pair += 1) {
  const order = pair % 2 === 1 ? ["control", "candidate"] : ["candidate", "control"];
  await quiet();
  const results = [];
  for (const label of order) {
    results.push(await oneRun(label, pair, order.join(",")));
  }
  const overLoad = results.some((r) => r.load[0] > LOAD_LIMIT || (r.loadAtClick ?? 0) > LOAD_LIMIT);
  const failed = results.some((r) => r.error !== undefined);
  const excluded = overLoad ? "load" : failed ? "error" : null;
  if (excluded === null) {
    validPairs += 1;
  }
  for (const result of results) {
    result.excluded = excluded;
    rows.push(result);
    fs.appendFileSync(OUT, `${JSON.stringify(result)}\n`);
    console.log(
      `${result.condition.padEnd(9)} pair ${pair}: load ${result.load.map((v) => v.toFixed(2)).join("/")} at click ${result.loadAtClick?.toFixed(2)} excluded ${excluded} ${result.error ?? ""}`,
    );
  }
}
console.log(`valid pairs ${validPairs}`);
