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
// where they sit: the legend under the tally bars on its held line, the marked cells'
// pixels on the marks canvas, lifted without growth, the pointer's cell's shimmer under the
// labels, the marked bars and entry, the tooltip's words, and that no layout box in the view
// moves. The map paints its cells on a canvas, so its own reading, inspectTreemap
// (treemap-map.js), names them, and the canvases' pixels say what is drawn.
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
// The module the view loaded, whose inspectTreemap reads the map it mounted.
const MAP_MODULE = `performance.getEntriesByType("resource").map((e) => e.name).find((n) => n.endsWith("/treemap-map.js"))`;
const VIEWPORT = `document.querySelector(".folder-treemap-host .tm-viewport")`;
// The centre of a cell's rectangle, from the map's reading.
const CELL = (cellPath) => `(async () => {
  const { inspectTreemap } = await import(${MAP_MODULE});
  const viewport = ${VIEWPORT};
  const cell = inspectTreemap(viewport)?.cells.find((c) => c.path === ${JSON.stringify(cellPath)});
  if (!cell) return null;
  const box = viewport.getBoundingClientRect();
  return { x: box.left + viewport.clientLeft + cell.x + cell.w / 2, y: box.top + viewport.clientTop + cell.y + cell.h / 2 };
})()`;

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
  const { inspectTreemap } = await import(${MAP_MODULE});
  const viewport = ${VIEWPORT};
  const map = inspectTreemap(viewport);
  const anchor = viewport.querySelector(".tm-hover-anchor");
  const labels = viewport.querySelector(".tm-labels");
  const nameOf = (element) => {
    if (element.dataset.legendKey !== undefined) return "legend " + element.dataset.legendKey;
    if (element.dataset.segmentKey !== undefined) return element.closest("tr").querySelector("th").textContent + " " + element.dataset.segmentKey;
    if (element.dataset.tmCell !== undefined) return "cell " + map.cells[Number(element.dataset.tmCell)].path + " (" + element.dataset.hovered + ")";
    return "not a mark: " + element.className;
  };
  // The bars' and the legend's marks are elements; the map's are its reading's, a cell
  // the pointer is on marked as itself.
  const marks = [...host.querySelectorAll("[data-hovered]")].filter((element) => element !== anchor);
  const cellName = (i) => "cell " + map.cells[i].path + " (" + (i === map.hovered && anchor?.dataset.hovered === "self" ? "self" : "family") + ")";
  // A cell's family is the first element of its paint style's key (treemap-map.js, cellStyleKey).
  const familyOf = new Map(map.paint.filter((r) => r.tone === "fill").map((r) => [r.cell, JSON.parse(r.style)[0]]));
  // What the canvases hold: the paint canvas every cell, the marks canvas the marked cells'
  // copies. A leaf's fill centre is its own pixel; a nesting folder's is its frame's left
  // column, where one is drawn.
  const pixels = (canvas) => canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height);
  const paint = pixels(viewport.querySelector(".tm-paint"));
  const lifted = pixels(viewport.querySelector(".tm-marks"));
  const at = (image, x, y) => [...image.data.slice((y * image.width + x) * 4, (y * image.width + x) * 4 + 4)];
  const ownPixel = (rect) => {
    const cell = map.cells[rect.cell];
    if (!cell.nested) return [rect.x + (rect.w >> 1), rect.y + (rect.h >> 1)];
    const inner = map.paint.find((r) => r.cell === rect.cell && r.tone === "edge");
    return inner && inner.x > rect.x ? [rect.x, rect.y + (rect.h >> 1)] : null;
  };
  const markedSet = new Set(map.marked);
  const canvasReading = { liftedPixels: 0, markedLifted: true, copied: true, unmarkedClear: true, sampled: 0 };
  for (let p = 3; p < lifted.data.length; p += 4) if (lifted.data[p] > 0) canvasReading.liftedPixels += 1;
  for (const rect of map.paint.filter((r) => r.tone === "fill")) {
    const own = ownPixel(rect);
    if (!own) continue;
    canvasReading.sampled += 1;
    const on = at(lifted, ...own);
    if (markedSet.has(rect.cell)) {
      canvasReading.markedLifted &&= on[3] > 0;
      canvasReading.copied &&= JSON.stringify(on) === JSON.stringify(at(paint, ...own));
    } else {
      canvasReading.unmarkedClear &&= on[3] === 0;
    }
  }
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
    marked: [...marks.map(nameOf), ...map.marked.map(cellName)],
    // Every cell of the first marked cell's family, the cells of one family.
    familyCells: map.marked.length
      ? map.cells.flatMap((_, i) => (familyOf.get(i) === familyOf.get(map.marked[0]) ? ["cell " + map.cells[i].path + " (family)"] : []))
      : [],
    canvas: canvasReading,
    // The marks canvas lifts, and does not grow.
    lift: style(viewport.querySelector(".tm-marks")),
    anchor: anchor
      ? {
          name: nameOf(anchor),
          ...style(anchor),
          // The sheen is the anchor's lowest layer, and the anchor lies under the labels.
          sheenUnderLabel:
            getComputedStyle(anchor, "::after").zIndex === "-1" &&
            Boolean(anchor.compareDocumentPosition(labels) & Node.DOCUMENT_POSITION_FOLLOWING),
        }
      : null,
    barStyle: marks.filter((element) => element.classList.contains("file-type-summary-fill")).map(style),
    barsAtRest: fills.filter((fill) => !marks.includes(fill)).every((fill) => { const s = style(fill); return s.scaleY === 1 && s.filter === "none"; }),
    entries: marks.filter((element) => element.dataset.legendKey !== undefined).map((item) => {
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
    layout: [...host.querySelectorAll(".tm-label-cell, .tm-paint, .tm-marks, .tm-viewport, .tm-legend-row, .file-type-summary-legend-item, .folder-totals tr, .file-type-summary-track")].map(box),
    tooltip: shown() ? tip.innerText.replace(/\\s+/g, " ").trim() : null,
    tooltipBelowEntry: tipBox && document.querySelector(".tm-legend .file-type-summary-legend-item:hover") ? tipBox.top >= document.querySelector(".tm-legend .file-type-summary-legend-item:hover").getBoundingClientRect().bottom : null,
  };
})()`;

// Clicks the staged Treemap tab the moment the shell draws it, and says what it found:
// the tab in an inert stage, no tab bar committed to the pane yet, and the Overview in
// front on the staged bar.
const EARLY_CHOICE = `(() => {
  const observer = new MutationObserver(() => {
    const tab = document.querySelector('#preview-pane > .preview-file-stage > .tab-bar > .tab-btn[data-tab="treemap"]');
    if (!tab) return;
    observer.disconnect();
    window.__earlyTabChoice = {
      staged: tab.closest(".preview-file-stage").inert === true,
      committedTabs: document.querySelectorAll("#preview-pane > .tab-bar > .tab-btn").length,
      front: tab.parentElement.querySelector(".tab-btn.active")?.dataset.tab ?? null,
    };
    tab.click();
  });
  observer.observe(document, { childList: true, subtree: true });
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
  /** @type {Record<string, any>} */
  const result = {};
  // The Treemap tab, by its own control, chosen while the folder's first view still holds
  // its first paint (mb-s588): the click lands on the staged bar in the turn after the
  // shell draws it, before the Overview has its data. The observer's callback is a
  // microtask queued by the write that draws the stage, so it runs when the shell's render
  // first waits, which is the hold, however slow the page is. The shell used to wire the
  // staged bar after the hold, and this click did nothing.
  await chrome.send("Page.addScriptToEvaluateOnNewDocument", { source: EARLY_CHOICE });
  await chrome.send("Page.navigate", { url: `${base}/view/` });
  const TABS = `[...document.querySelectorAll("#preview-pane > .tab-bar > .tab-btn")]`;
  await chrome.waitFor("window.__earlyTabChoice !== undefined", 30000);
  result.earlyChoice = await chrome.evaluate("window.__earlyTabChoice");
  // A click the shell did not take fails here, by name, rather than as the next wait: the
  // folder commits with the tab chosen in front.
  await chrome.waitFor(`${TABS}.some((tab) => tab.classList.contains("active"))`, 30000);
  result.frontAtCommit = await chrome.evaluate(
    `${TABS}.find((tab) => tab.classList.contains("active")).textContent.trim()`,
  );
  if (result.frontAtCommit !== "Treemap") {
    throw new Error(`the tab chosen during the hold was lost: ${JSON.stringify(result)}`);
  }
  await chrome.waitFor(
    `document.querySelectorAll(".tm-legend .file-type-summary-legend-item").length > 0 && document.querySelectorAll(".folder-treemap-host .tm-label-cell").length > 0 && document.querySelectorAll(".folder-totals .file-type-summary-ignored-row [data-segment-key]").length > 0`,
    30000,
  );
  phase("loaded");
  // `where` evaluates to a point, or null.
  const move = async (where) => {
    const at = await chrome.evaluate(where);
    if (!at) {
      throw new Error(`nothing to point at: ${where}`);
    }
    await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: at.x, y: at.y });
  };
  const away = async () => {
    await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1270, y: 10 });
  };
  await away();
  result.atRest = await chrome.evaluate(READ);
  await move(CENTER(ENTRY("Python")));
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
