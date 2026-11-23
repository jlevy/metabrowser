// Whether every cell the Treemap draws lies inside its parent folder's cell and inside the
// map's border, as Chrome lays the cells out: a served folder, the shell's page, and
// headless Chrome.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/treemap-containment-chrome.mjs METAB ROOT PORT STATE_DIR
//
// tests/test_treemap_containment_chrome.py writes the folder, owns the profile and
// STATE_DIR, runs this in a process group of its own, which Chrome and the server join,
// and judges what it prints: one JSON line of readings.
//
// The layout's rectangles are contained by construction, and
// tests/dom/treemap-layout-behavior.js holds that. What only a browser can say is what the
// stylesheet makes of them: a cell's padding and edge set a floor on the box it draws, and
// a cell drawn larger than its rectangle spills over its neighbours and past its folder.
import { spawn } from "node:child_process";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state] = process.argv.slice(2);
const base = `http://127.0.0.1:${port}`;
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);

async function serve() {
  const server = spawn(
    metab,
    [
      root,
      "--no-open",
      "--port",
      port,
      "--cache-dir",
      path.join(state, "cache"),
      "--config-dir",
      path.join(state, "config"),
    ],
    {
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, METABROWSER_LOG_LEVEL: "WARNING" },
    },
  );
  const exited = new Promise((resolve) => server.once("exit", resolve));
  let output = "";
  await new Promise((resolve, reject) => {
    const bound = setTimeout(() => reject(new Error(`no server: ${output}`)), 30000);
    const read = (chunk) => {
      output += chunk;
      if (output.includes("Serving ") && output.includes(base)) {
        clearTimeout(bound);
        resolve();
      }
    };
    server.stdout.on("data", read);
    server.stderr.on("data", read);
    server.once("exit", () => reject(new Error(`server exited: ${output}`)));
  });
  return {
    async stop() {
      server.kill("SIGTERM");
      let bound;
      await Promise.race([exited, new Promise((resolve) => (bound = setTimeout(resolve, 20000)))]);
      clearTimeout(bound);
      if (server.exitCode === null && server.signalCode === null) {
        server.kill("SIGKILL");
        await exited;
      }
    },
  };
}

// Every drawn cell against its parent folder's drawn cell (a remainder carries its folder's
// own path) and against the viewport's padding box, the box cells are placed in. A cell
// may meet an edge; past it by more than a rounding step is an escape.
const READ = `(() => {
  const SLACK = 0.05;
  const viewport = document.querySelector(".tm-viewport");
  const outer = viewport.getBoundingClientRect();
  const inner = {
    left: outer.left + viewport.clientLeft,
    top: outer.top + viewport.clientTop,
    right: outer.left + viewport.clientLeft + viewport.clientWidth,
    bottom: outer.top + viewport.clientTop + viewport.clientHeight,
  };
  const cells = [...viewport.querySelectorAll(".tm-cell")];
  const folders = new Map(
    cells.filter((cell) => cell.dataset.tmKind === "dir").map((cell) => [cell.dataset.tmPath, cell]),
  );
  const past = (box, within) =>
    Math.max(within.left - box.left, box.right - within.right, within.top - box.top, box.bottom - within.bottom);
  const escapes = [];
  let tiny = 0;
  let deepest = 0;
  // The keyboard reaches each actionable cell by one data-tm-index: its label when it
  // has one and nests, its own cell otherwise, a framed folder's included.
  let misindexed = 0;
  let framed = 0;
  for (const cell of cells) {
    const indexed = [cell, ...cell.querySelectorAll("[data-tm-index]")].filter((element) =>
      element.hasAttribute("data-tm-index"),
    );
    const actionable = cell.classList.contains("tm-actionable");
    if (cell.classList.contains("tm-framed")) {
      framed += 1;
      if (actionable && cell.getAttribute("role") !== "button") misindexed += 1;
    }
    if (indexed.length !== (actionable ? 1 : 0)) misindexed += 1;
    const box = cell.getBoundingClientRect();
    const declared = parseFloat(cell.style.width);
    if (declared < 8 || parseFloat(cell.style.height) < 8) tiny += 1;
    const cellPath = cell.dataset.tmPath;
    deepest = Math.max(deepest, cellPath ? cellPath.split("/").length : 0);
    const parentPath = cell.dataset.tmKind === "rest" ? cellPath : cellPath.split("/").slice(0, -1).join("/");
    const parent = parentPath ? folders.get(parentPath) : null;
    const overParent = parent && parent !== cell ? past(box, parent.getBoundingClientRect()) : 0;
    const overView = past(box, inner);
    const drawnWider = box.width - declared;
    if (overParent > SLACK || overView > SLACK || drawnWider > SLACK) {
      escapes.push({
        path: cellPath,
        kind: cell.dataset.tmKind,
        overParent: Math.round(overParent * 100) / 100,
        overView: Math.round(overView * 100) / 100,
        drawnWider: Math.round(drawnWider * 100) / 100,
      });
    }
  }
  return {
    cells: cells.length,
    tiny,
    deepest,
    framed,
    misindexed,
    escapes: escapes.length,
    sample: escapes.slice(0, 8),
  };
})()`;

const server = await serve();
phase("served");
let chrome = null;
try {
  chrome = await launchChrome(process.env.CHROME_BIN, {
    profiles: process.env.CHROME_PROFILES,
    width: 1280,
    height: 900,
  });
  phase("chrome");
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `${base}/view/` });
  const TAB = `document.querySelector('#preview-pane > .tab-bar > .tab-btn[data-tab="treemap"]')`;
  await chrome.waitFor(`${TAB} !== null`, 30000);
  await chrome.evaluate(`${TAB}.click()`);
  // The map draws once the index has finished; the count settles when the last answer
  // has been laid out.
  await chrome.waitFor(`document.querySelectorAll(".tm-viewport .tm-cell").length > 100`, 30000);
  await chrome.evaluate(`new Promise((resolve) => setTimeout(resolve, 500))`);
  phase("loaded");
  /** @type {Record<string, any>} */
  const result = { wide: await chrome.evaluate(READ) };
  // A narrower window: the same tree in less room, so more of it is drawn small.
  await chrome.send("Emulation.setDeviceMetricsOverride", {
    width: 760,
    height: 600,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await chrome.evaluate(`new Promise((resolve) => setTimeout(resolve, 800))`);
  result.narrow = await chrome.evaluate(READ);
  phase("measured");
  process.stdout.write(`${JSON.stringify(result)}\n`);
} finally {
  await chrome?.close();
  await server.stop();
  phase("closed");
}
