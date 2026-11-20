// Measures what the table view's bounds were set from, in a real engine: how long a table
// drawn whole takes from its last answer to laid out, by its rows, and how long a window
// of a windowed table takes to redraw while scrolling. It is a measurement, not a test:
// nothing runs it in the suite, and its numbers are recorded beside the constants in
// src/metabrowser/builtin_plugins/table/table-view.js.
//
//   node tests/dom/table-view-measure.mjs METAB CHROME WORK_DIR [PORT]
//
// WORK_DIR is a directory this writes and the caller removes: generated tables of 12
// columns (500, 1,000, 2,000, and 50,000 rows), a server's state, and Chrome's profile.
// To draw the tables of up to 2,000 rows whole, it serves the view's module with
// WHOLE_TABLE_MAX_ROWS raised to 2,000, and times the draw by marks it adds around it, through DevTools' request
// interception; the module on disk is not changed. Each table is opened three times, in
// turn, and every time is printed.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, chromeBin, work, port = "8798"] = process.argv.slice(2);
if (!metab || !chromeBin || !work) {
  console.error("usage: node tests/dom/table-view-measure.mjs METAB CHROME WORK_DIR [PORT]");
  process.exit(2);
}
const base = `http://127.0.0.1:${port}`;
const sleep = (/** @type {number} */ ms) => new Promise((resolve) => setTimeout(resolve, ms));
const served = path.join(work, "served");
fs.mkdirSync(served, { recursive: true });
fs.mkdirSync(path.join(work, "profiles"), { recursive: true });

/** @param {number} rows */
function table(rows) {
  const cities = ["Oslo", "Lima", "Paris", "Tokyo", "Cairo", "Quito"];
  const lines = ["id,name,city,amount,ratio,created,active,status,code,notes,count,label"];
  for (let i = 1; i <= rows; i++) {
    lines.push(
      [
        i,
        `Person ${i}`,
        cities[i % 6],
        ((i * 37) % 10000) / 7,
        (i % 97) / 97,
        `2024-0${1 + (i % 9)}-1${i % 9}`,
        i % 3 === 0,
        ["open", "closed", "pending"][i % 3],
        `C${(i * 7919) % 100000}`,
        `note for row ${i}`,
        i % 50,
        `L${i}`,
      ].join(","),
    );
  }
  return `${lines.join("\n")}\n`;
}
const sizes = [500, 1000, 2000, 50000];
for (const rows of sizes) {
  fs.writeFileSync(path.join(served, `rows${rows}.csv`), table(rows));
}

const server = spawn(
  metab,
  [
    served,
    "--no-open",
    "--port",
    port,
    "--cache-dir",
    path.join(work, "cache"),
    "--config-dir",
    path.join(work, "config"),
  ],
  {
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, METABROWSER_LOG_LEVEL: "WARNING", METABROWSER_EVENT_LOG: "0" },
  },
);
let output = "";
server.stdout.on("data", (chunk) => (output += chunk));
server.stderr.on("data", (chunk) => (output += chunk));
for (let i = 0; i < 300 && !output.includes(base); i++) {
  await sleep(100);
}
const chrome = await launchChrome(chromeBin, {
  profiles: path.join(work, "profiles"),
  width: 1280,
  height: 800,
});
try {
  await chrome.send("Page.enable");
  await chrome.send("Network.enable");
  await chrome.send("Network.setCacheDisabled", { cacheDisabled: true });
  await chrome.send("Fetch.enable", {
    patterns: [{ urlPattern: "*table-view.js*", requestStage: "Response" }],
  });
  chrome.on("Fetch.requestPaused", async (/** @type {any} */ event) => {
    const body = await chrome.send("Fetch.getResponseBody", { requestId: event.requestId });
    let text = body.base64Encoded ? Buffer.from(body.body, "base64").toString() : body.body;
    text = text.replace(/WHOLE_TABLE_MAX_ROWS = \d+/, "WHOLE_TABLE_MAX_ROWS = 2000");
    text = text.replace(
      "    refit(true);\n",
      "    const mark = performance.now(); refit(true); void document.body.offsetHeight; window.__tableDraw = performance.now() - mark;\n",
    );
    text = text.replace(
      "  function drawWindow(force = false) {",
      "  function drawWindow(force = false) { const mark = performance.now(); try { return drawWindowNow(force); } finally { (window.__tableWindow ||= []).push(performance.now() - mark); } }\n  function drawWindowNow(force = false) {",
    );
    await chrome.send("Fetch.fulfillRequest", {
      requestId: event.requestId,
      responseCode: 200,
      responseHeaders: [{ name: "Content-Type", value: "text/javascript" }],
      body: Buffer.from(text).toString("base64"),
    });
  });
  /** @type {Record<string, Array<Record<string, unknown>>>} */
  const results = {};
  for (let round = 0; round < 3; round++) {
    for (const rows of sizes) {
      const file = `rows${rows}.csv`;
      await chrome.send("Page.navigate", { url: `${base}/view/${file}` });
      let draw = null;
      for (let i = 0; i < 600 && draw === null; i++) {
        draw = await chrome.evaluate("window.__tableDraw ?? null");
        await sleep(50);
      }
      await sleep(300);
      /** @type {number[]} */
      let steps = [];
      if (rows === 50000) {
        await chrome.evaluate("window.__tableWindow = []");
        for (let step = 0; step < 20; step++) {
          await chrome.evaluate("document.querySelector('.table-scroll').scrollTop += 300");
          await sleep(40);
        }
        steps = await chrome.evaluate("window.__tableWindow");
      }
      (results[file] ||= []).push({
        draw_ms: Math.round(draw),
        drawn_rows: await chrome.evaluate(
          "document.querySelectorAll('.table-view tbody tr:not(.table-spacer)').length",
        ),
        row_px: await chrome.evaluate(
          "document.querySelector('.table-view tbody tr:not(.table-spacer)').getBoundingClientRect().height",
        ),
        window_step_ms: steps.length
          ? [Math.min(...steps), Math.max(...steps)].map((ms) => Number(ms.toFixed(1)))
          : null,
      });
    }
  }
  console.log(JSON.stringify(results, null, 2));
} finally {
  await chrome.close();
  server.kill();
}
