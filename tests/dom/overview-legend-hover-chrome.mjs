// File Overview's legend and the population bars above it, under Chrome's own pointer: a
// served folder, the shell's page, and headless Chrome.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/overview-legend-hover-chrome.mjs METAB ROOT PORT STATE_DIR
//
// tests/test_overview_legend_hover_chrome.py writes the folder, owns the profile and
// STATE_DIR, runs this in a process group of its own, which Chrome and the server join,
// and judges what it prints: one JSON line of readings.
//
// A legend entry is a second handle on its family's segment (docs/design-system.md,
// "Aggregate Distributions"). Which segment an entry names, the tooltip it shows, and
// when the hover is put away run browserlessly in tests/dom/file-overview-session.js.
// What only a browser can say is that Chrome's pointer reaches them: that moving it onto
// an entry's name and its dot lifts and grows the segment, in the computed style, and
// shows the segment's file count and byte size, placed on the entry the pointer is on;
// that moving it off puts both away; and that pointing at the segment itself lifts the
// same segment and shows the same counts under the family's name, placed on the segment.
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
      // The bound is cleared once the server exits: left pending, it held this process
      // open for the rest of its 20 s after the last reading.
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

// The centre of an element's box, for Chrome's pointer.
const CENTER = (selector) => `(() => {
  const element = ${selector};
  if (!element) return null;
  const box = element.getBoundingClientRect();
  return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
})()`;
const ENTRY = (label, part) =>
  `[...document.querySelectorAll(".file-type-summary-legend-item")].find((item) => item.querySelector(".file-type-summary-legend-label")?.textContent === ${JSON.stringify(label)})?.querySelector(".file-type-summary-legend-${part}")`;
const SEGMENT = (row, key) =>
  `document.querySelector(${JSON.stringify(`.folder-totals .file-type-summary-${row}-row [data-segment-key="${key}"]`)})`;

// What the hover draws once it has settled: the segments marked as hovered, with each
// one's row, its computed lift and growth, and the tooltip's words and box against the
// handle it is anchored on, the legend entry or the segment the pointer is on. Waits out
// the shell's tooltip appear delay and fade (TOOLTIP_APPEAR_DELAY and TOOLTIP_FADE_OUT in
// static/app.js, read from the page) and the segment's transition rather than guessing
// at them.
const READ = `(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const tip = document.querySelector(".custom-tooltip");
  const shown = () => tip?.style.display === "block" && tip.classList.contains("visible");
  const end = performance.now() + 3000;
  // Up, or gone, and holding still for two reads an appear delay and a fade apart, so a
  // tooltip on its way up or out is never read as settled.
  let last = null;
  while (performance.now() < end) {
    const now = JSON.stringify([shown(), tip?.style.display, tip?.textContent]);
    if (now === last) break;
    last = now;
    await wait(TOOLTIP_APPEAR_DELAY + TOOLTIP_FADE_OUT);
  }
  const marked = [...document.querySelectorAll(".folder-totals [data-hovered]")];
  await Promise.all(
    marked.flatMap((element) => element.getAnimations().map((animation) => animation.finished)),
  );
  const segments = [...document.querySelectorAll(".folder-totals [data-segment-key]")];
  const round = (value) => Math.round(value * 100) / 100;
  const style = (element) => {
    const computed = getComputedStyle(element);
    const matrix = new DOMMatrixReadOnly(computed.transform === "none" ? undefined : computed.transform);
    return { scaleY: round(matrix.d), scaleX: round(matrix.a), filter: computed.filter };
  };
  const rowOf = (element) => element.closest("tr").querySelector("th").textContent;
  const tipBox = shown() ? tip.getBoundingClientRect() : null;
  return {
    marked: marked.map((element) => rowOf(element) + " " + element.dataset.segmentKey),
    markedStyle: marked.map(style),
    // Every other segment as it is at rest.
    othersAtRest: segments
      .filter((element) => !marked.includes(element))
      .every((element) => {
        const { scaleY, scaleX, filter } = style(element);
        return scaleY === 1 && scaleX === 1 && filter === "none";
      }),
    legendMarked: [...document.querySelectorAll(".file-type-summary-legend [data-hovered]")].length,
    tooltip: shown() ? tip.innerText.replace(/\\s+/g, " ").trim() : null,
    // Where the tooltip sits: its centre against the centre of what the pointer is on,
    // the legend entry under it or else the marked segment, and whether it is above or
    // below that rather than over it.
    tooltipOnAnchor:
      tipBox && marked.length === 1
        ? (() => {
            const entry = document.querySelector(".file-type-summary-legend-item:hover");
            const box = (entry ?? marked[0]).getBoundingClientRect();
            return {
              anchor: entry ? "legend" : "segment",
              centerOffset: round(tipBox.left + tipBox.width / 2 - (box.left + box.width / 2)),
              clear: tipBox.top >= box.bottom || tipBox.bottom <= box.top,
            };
          })()
        : null,
    tooltipLeft: tipBox ? round(tipBox.left) : null,
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
  await chrome.waitFor(
    `document.querySelectorAll(".file-type-summary-legend-item").length > 0 && document.querySelectorAll(".folder-totals .file-type-summary-total-row [data-segment-key]").length > 0`,
    30000,
  );
  phase("loaded");
  const move = async (expression) => {
    const at = await chrome.evaluate(CENTER(expression));
    if (!at) {
      throw new Error(`nothing to point at: ${expression}`);
    }
    await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: at.x, y: at.y });
  };
  // A place on the page with nothing under it: the section's empty right side.
  const away = async () => {
    await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1270, y: 890 });
  };
  const result = {};
  result.legend = await chrome.evaluate(
    `[...document.querySelectorAll(".file-type-summary-legend-item")].map((item) => item.querySelector(".file-type-summary-legend-label").textContent)`,
  );
  result.atRest = await chrome.evaluate(READ);
  await move(ENTRY("Python", "label"));
  result.entryName = await chrome.evaluate(READ);
  // From the name to the dot, within the one entry: the tooltip holds still.
  await move(ENTRY("Python", "swatch"));
  result.entryDot = await chrome.evaluate(READ);
  await away();
  result.left = await chrome.evaluate(READ);
  await move(SEGMENT("total", "family:python"));
  result.segment = await chrome.evaluate(READ);
  await away();
  result.segmentLeft = await chrome.evaluate(READ);
  await move(ENTRY("Other", "label"));
  result.other = await chrome.evaluate(READ);
  await away();
  phase("hovered");
  process.stdout.write(`${JSON.stringify(result)}\n`);
} finally {
  await chrome?.close();
  await server.stop();
  phase("closed");
}
