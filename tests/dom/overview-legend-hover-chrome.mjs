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
// A legend entry is a handle on its family's marks in every bar on screen, and a segment
// on itself (docs/design-system.md, "Aggregate Distributions"). Which marks a handle
// names, the tooltip it shows, and when the hover is put away run browserlessly in
// tests/dom/file-overview-session.js. What only a browser can say is that Chrome's
// pointer reaches them and what they then compute to and where they sit: the marks' lift
// and growth, the entry's lifted dot and its name's ink and that ink's contrast, the
// shimmer's animations, the tooltip's place, the clearance between grown bars and what is
// next to them, that no layout box moves, and that reduced motion keeps the highlight and
// drops the motion.
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

// What the hover draws once it has settled. Waits out the shell's tooltip appear delay and
// fade (TOOLTIP_APPEAR_DELAY and TOOLTIP_FADE_OUT in static/app.js, read from the page) and
// every finite transition in the section rather than guessing at them; the shimmer is
// infinite and is read as it runs. Reads:
// - every element marked as hovered, named by its tally row, its Details row, or its
//   legend entry, with each bar mark's computed lift and growth;
// - the legend entry's dot's lift and its name's ink, the ink's contrast on the ground
//   behind it, and every other entry and bar as it is at rest;
// - the shimmers running, on what, whether they share one start, and what they animate;
// - the layout box of every row, track, bar, legend entry, and the Details toggle, the
//   bars' by their offsets, which a transform does not move;
// - how far each grown bar is from the tracks above and below it, grown or not, and
//   Total's from the legend;
// - the tooltip's words and its place against the handle the pointer is on.
// Each Details group's heading: its category's icon, the glyph size and in the heading's
// ink, with its name the gap after it, against its first family row's icon and name
// (docs/design-system.md, "File-Type Category Icons").
const DETAILS_HEADINGS = `(() => {
  const round = (value) => Math.round(value * 100) / 100;
  const root = getComputedStyle(document.documentElement);
  const headings = [...document.querySelectorAll(".file-type-summary-group-row th")].map((heading) => {
    const icon = heading.querySelector(":scope > .category-icon");
    const name = heading.lastElementChild;
    const row = heading.closest("tbody").querySelector("tr[data-type-key] .file-type-summary-type-content");
    const rowGlyph = row.firstElementChild.querySelector("svg").getBoundingClientRect();
    // The row's name: its first drawn words, in its label or, for a family that opens,
    // its disclosure.
    const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
    let rowName = null;
    for (let node = walker.nextNode(); node && !rowName; node = walker.nextNode()) {
      const range = document.createRange();
      range.selectNodeContents(node);
      const rect = range.getBoundingClientRect();
      if (node.textContent.trim() && rect.width > 0) rowName = rect;
    }
    const box = icon?.getBoundingClientRect();
    const ink = getComputedStyle(heading).color;
    return {
      name: name.textContent,
      icon: icon && {
        width: round(box.width),
        height: round(box.height),
        inHeadingInk: getComputedStyle(icon).color === ink && getComputedStyle(icon).stroke === ink,
        textFromIcon: round(name.getBoundingClientRect().left - box.right),
        fromRowGlyph: round(box.left - rowGlyph.left),
        nameFromRowName: round(name.getBoundingClientRect().left - rowName.left),
      },
    };
  });
  return {
    headings,
    glyph: parseFloat(root.getPropertyValue("--icon-glyph")),
    gap: parseFloat(root.getPropertyValue("--category-icon-gap")),
  };
})()`;

