// The Treemap tab's file-type legend and the hover its cells, tally bars, and legend share,
// under Chrome's own pointer: a served folder, the shell's page, and headless Chrome.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/treemap-legend-hover-chrome.mjs METAB ROOT PORT STATE_DIR
//
// tests/test_treemap_legend_hover_chrome.py writes the folder, owns the profile and
// STATE_DIR, runs this in a process group of its own, which Chrome and the server join,
// and judges what it prints: one JSON line of readings.
//
// Which marks an entry, a cell, or a segment names, the tooltip it shows, and when the
// hover is put away run browserlessly in tests/dom/treemap-legend-session.js. What only a
// browser can say is that Chrome's pointer reaches them and what they then compute to and
// where they sit: the legend under the tally bars on its held line, the marked cells' lift
// without growth and their shimmer under their labels, the marked bars and entry, the
// tooltip's words, and that no layout box in the view moves.
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
const ENTRY = (label) =>
  `[...document.querySelectorAll(".tm-legend .file-type-summary-legend-item")].find((item) => item.querySelector(".file-type-summary-legend-label")?.textContent === ${JSON.stringify(label)})?.querySelector(".file-type-summary-legend-label")`;
const CELL = (cellPath) =>
  `document.querySelector(${JSON.stringify(`.tm-cell[data-tm-path="${cellPath}"]`)})`;

