// What Chrome draws of the Treemap, in its view and in the Overview's compact map: the
// cells the canvas paints, the labels over them, and the pointer and keyboard on them, from
// a served folder, the shell's page, and headless Chrome.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/treemap-containment-chrome.mjs METAB ROOT PORT STATE_DIR
//
// tests/test_treemap_containment_chrome.py writes the folder, owns the profile and
// STATE_DIR, runs this in a process group of its own, which Chrome and the server join,
// and judges what it prints: one JSON line of readings.
//
// The layout's rectangles are contained by construction, and the paint list, mark ops, and
// hit grid follow from them (tests/dom/treemap-layout-behavior.js,
// tests/dom/treemap-paint-hit-behavior.js). What only a browser can say is what it draws of
// them: the pixels the canvas holds at each cell, the boxes the stylesheet gives the
// labels, and what the pointer and the keys reach. The map's own reading,
// inspectTreemap (treemap-map.js), names the cells; the page's pixels and elements are
// checked against it.
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

// The Treemap view's map, and the compact one on the Overview.
const FULL = ".tm-viewport:not(.tm-viewport-compact)";
const COMPACT = ".tm-viewport-compact";

// The module the view loaded, whose inspectTreemap reads the map it mounted.
const MAP_MODULE = `performance.getEntriesByType("resource").map((e) => e.name).find((n) => n.endsWith("/treemap-map.js"))`;

// Every painted cell's pixels and every label's box, against the map's own reading. A label
// may meet its cell's edge; past it, or past the viewport's padding box, by more than its
// rounding is an escape. A cell's center pixel is its fill: sampled for every cell at
// least 6 device pixels on a side, whose center no child covers, and held against the
// color its style resolved to from its probe (inspectTreemap's styles), for the opaque
// styles, whose pixel is that color alone.
const read = (selector) => `(async () => {
  // A label's left and width are written to a tenth of a pixel, each rounding by up to 0.05.
  const SLACK = 0.1 + 1e-6;
  const { inspectTreemap } = await import(${MAP_MODULE});
  const viewport = document.querySelector(${JSON.stringify(selector)});
  const map = inspectTreemap(viewport);
  const outer = viewport.getBoundingClientRect();
  const inner = {
    left: outer.left + viewport.clientLeft,
    top: outer.top + viewport.clientTop,
    right: outer.left + viewport.clientLeft + viewport.clientWidth,
    bottom: outer.top + viewport.clientTop + viewport.clientHeight,
  };
  const past = (box, within) =>
    Math.max(within.left - box.left, box.right - within.right, within.top - box.top, box.bottom - within.bottom);
  const escapes = [];
  for (const label of viewport.querySelectorAll(".tm-label-cell")) {
    const cell = map.cells[Number(label.dataset.tmCell)];
    const box = label.getBoundingClientRect();
    const own = { left: inner.left + cell.x, top: inner.top + cell.y, right: inner.left + cell.x + cell.w, bottom: inner.top + cell.y + cell.h };
    const over = Math.max(past(box, own), past(box, inner));
    if (over > SLACK) escapes.push({ path: cell.path, over: Math.round(over * 100) / 100 });
  }
  // The paint canvas's pixel at each sampled cell's center, against the fill its probe
  // resolved, drawn once on a scratch canvas.
  const scratch = document.createElement("canvas");
  scratch.width = scratch.height = 1;
  const scratchCtx = scratch.getContext("2d", { willReadFrequently: true });
  const rgb = (color) => {
    scratchCtx.clearRect(0, 0, 1, 1);
    scratchCtx.fillStyle = color;
    scratchCtx.fillRect(0, 0, 1, 1);
    return [...scratchCtx.getImageData(0, 0, 1, 1).data.slice(0, 3)];
  };
  const canvas = viewport.querySelector("canvas.tm-paint");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  const covered = new Set(map.cells.map((c) => c.parent));
  const byCell = new Map(map.paint.filter((r) => r.tone === "fill").map((r) => [r.cell, r]));
  let sampled = 0;
  let wrong = 0;
  const wrongSample = [];
  const fills = new Map();
  for (const [i, rect] of byCell) {
    const style = map.styles[rect.style];
    if (covered.has(i) || rect.w < 6 || rect.h < 6 || !style || style.alpha !== 1) continue;
    const cx = rect.x + Math.floor(rect.w / 2);
    const cy = rect.y + Math.floor(rect.h / 2);
    const k = (cy * canvas.width + cx) * 4;
    const got = [pixels[k], pixels[k + 1], pixels[k + 2]];
    const want = rgb(style.fill);
    fills.set(rect.style, want);
    sampled += 1;
    if (got.some((v, c) => Math.abs(v - want[c]) > 2)) {
      wrong += 1;
      if (wrongSample.length < 4) wrongSample.push({ path: map.cells[i].path, got, want });
    }
  }
  // Distinct styles paint distinct colors: two styles with one color would be a probe that
  // read nothing.
  const distinct = new Set([...fills.values()].map((v) => v.join(","))).size;
  let deepest = 0;
  let tiny = 0;
  for (const cell of map.cells) {
    deepest = Math.max(deepest, cell.path ? cell.path.split("/").length : 0);
    if (cell.w < 8 || cell.h < 8) tiny += 1;
  }
  // Every folder and file opens something, but in the Treemap view the outer box is the
  // view's own folder and opens nothing; on the compact map it opens the view.
  const ownFolderOpens = ${JSON.stringify(selector)} === ${JSON.stringify(COMPACT)};
  const actionable = map.cells.filter(
    (c) => (c.kind === "dir" || c.kind === "file") && (ownFolderOpens || c.parent !== -1),
  ).length;
  return {
    cells: map.cells.length,
    painted: map.paint.length,
    tiny,
    deepest,
    labels: viewport.querySelectorAll(".tm-label-cell").length,
    escapes: escapes.length,
    sample: escapes.slice(0, 8),
    sampled,
    styles: fills.size,
    distinct,
    wrongFill: wrong,
    wrongSample,
    resolved: Object.fromEntries([...fills].map(([key, value]) => [key, value.join(",")])),
    focusable: viewport.querySelectorAll('[tabindex="0"]').length,
    focusOrder: map.focusOrder.length,
    actionable,
    domElements: viewport.querySelectorAll("*").length,
  };
})()`;

