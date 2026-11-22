// Measures what the table view's bounds were set from, in a real engine: how long a table
// drawn whole takes from its last answer to laid out, by its rows, and how long a window
// of a windowed table takes to redraw while scrolling. It is a measurement, not a test:
// nothing runs it in the suite, and its numbers are recorded beside the constants in
// src/metabrowser/builtin_plugins/table/table-view.js.
//
//   node tests/dom/table-view-measure.mjs METAB CHROME WORK_DIR [PORT] [held]
//
// WORK_DIR is a directory this writes and the caller removes: generated tables of 12
// columns (500, 1,000, 2,000, and 50,000 rows), a server's state, and Chrome's profile.
//
// With `held`, it measures instead what a windowed table costs as the reader scrolls on
// and the view holds every page it read: the JavaScript heap after a collection, a window's
// redraw, and drawing every row held for print, as the rows held grow to the most the
// delimited source parses of each shape, 12 columns to its byte bound (about 150,000
// rows) and 2 columns to its row bound (500,000 rows).
// To draw the tables of up to 2,000 rows whole, it serves the view's module with
// WHOLE_TABLE_MAX_ROWS raised to 2,000, and times the draw by marks it adds around it, through DevTools' request
// interception; the module on disk is not changed. Each table is opened three times, in
// turn, and every time is printed.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, chromeBin, work, port = "8798", mode = "draw"] = process.argv.slice(2);
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
if (mode === "held") {
  fs.writeFileSync(path.join(served, "wide150000.csv"), table(150000));
  fs.writeFileSync(
    path.join(served, "narrow500000.csv"),
    `n,word\n${Array.from({ length: 500000 }, (_, i) => `${i + 1},word ${i + 1}`).join("\n")}\n`,
  );
} else {
  for (const rows of sizes) {
    fs.writeFileSync(path.join(served, `rows${rows}.csv`), table(rows));
  }
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
      /^ {4}refit\(true\);\n/m,
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
  if (mode === "held") {
    await chrome.send("HeapProfiler.enable");
    for (const [file, marks] of [
      ["wide150000.csv", [200, 10000, 50000, 150000]],
      ["narrow500000.csv", [200, 50000, 150000, 500000]],
    ]) {
      await chrome.send("Page.navigate", { url: `${base}/view/${file}` });
      for (let i = 0; i < 1200; i++) {
        if (await chrome.evaluate("Boolean(window.__tableDraw)")) {
          break;
        }
        await sleep(50);
      }
      await sleep(500);
      results[file] = [];
      const started = Date.now();
      for (const mark of marks) {
        // Scroll to the end of what is held until the view holds *mark* rows or reads no more.
        const held = await chrome.evaluate(`(async () => {
          const scroll = document.querySelector(".table-view .table-scroll");
          const rowPx = document.querySelector(".table-view tbody tr:not(.table-spacer)").getBoundingClientRect().height;
          const heldRows = () => Math.round(document.querySelector(".table-view tbody").getBoundingClientRect().height / rowPx);
          let last = -1;
          let still = 0;
          while (heldRows() < ${mark} && still < 100) {
            scroll.scrollTop = scroll.scrollHeight;
            await new Promise((resolve) => setTimeout(resolve, 30));
            const now = heldRows();
            still = now === last ? still + 1 : 0;
            last = now;
          }
          return heldRows();
        })()`);
        await chrome.send("HeapProfiler.collectGarbage");
        const heap = await chrome.send("Runtime.getHeapUsage");
        await chrome.evaluate("window.__tableWindow = []");
        for (let step = 0; step < 10; step++) {
          await chrome.evaluate("document.querySelector('.table-scroll').scrollTop -= 300");
          await sleep(40);
        }
        const steps = await chrome.evaluate("window.__tableWindow");
        const print = await chrome.evaluate(`(() => {
          const mark = performance.now();
          window.dispatchEvent(new Event("beforeprint"));
          void document.body.offsetHeight;
          const ms = performance.now() - mark;
          window.dispatchEvent(new Event("afterprint"));
          return ms;
        })()`);
        results[file].push({
          rows_held: held,
          read_s: Math.round((Date.now() - started) / 100) / 10,
          heap_mb: Math.round(heap.usedSize / 1e5) / 10,
          window_step_ms: steps.length
            ? [Math.min(...steps), Math.max(...steps)].map((ms) => Number(ms.toFixed(1)))
            : null,
          print_draw_ms: Math.round(print),
        });
        console.error(file, JSON.stringify(results[file].at(-1)));
      }
    }
    console.log(JSON.stringify(results, null, 2));
  }
  for (let round = 0; round < (mode === "held" ? 0 : 3); round++) {
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
      results[file] ??= [];
      results[file].push({
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
