// File Overview's label column and its legend's wrap, in headless Chrome: a served folder of
// eleven file-type families, the shell's page, and its Overview at each pane width.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/overview-label-column-chrome.mjs METAB ROOT PORT STATE_DIR
//
// tests/test_overview_label_column_chrome.py writes the folder, owns the profile and
// STATE_DIR, runs this in a process group of its own, which Chrome and the server join, and
// judges what it prints: one JSON line of readings.
//
// The bars stand to the right of a label column, and where they start is layout: a width in
// file_type_summary.css, a share of the table in a narrow pane, the metric cell's padding,
// value, and gap, and the font of the longest label. Which only a browser computes. This
// reads, at each width in each font set, with Details closed and open and with Files and
// Bytes, where every row's label column ends and its bar starts, whether the Documentation
// heading and the Markdown row fit it on one line, what a label longer than the column does
// to the rows, and how the legend's entries wrap.
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

// What is on screen: both tables' rows, where each one's label column ends and its bar
// starts, measured from the table's left edge, the tokens that make them, the two labels
// the column is sized for, and the legend's entries.
const READ = `(() => {
  const round = (value) => Math.round(value * 100) / 100;
  const tables = [...document.querySelectorAll(".file-type-summary-table")];
  const tally = tables.find((table) => table.classList.contains("folder-totals-table"));
  const opened = document.querySelector(".file-type-summary-details-toggle")?.getAttribute("aria-expanded") === "true";
  const details = opened ? tables.find((table) => !table.classList.contains("folder-totals-table")) : undefined;
  const host = document.querySelector(".folder-overview-host");
  const rows = (table, kind) =>
    table
      ? [...table.querySelectorAll("tr")].flatMap((tr) => {
          const track = tr.querySelector(".file-type-summary-track");
          const heading = tr.querySelector("th");
          if (!track || !heading) return [];
          const box = table.getBoundingClientRect();
          return [{
            kind,
            label: heading.textContent.trim(),
            labelWidth: round(heading.getBoundingClientRect().width),
            barLeft: round(track.getBoundingClientRect().left - box.left),
          }];
        })
      : [];
  // The lines a label's words are drawn on, and whether they stay inside the heading cell.
  const lines = (cell, name) => {
    if (!cell) return null;
    const range = document.createRange();
    range.selectNodeContents(name);
    const rects = [...range.getClientRects()].filter((rect) => rect.width > 0);
    const cellBox = cell.getBoundingClientRect();
    return {
      lines: new Set(rects.map((rect) => Math.round(rect.top))).size,
      inside: rects.every((rect) => rect.right <= cellBox.right + 0.5),
      contentRight: round(Math.max(...rects.map((rect) => rect.right)) - cellBox.left),
    };
  };
  const documentation = details && [...details.querySelectorAll(".file-type-summary-group-row th")]
    .find((heading) => heading.textContent.trim() === "Documentation");
  const markdown = details?.querySelector('tr[data-type-key="family:markdown"] th');
  const special = (label) => details && [...details.querySelectorAll("tr[data-type-key] th")]
    .find((heading) => heading.querySelector("button span")?.textContent.trim() === label);
  const noExtension = special("No extension");
  const otherTypes = special("Other types");
  const entries = [...document.querySelectorAll(".file-type-summary-legend-item")].map((item) => {
    const box = item.getBoundingClientRect();
    const dot = item.querySelector(".file-type-summary-legend-swatch").getBoundingClientRect();
    const label = item.querySelector(".file-type-summary-legend-label").getBoundingClientRect();
    return {
      text: item.textContent.trim(),
      top: round(box.top),
      left: round(box.left),
      right: round(box.right),
      height: round(box.height),
      dotMiddle: round(dot.top + dot.height / 2 - box.top),
      labelMiddle: round(label.top + label.height / 2 - box.top),
    };
  });
  const legend = document.querySelector(".file-type-summary-legend");
  const legendBox = legend.getBoundingClientRect();
  const style = getComputedStyle(tally);
  return {
    host: round(host.getBoundingClientRect().width),
    table: round(tally.getBoundingClientRect().width),
    tableScroll: [tally.scrollWidth, tally.clientWidth],
    detailsOpen: Boolean(details),
    detailsScroll: details ? [details.scrollWidth, details.clientWidth] : null,
    rows: [...rows(tally, "tally"), ...rows(details, "details")],
    labelWidthToken: parseFloat(style.getPropertyValue("--file-type-summary-label-width")),
    metricPadding: parseFloat(style.getPropertyValue("--file-type-summary-metric-padding")),
    valueWidth: parseFloat(style.getPropertyValue("--file-type-summary-value-width")),
    metricGap: parseFloat(style.getPropertyValue("--file-type-summary-metric-gap")),
    documentation: lines(documentation, documentation?.lastElementChild),
    markdown: lines(markdown, markdown?.querySelector("button span")),
    noExtension: lines(noExtension, noExtension?.querySelector("button span")),
    otherTypes: lines(otherTypes, otherTypes?.querySelector("button span")),
    legend: { left: round(legendBox.left), right: round(legendBox.right), scroll: [legend.scrollWidth, legend.clientWidth], entries },
  };
})()`;

