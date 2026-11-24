// How many of the Treemap's cells name themselves, by a label or by an icon alone, as
// headless Chrome draws them: the measurement the label and icon bounds in treemap-map.js
// and treemap-layout.js record. Not a test; it prints one JSON line of readings.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/treemap-label-coverage-chrome.mjs METAB ROOT PORT STATE_DIR
//
// It serves ROOT, opens the Treemap view at 1400 by 900 and reads the map by Files and by
// Bytes, then the Overview's compact map. A cell counts when it is a file or a folder whose
// box is its own: a framed folder's children cover it, and a remainder is not one item.
import { spawn } from "node:child_process";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state] = process.argv.slice(2);
const base = `http://127.0.0.1:${port}`;

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
    const bound = setTimeout(() => reject(new Error(`no server: ${output}`)), 60000);
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
      await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 20000))]);
      if (server.exitCode === null && server.signalCode === null) {
        server.kill("SIGKILL");
        await exited;
      }
    },
  };
}

const FULL = ".tm-viewport:not(.tm-viewport-compact)";
const COMPACT = ".tm-viewport-compact";
const MAP_MODULE = `performance.getEntriesByType("resource").map((e) => e.name).find((n) => n.endsWith("/treemap-map.js"))`;

// The cells that could name themselves, those that do by a label, by an icon alone, or
// not at all, and the icon sizes Chrome gives the glyphs it draws.
const read = (selector) => `(async () => {
  const { inspectTreemap } = await import(${MAP_MODULE});
  const viewport = document.querySelector(${JSON.stringify(selector)});
  const map = inspectTreemap(viewport);
  const own = (c) => (c.kind === "file" || c.kind === "dir") && !c.framed && c.parent !== -1;
  const nameable = map.cells.filter(own).length;
  const labels = map.labels.filter((i) => own(map.cells[i])).length;
  const icons = map.icons.filter((icon) => own(map.cells[icon.cell])).length;
  const glyphSizes = (selector) => {
    const sizes = {};
    for (const svg of viewport.querySelectorAll(selector)) {
      const px = Math.round(svg.getBoundingClientRect().width * 10) / 10;
      sizes[px] = (sizes[px] || 0) + 1;
    }
    return sizes;
  };
  // The short sides of the cells that name themselves not at all, by whole pixel.
  const shown = new Set([...map.labels, ...map.icons.map((icon) => icon.cell)]);
  const unnamedShortSides = {};
  map.cells.forEach((c, i) => {
    if (!own(c) || shown.has(i)) return;
    const side = Math.floor(Math.min(c.w, c.h));
    const bucket = side >= 20 ? "20+" : String(side);
    unnamedShortSides[bucket] = (unnamedShortSides[bucket] || 0) + 1;
  });
  return {
    box: [viewport.clientWidth, viewport.clientHeight],
    cells: map.cells.length,
    nameable,
    labels,
    icons,
    named: labels + icons,
    namedShare: Math.round(((labels + icons) / Math.max(1, nameable)) * 1000) / 1000,
    labelGlyphs: glyphSizes(".tm-label-cell .file-identity-icon svg"),
    iconGlyphs: map.icons.reduce((sizes, { px }) => ({ ...sizes, [px]: (sizes[px] || 0) + 1 }), {}),
    unnamedShortSides,
  };
})()`;

const server = await serve();
let chrome = null;
try {
  chrome = await launchChrome(process.env.CHROME_BIN, {
    profiles: process.env.CHROME_PROFILES,
    width: 1400,
    height: 900,
  });
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `${base}/view/` });
  const drawn = (selector, least) =>
    `import(${MAP_MODULE}).then(({ inspectTreemap }) => (inspectTreemap(document.querySelector(${JSON.stringify(selector)}))?.cells.length ?? 0) > ${least})`;
  const settle = (ms) => chrome.evaluate(`new Promise((resolve) => setTimeout(resolve, ${ms}))`);
  await chrome.waitFor(`${MAP_MODULE} !== undefined`, 60000);
  await chrome.waitFor(drawn(COMPACT, 50), 120000);
  await settle(1500);
  /** @type {Record<string, any>} */
  const result = { compact: await chrome.evaluate(read(COMPACT)) };
  const TAB = `document.querySelector('#preview-pane > .tab-bar > .tab-btn[data-tab="treemap"]')`;
  await chrome.waitFor(`${TAB} !== null`, 30000);
  await chrome.evaluate(`${TAB}.click()`);
  await chrome.waitFor(drawn(FULL, 100), 120000);
  await settle(1500);
  result.files = await chrome.evaluate(read(FULL));
  await chrome.evaluate(
    `[...document.querySelectorAll("#preview-pane .folder-rollup-controls button")].find((b) => b.textContent.trim() === "Bytes" && b.offsetParent !== null).click()`,
  );
  await settle(1500);
  result.bytes = await chrome.evaluate(read(FULL));
  process.stdout.write(`${JSON.stringify(result)}\n`);
} finally {
  await chrome?.close();
  await server.stop();
}