// Point at the smallest unlabelled file cell large enough to aim at, through the browser's
// own input, and read what the map says is hovered and what the tooltip says; then click it.
const point = (selector) => `(async () => {
  const { inspectTreemap } = await import(${MAP_MODULE});
  const viewport = document.querySelector(${JSON.stringify(selector)});
  const map = inspectTreemap(viewport);
  const labelled = new Set(map.labels);
  const covered = new Set(map.cells.map((c) => c.parent));
  let target = -1;
  map.cells.forEach((c, i) => {
    if (c.kind !== "file" || labelled.has(i) || covered.has(i) || c.w < 3 || c.h < 3) return;
    if (target < 0 || c.w * c.h < map.cells[target].w * map.cells[target].h) target = i;
  });
  const rect = viewport.getBoundingClientRect();
  const cell = map.cells[target];
  return {
    index: target,
    path: cell.path,
    x: rect.left + viewport.clientLeft + cell.x + cell.w / 2,
    y: rect.top + viewport.clientTop + cell.y + cell.h / 2,
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
  // The Overview opens first, with the compact map under the type breakdown.
  const drawn = (selector, least) =>
    `import(${MAP_MODULE}).then(({ inspectTreemap }) => (inspectTreemap(document.querySelector(${JSON.stringify(selector)}))?.cells.length ?? 0) > ${least})`;
  await chrome.waitFor(`${MAP_MODULE} !== undefined`, 30000);
  await chrome.waitFor(drawn(COMPACT, 50), 30000);
  await chrome.evaluate(`new Promise((resolve) => setTimeout(resolve, 500))`);
  /** @type {Record<string, any>} */
  const result = { compact: await chrome.evaluate(read(COMPACT)) };
  const TAB = `document.querySelector('#preview-pane > .tab-bar > .tab-btn[data-tab="treemap"]')`;
  await chrome.waitFor(`${TAB} !== null`, 30000);
  await chrome.evaluate(`${TAB}.click()`);
  // The map draws once the index has finished; the count settles when the last answer
  // has been laid out.
  await chrome.waitFor(drawn(FULL, 100), 30000);
  await chrome.evaluate(`new Promise((resolve) => setTimeout(resolve, 500))`);
  phase("loaded");
  result.wide = await chrome.evaluate(read(FULL));
  // The other theme: the map reads its probes again and paints every cell in its new
  // fill, then the theme goes back.
  const THEME = `document.documentElement.getAttribute("data-theme")`;
  const shownTheme = await chrome.evaluate(THEME);
  const setTheme = (theme) =>
    chrome.evaluate(
      `(document.documentElement.setAttribute("data-theme", ${JSON.stringify(theme)}), new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 300))))`,
    );
  await setTheme(shownTheme === "dark" ? "light" : "dark");
  result.themed = await chrome.evaluate(read(FULL));
  result.themed.theme = await chrome.evaluate(THEME);
  await setTheme(shownTheme);
  result.wide.theme = shownTheme;
  // The pointer on a small unlabelled file: the map hovers it and the tooltip names it.
  const target = await chrome.evaluate(point(FULL));
  await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: target.x, y: target.y });
  const hovered = `import(${MAP_MODULE}).then(({ inspectTreemap }) => inspectTreemap(document.querySelector(${JSON.stringify(FULL)})).hovered === ${target.index})`;
  const named = `document.querySelector(".custom-tooltip")?.textContent.includes(${JSON.stringify(target.path)}) === true`;
  result.pointer = {
    hovered: await chrome.waitFor(hovered, 10000).then(
      () => true,
      () => false,
    ),
    tooltip: await chrome.waitFor(named, 10000).then(
      () => true,
      () => false,
    ),
  };
  // A click opens it: the view navigates to the file.
  for (const type of ["mousePressed", "mouseReleased"]) {
    await chrome.send("Input.dispatchMouseEvent", {
      type,
      x: target.x,
      y: target.y,
      button: "left",
      clickCount: 1,
    });
  }
  const leaf = target.path.split("/").pop();
  result.pointer.opened = await chrome
    .waitFor(
      `decodeURIComponent(location.pathname).endsWith(${JSON.stringify(`/${target.path}`)})`,
      10000,
    )
    .then(
      () => true,
      () => false,
    );
  result.pointer.leaf = leaf;
  await chrome.send("Page.navigate", { url: `${base}/view/` });
  await chrome.waitFor(`${TAB} !== null`, 30000);
  await chrome.evaluate(`${TAB}.click()`);
  await chrome.waitFor(drawn(FULL, 100), 30000);
  // The keyboard: the focus proxy takes focus, and ArrowRight moves it to the next cell.
  result.keyboard = await chrome.evaluate(`(async () => {
    const { inspectTreemap } = await import(${MAP_MODULE});
    const viewport = document.querySelector(${JSON.stringify(FULL)});
    const proxy = viewport.querySelector(".tm-focus");
    proxy.focus();
    const before = inspectTreemap(viewport).focused;
    proxy.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    const after = inspectTreemap(viewport).focused;
    const order = inspectTreemap(viewport).focusOrder;
    return {
      focused: document.activeElement === proxy,
      moved: order.indexOf(after) === order.indexOf(before) + 1,
      named: (proxy.getAttribute("aria-label") || "").length > 0,
    };
  })()`);
  // A narrower window: the same tree in less room, so more of it is drawn small.
  await chrome.send("Emulation.setDeviceMetricsOverride", {
    width: 760,
    height: 600,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await chrome.evaluate(`new Promise((resolve) => setTimeout(resolve, 800))`);
  result.narrow = await chrome.evaluate(read(FULL));
  phase("measured");
  process.stdout.write(`${JSON.stringify(result)}\n`);
} finally {
  await chrome?.close();
  await server.stop();
  phase("closed");
}