// A family row's label, replaced by one longer than the column, at its own cell, and what
// that does to every bar: the label is written to the row's two label spans, as the view
// writes them, and read back after the browser has laid it out.
const LONG_LABEL = (label) => `(() => {
  const round = (value) => Math.round(value * 100) / 100;
  const row = document.querySelector('.file-type-summary-table tr[data-type-key="family:markdown"]');
  const name = row.querySelector("button span");
  name.textContent = ${JSON.stringify(label)};
  row.querySelector(".file-type-summary-type-content > span:nth-child(2)").textContent = ${JSON.stringify(label)};
  const cell = row.querySelector("th");
  const box = cell.getBoundingClientRect();
  const table = row.closest("table");
  const range = document.createRange();
  range.selectNodeContents(name);
  const rects = [...range.getClientRects()].filter((rect) => rect.width > 0);
  return {
    cellWidth: round(box.width),
    cellHeight: round(box.height),
    lines: new Set(rects.map((rect) => Math.round(rect.top))).size,
    inside: rects.every((rect) => rect.right <= box.right + 0.5),
    tableScroll: [table.scrollWidth, table.clientWidth],
    bars: [...table.querySelectorAll(".file-type-summary-track")].map((track) => round(track.getBoundingClientRect().left - table.getBoundingClientRect().left)),
  };
})()`;

const server = await serve();
phase("served");
let chrome = null;
try {
  chrome = await launchChrome(process.env.CHROME_BIN, {
    profiles: process.env.CHROME_PROFILES,
    width: 1280,
    height: 1000,
  });
  phase("chrome");
  await chrome.send("Page.enable");
  await chrome.send("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-color-scheme", value: "light" }],
  });
  const settle = (ms) => chrome.evaluate(`new Promise((resolve) => setTimeout(resolve, ${ms}))`);
  const detailsOpen = () =>
    chrome.evaluate(
      `document.querySelector(".file-type-summary-details-toggle")?.getAttribute("aria-expanded") === "true"`,
    );
  const setDetails = async (open) => {
    if ((await detailsOpen()) !== open) {
      await chrome.evaluate(`document.querySelector(".file-type-summary-details-toggle").click()`);
      await settle(200);
    }
  };
  const setMeasure = async (name) => {
    await chrome.evaluate(
      `[...document.querySelectorAll(".folder-rollup-controls button")].find((button) => button.textContent.trim() === ${JSON.stringify(name)}).click()`,
    );
    await settle(200);
  };
  const result = {};
  // The pane's width is the window's less the navigation's. These put the Overview host
  // (the section's container) in each of the label column's regimes: a narrow pane's 28%,
  // the 24% above it, and the label width from the host width the rule names.
  const WIDTHS = [640, 760, 860, 960, 1280];
  for (const width of WIDTHS) {
    await chrome.send("Emulation.setDeviceMetricsOverride", {
      width,
      height: 1000,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await chrome.send("Page.navigate", { url: `${base}/view/` });
    await chrome.waitFor(
      `document.querySelectorAll(".file-type-summary-legend-item").length > 0 && document.querySelectorAll(".folder-totals .file-type-summary-files-row [data-segment-key]").length > 0`,
      30000,
    );
    await settle(500);
    result[width] = {};
    for (const font of ["clean", "system"]) {
      await chrome.evaluate(
        `document.documentElement.setAttribute("data-app-font", ${JSON.stringify(font)})`,
      );
      await chrome.evaluate(
        `document.fonts.ready.then(() => new Promise((resolve) => setTimeout(resolve, 200)))`,
      );
      const reading = {};
      for (const measure of ["Files", "Bytes"]) {
        await setMeasure(measure);
        for (const open of [false, true]) {
          await setDetails(open);
          reading[`${measure} ${open ? "open" : "closed"}`] = await chrome.evaluate(READ);
        }
      }
      await setMeasure("Files");
      await setDetails(true);
      if (width === 1280) {
        // Longer than the column: words that wrap at a space, and one word longer than the
        // column, which wraps inside it.
        reading.longWords = await chrome.evaluate(
          LONG_LABEL("Extraordinarily long plugin family name"),
        );
        reading.longWord = await chrome.evaluate(LONG_LABEL("Supercalifragilisticexpialidocious"));
      }
      result[width][font] = reading;
    }
    phase(`measured ${width}`);
  }
  phase("measured");
  process.stdout.write(`${JSON.stringify(result)}\n`);
} finally {
  await chrome?.close();
  await server.stop();
  phase("closed");
}