// What the hover draws once it has settled, after the shell's tooltip appear delay or fade
// (TOOLTIP_APPEAR_DELAY and TOOLTIP_FADE_OUT in static/app.js, read from the page) and the
// view's finite transitions; the shimmer is infinite and is read as it runs.
const READ = `(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const tip = document.querySelector(".custom-tooltip");
  const shown = () => tip?.style.display === "block" && tip.classList.contains("visible");
  const end = performance.now() + 3000;
  let last = null;
  while (performance.now() < end) {
    const now = JSON.stringify([shown(), tip?.style.display, tip?.textContent]);
    if (now === last) break;
    last = now;
    await wait(TOOLTIP_APPEAR_DELAY + TOOLTIP_FADE_OUT);
  }
  await Promise.all(
    document
      .getAnimations()
      .filter((animation) => animation.effect?.getComputedTiming().iterations !== Infinity)
      .map((animation) => animation.finished.catch(() => null)),
  );
  const round = (value) => Math.round(value * 100) / 100;
  const host = document.querySelector(".folder-treemap-host") ?? document.body;
  const nameOf = (element) => {
    if (element.dataset.legendKey !== undefined) return "legend " + element.dataset.legendKey;
    if (element.dataset.segmentKey !== undefined) return element.closest("tr").querySelector("th").textContent + " " + element.dataset.segmentKey;
    if (element.dataset.tmPath !== undefined) return "cell " + element.dataset.tmPath + " (" + element.dataset.hovered + ")";
    return "not a mark: " + element.className;
  };
  const marked = [...host.querySelectorAll("[data-hovered]")];
  const cells = [...host.querySelectorAll(".tm-cell")];
  const colorOf = (cell) => cell.style.getPropertyValue("--mb-distribution-color-light");
  const style = (element) => {
    const computed = getComputedStyle(element);
    const matrix = new DOMMatrixReadOnly(computed.transform === "none" ? undefined : computed.transform);
    return { scaleY: round(matrix.d), scaleX: round(matrix.a), filter: computed.filter };
  };
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 1;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  const rgb = (color) => {
    context.clearRect(0, 0, 1, 1);
    context.fillStyle = color;
    context.fillRect(0, 0, 1, 1);
    return [...context.getImageData(0, 0, 1, 1).data.slice(0, 3)];
  };
  const luminance = (channels) => {
    const [r, g, b] = channels.map((c) => {
      const v = c / 255;
      return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const ground = (element) => {
    for (let node = element; node; node = node.parentElement) {
      const color = getComputedStyle(node).backgroundColor;
      if (!/^rgba\\(0, 0, 0, 0\\)$|^transparent$/.test(color)) return rgb(color);
    }
    return [255, 255, 255];
  };
  const ratio = (a, b) => {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return round((hi + 0.05) / (lo + 0.05));
  };
  const box = (element) => {
    const r = element.getBoundingClientRect();
    return [r.left, r.top, r.width, r.height].map(round).join(",");
  };
  const fills = [...host.querySelectorAll(".file-type-summary-fill")];
  const legendRow = host.querySelector(".tm-legend-row");
  const shimmers = document.getAnimations().filter((animation) => animation.animationName === "viz-hover-shimmer");
  const tipBox = shown() ? tip.getBoundingClientRect() : null;
  return {
    legend: [...host.querySelectorAll(".tm-legend .file-type-summary-legend-item")].map((item) => item.querySelector(".file-type-summary-legend-label").textContent),
    legendName: host.querySelector(".tm-legend").getAttribute("aria-label"),
    // The legend sits under the tally bars, and its row is one line, the line it holds
    // while it has no entries.
    legendUnderBars: host.querySelector(".tm-totals").getBoundingClientRect().bottom <= legendRow.getBoundingClientRect().top,
    legendRowHeld: round(legendRow.getBoundingClientRect().height) === round(parseFloat(getComputedStyle(legendRow).minHeight)),
    marked: marked.map(nameOf),
    // Every cell painted the color of the first marked cell, the cells of one family.
    familyCells: (() => {
      const first = marked.find((element) => element.classList.contains("tm-cell"));
      return first
        ? cells
            .filter((cell) => colorOf(cell) === colorOf(first))
            .map((cell) => "cell " + cell.dataset.tmPath + " (family)")
        : [];
    })(),
    cellStyle: marked.filter((element) => element.classList.contains("tm-cell")).map((cell) => ({
      ...style(cell),
      marks: cell.dataset.hovered,
      sheenUnderLabel: getComputedStyle(cell, "::after").zIndex === "-1",
    })),
    cellsAtRest: cells.filter((cell) => !marked.includes(cell)).every((cell) => getComputedStyle(cell).filter === "none"),
    barStyle: marked.filter((element) => element.classList.contains("file-type-summary-fill")).map(style),
    barsAtRest: fills.filter((fill) => !marked.includes(fill)).every((fill) => { const s = style(fill); return s.scaleY === 1 && s.filter === "none"; }),
    entries: marked.filter((element) => element.dataset.legendKey !== undefined).map((item) => {
      const label = item.querySelector(".file-type-summary-legend-label");
      return {
        dotFilter: getComputedStyle(item.querySelector(".file-type-summary-legend-swatch")).filter,
        inkContrast: ratio(rgb(getComputedStyle(label).color), ground(item)),
      };
    }),
    shimmer: {
      on: shimmers.map((animation) => {
        const target = animation.effect.target;
        return nameOf(target.closest(".file-type-summary-legend-item") ?? target);
      }),
      animates: [...new Set(shimmers.flatMap((animation) => animation.effect.getKeyframes().flatMap((frame) => Object.keys(frame).filter((key) => !["offset", "easing", "composite", "computedOffset"].includes(key)))))],
    },
    layout: [...host.querySelectorAll(".tm-cell, .tm-viewport, .tm-legend-row, .file-type-summary-legend-item, .folder-totals tr, .file-type-summary-track")].map(box),
    tooltip: shown() ? tip.innerText.replace(/\\s+/g, " ").trim() : null,
    tooltipBelowEntry: tipBox && document.querySelector(".tm-legend .file-type-summary-legend-item:hover") ? tipBox.top >= document.querySelector(".tm-legend .file-type-summary-legend-item:hover").getBoundingClientRect().bottom : null,
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
  await chrome.send("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-color-scheme", value: "light" }],
  });
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `${base}/view/` });
  // The Treemap tab, by its own control, once the folder's first view is in front with its
  // legend drawn: while the Overview holds its first paint no tab is active, and a click
  // then is overridden when the Overview paints.
  const TABS = `[...document.querySelectorAll("#preview-pane > .tab-bar > .tab-btn")]`;
  await chrome.waitFor(
    `document.querySelector("#preview-pane > .tab-bar > .tab-btn.active") && document.querySelectorAll(".file-type-summary-legend-item").length > 0 && ${TABS}.some((tab) => tab.textContent.trim() === "Treemap")`,
    30000,
  );
  await chrome.evaluate(`${TABS}.find((tab) => tab.textContent.trim() === "Treemap").click()`);
  // A click the shell did not take fails here, by name, rather than as the next wait.
  await chrome.waitFor(
    `${TABS}.find((tab) => tab.textContent.trim() === "Treemap")?.classList.contains("active")`,
    10000,
  );
  await chrome.waitFor(
    `document.querySelectorAll(".tm-legend .file-type-summary-legend-item").length > 0 && document.querySelectorAll(".tm-cell").length > 0 && document.querySelectorAll(".folder-totals .file-type-summary-ignored-row [data-segment-key]").length > 0`,
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
  const away = async () => {
    await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1270, y: 10 });
  };
  const result = {};
  await away();
  result.atRest = await chrome.evaluate(READ);
  await move(ENTRY("Python"));
  result.entry = await chrome.evaluate(READ);
  await away();
  result.left = await chrome.evaluate(READ);
  await move(CELL("f1.py"));
  result.cell = await chrome.evaluate(READ);
  await away();
  result.cellLeft = await chrome.evaluate(READ);
  phase("hovered");
  process.stdout.write(`${JSON.stringify(result)}\n`);
} finally {
  await chrome?.close();
  await server.stop();
  phase("closed");
}