// The module the view loaded, whose inspectTreemap reads the map it mounted.
const MAP_MODULE = `performance.getEntriesByType("resource").map((e) => e.name).find((n) => n.endsWith("/treemap-map.js"))`;

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
  await Promise.all(
    document
      .getAnimations()
      .filter((animation) => animation.effect?.getComputedTiming().iterations !== Infinity)
      .map((animation) => animation.finished.catch(() => null)),
  );
  const round = (value) => Math.round(value * 100) / 100;
  const nameOf = (element) => {
    if (element.dataset.legendKey !== undefined) return "legend " + element.dataset.legendKey;
    const row = element.closest("tr");
    if (element.closest(".folder-totals")) return row.querySelector("th").textContent + " " + element.dataset.segmentKey;
    return "Details " + row.dataset.typeKey;
  };
  // The compact treemap under the breakdown joins the section's hover; its cells are read
  // apart from the bars and the legend, as the map's own marks.
  // The map paints its cells on a canvas, so its own reading, inspectTreemap
  // (treemap-map.js), names them, and the canvases' pixels say what is drawn.
  const marked = [...document.querySelectorAll("[data-hovered]")].filter((element) => !element.classList.contains("tm-hover-anchor"));
  const mapViewport = document.querySelector(".tm-viewport-compact");
  const { inspectTreemap } = await import(${MAP_MODULE});
  const map = mapViewport ? inspectTreemap(mapViewport) : null;
  const mapCells = map?.cells ?? [];
  const mapMarked = map?.marked ?? [];
  // A cell's family is the first element of its paint style's key (treemap-map.js, cellStyleKey).
  const familyOf = new Map((map?.paint ?? []).filter((r) => r.tone === "fill").map((r) => [r.cell, JSON.parse(r.style)[0]]));
  // Each painted cell's own pixel on the marks canvas: a leaf's fill centre, a nesting
  // folder's frame's left column where one is drawn. A marked cell's is a copy of the
  // paint canvas's; any other cell's is clear.
  const lift = (() => {
    if (!map) return { lifted: true, clear: true, sampled: 0 };
    const pixels = (selector) => {
      const c = mapViewport.querySelector(selector);
      return c.getContext("2d").getImageData(0, 0, c.width, c.height);
    };
    const paint = pixels(".tm-paint");
    // The marks canvas shown, or, with none shown, what shows: nothing lifted. The two
    // canvases cross-fade (styles.css, .tm-marks), and one not shown is fading out.
    const marks = mapViewport.querySelector(".tm-marks.tm-marks-shown")
      ? pixels(".tm-marks.tm-marks-shown")
      : new ImageData(paint.width, paint.height);
    const at = (image, x, y) => [...image.data.slice((y * image.width + x) * 4, (y * image.width + x) * 4 + 4)];
    const markedSet = new Set(mapMarked);
    const out = { lifted: true, clear: true, sampled: 0 };
    for (const rect of map.paint.filter((r) => r.tone === "fill")) {
      let own = [rect.x + (rect.w >> 1), rect.y + (rect.h >> 1)];
      if (mapCells[rect.cell].nested) {
        const inner = map.paint.find((r) => r.cell === rect.cell && r.tone === "edge");
        if (!inner || inner.x <= rect.x) continue;
        own = [rect.x, rect.y + (rect.h >> 1)];
      }
      out.sampled += 1;
      const on = at(marks, ...own);
      if (markedSet.has(rect.cell)) {
        out.lifted &&= on[3] > 0 && JSON.stringify(on) === JSON.stringify(at(paint, ...own));
      } else {
        out.clear &&= on[3] === 0;
      }
    }
    return out;
  })();
  const bars = marked.filter((element) => element.classList.contains("file-type-summary-fill"));
  const style = (element) => {
    const computed = getComputedStyle(element);
    const matrix = new DOMMatrixReadOnly(computed.transform === "none" ? undefined : computed.transform);
    return { scaleY: round(matrix.d), scaleX: round(matrix.a), filter: computed.filter };
  };
  const fills = [...document.querySelectorAll(".file-type-summary-fill")].filter((element) => element.offsetParent);
  const entries = [...document.querySelectorAll(".file-type-summary-legend-item")];
  // Colours through a canvas, which takes any colour the cascade computes, oklab included.
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
  // The first painted background behind an element.
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
  const markedEntries = marked.filter((element) => element.dataset.legendKey !== undefined);
  const entryReading = markedEntries.map((item) => {
    const label = item.querySelector(".file-type-summary-legend-label");
    const ink = rgb(getComputedStyle(label).color);
    return {
      dotFilter: getComputedStyle(item.querySelector(".file-type-summary-legend-swatch")).filter,
      ink,
      inkContrast: ratio(ink, ground(item)),
    };
  });
  const restingEntries = entries
    .filter((item) => !marked.includes(item))
    .every(
      (item) =>
        getComputedStyle(item.querySelector(".file-type-summary-legend-swatch")).filter === "none" &&
        getComputedStyle(item.querySelector(".file-type-summary-legend-label")).color ===
          getComputedStyle(item).color,
    );
  const shimmers = document
    .getAnimations()
    .filter((animation) => animation.animationName === "viz-hover-shimmer");
  const shimmerOn = (animation) => {
    const target = animation.effect.target;
    return nameOf(target.closest(".file-type-summary-legend-item") ?? target) + animation.effect.pseudoElement;
  };
  const box = (element) => {
    const r = element.getBoundingClientRect();
    return [r.left, r.top, r.width, r.height].map(round).join(",");
  };
  const layout = [
    ...[...document.querySelectorAll(".folder-totals tr, .file-type-summary-details tr, .file-type-summary-track, .file-type-summary-details-toggle")].filter((e) => e.offsetParent).map(box),
    ...entries.flatMap((item) => [item, ...item.children]).map(box),
    ...fills.map((fill) => [fill.offsetLeft, fill.offsetTop, fill.offsetWidth, fill.offsetHeight].join(",")),
  ];
  const tracks = [...document.querySelectorAll(".file-type-summary-track")].filter((e) => e.offsetParent);
  const legendBox = document.querySelector(".file-type-summary-legend").getBoundingClientRect();
  const clearance = bars.map((bar) => {
    const own = bar.closest(".file-type-summary-track");
    const index = tracks.indexOf(own);
    const barBox = bar.getBoundingClientRect();
    const sameTable = (track) => track.closest("table") === own.closest("table");
    const gaps = [tracks[index - 1], tracks[index + 1]].filter((t) => t && sameTable(t)).map((t) => {
      const other = (t.querySelector("[data-hovered]") ?? t).getBoundingClientRect();
      return round(other.top >= barBox.bottom ? other.top - barBox.bottom : barBox.top - other.bottom);
    });
    if (own.closest(".file-type-summary-total-row")) gaps.push(round(legendBox.top - barBox.bottom));
    return Math.min(...gaps);
  });
  const tipBox = shown() ? tip.getBoundingClientRect() : null;
  const hoveredEntry = document.querySelector(".file-type-summary-legend-item:hover");
  const pointedSegment = bars.find((bar) => bar.matches(":hover"));
  const handle = hoveredEntry ?? pointedSegment;
  const marksLayer =
    mapViewport?.querySelector(".tm-marks.tm-marks-shown") ?? mapViewport?.querySelector(".tm-marks");
  return {
    marked: marked.map(nameOf),
    map: {
      cells: mapCells.length,
      sampled: lift.sampled,
      marked: mapMarked.map((i) => mapCells[i].path + " (family)"),
      // Every cell of the first marked cell's family.
      family: mapMarked.length
        ? mapCells.flatMap((cell, i) => (familyOf.get(i) === familyOf.get(mapMarked[0]) ? [cell.path + " (family)"] : []))
        : [],
      // The marked cells' pixels copied to the marks canvas, which lifts and does not grow.
      liftedNotGrown:
        lift.lifted &&
        (() => {
          const { scaleY, scaleX, filter } = style(marksLayer);
          return scaleY === 1 && scaleX === 1 && filter !== "none";
        })(),
      othersAtRest: lift.clear,
      inside: mapCells.every(
        (cell) => cell.x >= -0.05 && cell.y >= -0.05 && cell.x + cell.w <= mapViewport.clientWidth + 0.05 && cell.y + cell.h <= mapViewport.clientHeight + 0.05,
      ),
      layout: [
        ...mapCells.map((cell) => [cell.x, cell.y, cell.w, cell.h].map(round).join(",")),
        ...[...mapViewport.querySelectorAll(".tm-paint, .tm-marks, .tm-label-cell")].map(box),
      ],
    },
    barStyle: bars.map(style),
    // Every other bar, and every bar outside the tally rows and an open Details, at rest.
    othersAtRest: fills
      .filter((element) => !marked.includes(element))
      .every((element) => {
        const { scaleY, scaleX, filter } = style(element);
        return scaleY === 1 && scaleX === 1 && filter === "none";
      }),
    entries: entryReading,
    otherEntriesAtRest: restingEntries,
    shimmer: {
      on: shimmers.map(shimmerOn),
      running: shimmers.every((animation) => animation.playState === "running"),
      oneStart: new Set(shimmers.map((animation) => animation.startTime)).size <= 1,
      animates: [...new Set(shimmers.flatMap((animation) => animation.effect.getKeyframes().flatMap((frame) => Object.keys(frame).filter((key) => !["offset", "easing", "composite", "computedOffset"].includes(key)))))],
    },
    layout,
    entrySize: entries.map((item) => { const r = item.getBoundingClientRect(); return round(r.width) + "x" + round(r.height); }),
    clearance,
    tooltip: shown() ? tip.innerText.replace(/\\s+/g, " ").trim() : null,
    // The glyph before the family's name, drawn at the icon size, or null for none.
    tooltipIcon: (() => {
      const svg = shown() ? tip.querySelector(".tm-tip-icon svg") : null;
      if (!svg) return null;
      const r = svg.getBoundingClientRect();
      return { w: round(r.width), h: round(r.height) };
    })(),
    // Where the tooltip sits: its centre against the centre of what the pointer is on, and
    // whether it is above or below that rather than over it.
    tooltipOnAnchor:
      tipBox && handle
        ? (() => {
            const anchorBox = handle.getBoundingClientRect();
            return {
              anchor: hoveredEntry ? "legend" : "segment",
              centerOffset: round(tipBox.left + tipBox.width / 2 - (anchorBox.left + anchorBox.width / 2)),
              clear: tipBox.top >= anchorBox.bottom || tipBox.bottom <= anchorBox.top,
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
  // The light page, whatever the machine's own appearance, until a step asks for the dark.
  const LIGHT = { name: "prefers-color-scheme", value: "light" };
  await chrome.send("Emulation.setEmulatedMedia", { features: [LIGHT] });
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `${base}/view/` });
  await chrome.waitFor(
    `document.querySelectorAll(".file-type-summary-legend-item").length > 0 && document.querySelectorAll(".folder-totals .file-type-summary-ignored-row [data-segment-key]").length > 0 && document.querySelectorAll(".tm-viewport-compact .tm-paint").length > 0 && ${MAP_MODULE} !== undefined`,
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
  // Details, toggled by its own control without the pointer, as a key toggles it while
  // the pointer rests on a legend entry.
  const toggleDetails = () =>
    chrome.evaluate(`document.querySelector(".file-type-summary-details-toggle").click()`);
  const result = {};
  result.theme = await chrome.evaluate(
    `getComputedStyle(document.documentElement).getPropertyValue("--viz-data-mark-hover-filter").trim()`,
  );
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
  await toggleDetails();
  result.detailsAtRest = await chrome.evaluate(READ);
  result.detailsHeadings = await chrome.evaluate(DETAILS_HEADINGS);
  await move(ENTRY("Python", "label"));
  result.detailsEntry = await chrome.evaluate(READ);
  await toggleDetails();
  result.detailsClosedUnderEntry = await chrome.evaluate(READ);
  // And opened again under the entry the pointer still holds: the row is marked after the
  // bars and the dot, so its shimmer starts its own cycle.
  await toggleDetails();
  result.detailsOpenedUnderEntry = await chrome.evaluate(READ);
  await toggleDetails();
  await away();
  await chrome.evaluate(`document.documentElement.dataset.theme = "dark"`);
  await move(ENTRY("Python", "label"));
  result.darkEntry = await chrome.evaluate(READ);
  await away();
  await chrome.evaluate(`document.documentElement.dataset.theme = "light"`);
  await chrome.send("Emulation.setEmulatedMedia", {
    features: [LIGHT, { name: "prefers-reduced-motion", value: "reduce" }],
  });
  await move(ENTRY("Python", "label"));
  result.reducedMotion = await chrome.evaluate(READ);
  result.reducedMotionTransitions = await chrome.evaluate(
    `[...new Set([...document.querySelectorAll(".file-type-summary-fill, .file-type-summary-legend-swatch, .file-type-summary-legend-label")].map((e) => getComputedStyle(e).transitionDuration))]`,
  );
  await away();
  await chrome.send("Emulation.setEmulatedMedia", { features: [LIGHT] });
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
