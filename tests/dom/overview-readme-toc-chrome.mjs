// A folder Overview's README keeps the table of contents it has opened as a file, in
// headless Chrome against a live `metab` (docs/design-system.md, "Embedded Document
// Navigation").
//
// Usage: node overview-readme-toc-chrome.mjs METAB ROOT PORT STATE_DIR, with CHROME_BIN set,
// and CHROME_PROFILES naming where Chrome's profile goes (tests/dom/chrome-session.mjs).
// tests/test_overview_readme_toc_chrome.py writes ROOT, a folder whose README is long enough
// for KPress's table of contents, owns the profile directory, and runs this in a process
// group of its own, which Chrome and the servers join, stopped however the session ends.
//
// The folder is served twice, trusted, where KPress's toc.js runs the table of contents, and
// `--untrusted`, where the page runs its own (inert-toc.js). Under each, at a window whose pane
// is in KPress's narrow band and at one in its wide band, it opens the README as a file and
// the folder's Overview, and checks:
//
// - narrow: in the file, the toggle is hidden at the top and fades in past KPress's
//   threshold; on the Overview it stays hidden past the threshold while the reader is above
//   the README, fades in once the README's beginning reaches the pane's top, and fades out
//   back above it;
// - narrow: scrolled to a section, its entry is the active one; collapsing the README while
//   reading it hides the toggle;
// - narrow: the README card, the section rules and File Overview's body end at one edge at
//   the window's width and at two narrower ones, one with the pane just above KPress's
//   48 rem boundary, where KPress's trailing toggle gutter takes the card in from the
//   column, and one below it;
// - narrow: arriving from the README's file page by in-app navigation, which keeps the file
//   in the pane while the Overview is laid out in the shell's stage, an entry follows the
//   reader;
// - both bands: the README's prose has the file's left edge and width;
// - wide: a deep link to a README heading lands it at the pane's top on the Overview;
// - wide: the rail is where the file's is, and sticks at the file's offset once scrolled;
// - wide: an entry clicked on the Overview scrolls the Overview to its heading and puts the
//   fragment on the folder's address.
//
// Every read is of the committed pane, after File Overview's rollup has landed: the shell
// lays a page out in a hidden, inert stage while the page before stays shown, and File
// Overview grows when its rollup lands (tests/dom/folder-overview-alignment-chrome.mjs).
// Each scroll is computed from where the README starts at that moment.
//
// A check named in EXPECTED_FAILURES is a known defect with a bead: it is reported when it
// fails the way the defect does, and the session fails if it passes or fails another way,
// so the fix removes it from the list and a different fault is not taken for it.
//
// Each step writes `phase <name> <ms since start>` to stderr. It prints
// `overview README TOC in Chrome: <n> checks passed`, then `expected to fail (<bead>):
// <check>` for each expected failure, or the failures and exits 1.
import { spawn } from "node:child_process";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state] = process.argv.slice(2);
if (!metab || !root || !port || !state || !process.env.CHROME_BIN) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES overview-readme-toc-chrome.mjs METAB ROOT PORT STATE",
  );
}
const base = `http://127.0.0.1:${port}`;
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// The window widths that put the preview pane in KPress's narrow band (below 75rem) and in
// its wide band, beside the default navigation pane.
const NARROW = 1280;
const WIDE = 1920;
// Narrower windows, each checked for the shared edge in the band the pane is in: 1100 puts
// the pane just above KPress's 48 rem boundary, 49.3 rem beside the navigation pane, where
// the card stopped 32 px short of the section rules; 900 puts it below the boundary.
const EDGE_WIDTHS = [
  [1100, "regular"],
  [900, "phone"],
];
// KPress's toggle threshold (toc.js), which builtin_plugins/markdown/toc-toggle.js follows.
const THRESHOLD = 100;
// Positions are fractional; a difference under half a pixel is not a different edge.
const TOLERANCE_PX = 0.5;
// How long a scroll-spy is given to mark the section the reader scrolled to. It marks it in
// an IntersectionObserver callback or a frame later; 2 s is many times that under load.
const ACTIVE_WAIT_MS = 2000;
// The section the scroll-spy steps scroll to: a middle one, which the pane can bring to its
// top.
const SECTION = "Section 5";

// Each listed check's bead, and the symptom its failure must show.
const EXPECTED_FAILURES = new Map([
  // KPress's toc.js finds each entry's heading with document.getElementById while the
  // Overview is staged and the file, with the same heading ids, is still in the pane, and
  // watches the file's headings: the section's heading reaches the pane's top, and the
  // highlight stays where it was at arrival, on the first entry or on none.
  [
    "trusted narrow: arriving in-app from the README's file, an entry follows the reader",
    {
      bead: "mb-hpoq",
      symptom: (state) =>
        Math.abs(state.sectionOffset) <= 2 &&
        (state.active === null || state.active === state.first),
    },
  ],
]);

const failures = [];
const expected = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  const known = EXPECTED_FAILURES.get(label);
  if (known) {
    const { bead, symptom } = known;
    if (ok) {
      failures.push(`${label}: passes, and is listed as expected to fail (${bead})`);
    } else if (!symptom(detail)) {
      failures.push(`${label}: fails, but not as ${bead} does: ${JSON.stringify(detail)}`);
    } else {
      expected.push(`expected to fail (${bead}): ${label}`);
      process.stderr.write(`expected failure (${bead}) ${label}: ${JSON.stringify(detail)}\n`);
    }
    return;
  }
  if (!ok) {
    const failure = `${label}${detail ? `: ${JSON.stringify(detail)}` : ""}`;
    failures.push(failure);
    process.stderr.write(`failed ${failure}\n`);
  }
};

/** Start a server with *flags*, and resolve to its stop once it says where it serves. */
async function serve(flags) {
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
      ...flags,
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
  return async () => {
    server.kill();
    await exited;
  };
}

// The page the pane shows: no stage pending, its tab bar a child of the pane, and its active
// tab naming the view that is shown, with the document's host, which is the view on a file's
// page and the README panel's body on an Overview; or null.
const SHOWN = `(() => {
  const pane = document.getElementById("preview-pane");
  if (!pane || pane.querySelector(":scope > .preview-file-stage")) {
    return null;
  }
  const tab = pane.querySelector(":scope > .tab-bar > .tab-btn.active");
  const view = pane.querySelector(':scope > [data-active-view="true"]');
  const host = view?.matches(".metabrowser-kpress-host")
    ? view
    : view?.querySelector(".metabrowser-kpress-host");
  return tab && host && tab.dataset.tab === view.dataset.tabContent ? { pane, view, host } : null;
})()`;

// Shown, with its table of contents running, and on the Overview with File Overview's
// rollup landed.
const READY = `(() => {
  const shown = ${SHOWN};
  if (!shown || !shown.host.querySelector(".kpress-toc ol a")) {
    return false;
  }
  const bound =
    shown.host.querySelector("[data-kpress-toc-bound]") !== null ||
    shown.host.querySelector(".kpress-toc a.toc-link") !== null;
  const overview = shown.view.querySelector(".folder-overview-stack") !== null;
  return bound && (!overview || shown.view.querySelector(".file-type-summary-details-toggle") !== null);
})()`;

// In the page: the pane, the document's host, and its table of contents, in pane
// coordinates, after two frames so a scroll's update has run; null if the pane is not
// showing a page.
const STATE = `(async () => {
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const shown = ${SHOWN};
  if (!shown) {
    return null;
  }
  const { pane, view, host } = shown;
  const top = pane.getBoundingClientRect().top;
  const prose = host.querySelector(".kpress-prose").getBoundingClientRect();
  const toc = host.querySelector(".kpress-toc");
  const toggle = host.querySelector(".kpress-toc-toggle");
  const rail = toc.getBoundingClientRect();
  const active = toc.querySelector('a.active, a[data-active="true"]');
  return {
    path: location.pathname,
    hash: location.hash,
    scrollTop: pane.scrollTop,
    documentTop: Math.round(host.getBoundingClientRect().top - top + pane.scrollTop),
    overview: view.querySelector(".folder-overview-stack") !== null,
    prose: [Math.round(prose.left), Math.round(prose.width)],
    rail: { position: getComputedStyle(toc).position, left: Math.round(rail.left), top: Math.round(rail.top - top) },
    active: active ? active.textContent.trim() : null,
    first: toc.querySelector("ol a")?.textContent.trim() ?? null,
    toggle: toggle.classList.contains("show-toggle"),
    toggleDisplay: getComputedStyle(toggle).display,
    toggleOpacity: getComputedStyle(toggle).opacity,
  };
})()`;

// Where the Overview's README card, section rules, and surface bodies end, and the pane's
// band, in the shown pane.
const EDGES = `(() => {
  const shown = ${SHOWN};
  if (!shown) {
    return null;
  }
  const { pane, view } = shown;
  const rem = Number.parseFloat(getComputedStyle(document.documentElement).fontSize);
  const right = (element) => Math.round(element.getBoundingClientRect().right * 100) / 100;
  return {
    paneRem: Math.round((pane.clientWidth / rem) * 100) / 100,
    card: right(view.querySelector(".folder-overview-panel-document .kpress-long-text")),
    rules: [...view.querySelectorAll(".folder-overview-panel-heading")].map(right),
    surfaces: [
      ...view.querySelectorAll(".folder-overview-panel-surface > .folder-overview-panel-body"),
    ].map(right),
    legend: (() => {
      const legend = view.querySelector(".file-overview-body .file-type-summary-legend");
      const body = view.querySelector(".file-overview-body").getBoundingClientRect();
      const toc = view.querySelector(".kpress-toc").getBoundingClientRect();
      const items = [...legend.querySelectorAll(".file-type-summary-legend-item")].map(
        (item) => item.getBoundingClientRect(),
      );
      const box = legend.getBoundingClientRect();
      const track = legend.parentElement.getBoundingClientRect();
      const first = legend.querySelector(".file-type-summary-legend-item");
      const entry = view.querySelector(".kpress-toc .kpress-toc-level-1 > a");
      const entryText = document.createRange();
      entryText.selectNodeContents(entry);
      const leftOf = (selector) => first.querySelector(selector).getBoundingClientRect().left;
      return {
        rail: getComputedStyle(legend.parentElement).position === "absolute",
        left: box.left,
        width: box.width,
        trackLeft: track.left,
        trackWidth: track.width,
        swatchLeft: leftOf(".file-type-summary-legend-swatch"),
        labelLeft: leftOf(".file-type-summary-legend-label"),
        tocEntryLeft: entry.getBoundingClientRect().left,
        tocTextLeft: entryText.getBoundingClientRect().left,
        shareRights: [...legend.querySelectorAll(".file-type-summary-legend-percent")].map(
          (percent) => percent.getBoundingClientRect().right,
        ),
        tocEntryRight: entry.getBoundingClientRect().right,
        top: box.top,
        bodyLeft: body.left,
        bodyRight: body.right,
        bodyTop: body.top,
        tocLeft: toc.left,
        tocWidth: toc.width,
        items: items.length,
        lines: new Set(items.map((item) => Math.round(item.top))).size,
      };
    })(),
  };
})()`;

/** Poll *expression* in *page* until it is truthy or *timeoutMs* passes; whether it was. */
async function poll(page, expression, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await page.evaluate(expression)) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  return false;
}

/** Read the shown page's state, waiting for the pane to show one. */
async function read(page) {
  for (;;) {
    await page.waitFor(`!!${SHOWN}`, 20000);
    const value = await page.evaluate(STATE);
    if (value !== null) {
      return value;
    }
  }
}

/** Wait until the page is ready, its faces loaded, and read it. */
async function ready(page) {
  await page.waitFor(READY, 20000);
  await page.evaluate("document.fonts.ready.then(() => true)");
  return read(page);
}

/** Open *address* in *page* with a full load and read it once its table of contents runs. */
async function open(page, address) {
  await page.send("Page.navigate", { url: `${base}${address}` });
  return ready(page);
}

/** Read the state once the toggle's fade has ended. */
async function settled(page) {
  const value = await read(page);
  if (value.toggleDisplay !== "none" && value.toggleOpacity !== (value.toggle ? "1" : "0")) {
    // The fade (KPress's --kpress-transition-fade) has ended when the computed opacity
    // is the end the class names.
    await page.waitFor(
      `(() => {
        const toggle = ${SHOWN}?.host.querySelector(".kpress-toc-toggle");
        return !!toggle && getComputedStyle(toggle).opacity ===
          (toggle.classList.contains("show-toggle") ? "1" : "0");
      })()`,
      5000,
    );
    return read(page);
  }
  return value;
}

/** Scroll the pane to *scrollTop* and read the state once the toggle's fade has ended. */
async function scrollTo(page, scrollTop) {
  await page.evaluate(`document.getElementById("preview-pane").scrollTop = ${scrollTop}`);
  return settled(page);
}

/**
 * Scroll the shown document's heading *id* to the pane's top, and read the state once its
 * entry is the active one or ACTIVE_WAIT_MS has passed, with `sectionOffset`, where the
 * heading then is below the pane's top.
 */
async function scrollToSection(page, id) {
  const heading = `${SHOWN}.host.querySelector(${JSON.stringify(`[id="${id}"]`)})`;
  const offset = `(${heading}.getBoundingClientRect().top - ${SHOWN}.pane.getBoundingClientRect().top)`;
  await page.evaluate(`(document.getElementById("preview-pane").scrollTop += ${offset}), true`);
  await poll(
    page,
    `${SHOWN}?.host.querySelector('.kpress-toc a.active, .kpress-toc a[data-active="true"]')?.textContent.trim() === ${JSON.stringify(SECTION)}`,
    ACTIVE_WAIT_MS,
  );
  const state = await read(page);
  return { ...state, sectionOffset: Math.round(await page.evaluate(offset)) };
}

/** Check that the shown Overview's card, section rules, and surface bodies share an edge. */
async function checkEdges(page, label, band) {
  const edges = await page.evaluate(EDGES);
  const inBand = {
    phone: edges.paneRem < 48,
    regular: edges.paneRem >= 48 && edges.paneRem < 75,
    narrow: edges.paneRem < 75,
    wide: edges.paneRem >= 75,
  }[band];
  check(`${label}: the pane is in the ${band} band`, inBand, edges);
  const ends = [...edges.rules, ...edges.surfaces];
  check(
    `${label}: the README card, the section rules and File Overview's body end at one edge`,
    ends.length >= 3 && ends.every((edge) => Math.abs(edge - edges.card) < TOLERANCE_PX),
    edges,
  );
  // File Overview's legend: in the wide band, a rail where the README's table of contents
  // is, from the section's top, one entry to a line, each swatch on the line of the
  // contents' entry marks, each name on a level-1 entry's text edge, and each share ending
  // where the entries do; in every other band,
  // inside the section's body under the bars, as it was.
  const legend = edges.legend;
  if (band === "wide") {
    check(
      `${label}: File Overview's legend is a rail on the table of contents' track, aligned with its entries`,
      legend.rail &&
        Math.abs(legend.trackLeft - legend.tocLeft) < TOLERANCE_PX &&
        Math.abs(legend.trackWidth - legend.tocWidth) < TOLERANCE_PX &&
        Math.abs(legend.swatchLeft - legend.tocEntryLeft) < TOLERANCE_PX &&
        Math.abs(legend.labelLeft - legend.tocTextLeft) < TOLERANCE_PX &&
        legend.shareRights.length > 1 &&
        legend.shareRights.every(
          (right) => Math.abs(right - legend.tocEntryRight) < TOLERANCE_PX,
        ) &&
        Math.abs(legend.top - legend.bodyTop) < TOLERANCE_PX &&
        legend.items > 1 &&
        legend.lines === legend.items,
      legend,
    );
  } else {
    check(
      `${label}: File Overview's legend stays in its body, below the bars`,
      !legend.rail &&
        legend.left >= legend.bodyLeft - TOLERANCE_PX &&
        legend.left + legend.width <= legend.bodyRight + TOLERANCE_PX &&
        legend.top > legend.bodyTop &&
        legend.items > 1 &&
        legend.lines < legend.items,
      legend,
    );
  }
}

async function checkProfile(label, anchorPrefix) {
  const sectionId = `${anchorPrefix}${SECTION.toLowerCase().replace(" ", "-")}`;
  // The narrow band: the floating toggle.
  let page = await launchChrome(process.env.CHROME_BIN, {
    profiles: process.env.CHROME_PROFILES,
    width: NARROW,
  });
  try {
    await page.send("Page.enable");
    const file = await open(page, "/view/README.md");
    check(`${label} narrow: the file's toggle is hidden at the top`, !file.toggle, file);
    const fileScrolled = await scrollTo(page, THRESHOLD + 50);
    check(
      `${label} narrow: the file's toggle shows past the threshold`,
      fileScrolled.toggle,
      fileScrolled,
    );

    const overview = await open(page, "/view/");
    check(
      `${label} narrow: the README starts below the threshold's reach`,
      overview.overview && overview.documentTop > THRESHOLD + 70,
      overview,
    );
    check(
      `${label} narrow: the README's prose is the file's`,
      overview.prose.join() === file.prose.join(),
      [overview.prose, file.prose],
    );
    check(
      `${label} narrow: the Overview's toggle is hidden at the top`,
      !overview.toggle,
      overview,
    );
    const steps = [
      ["past the threshold, above the README", () => THRESHOLD + 50, false],
      ["just above the README", (top) => top - 20, false],
      ["at the README's beginning", (top) => top + 5, true],
      ["reading the README", (top) => top + 600, true],
      ["back above the README", () => THRESHOLD + 50, false],
    ];
    for (const [where, scrollTop, shown] of steps) {
      const before = await read(page);
      const after = await scrollTo(page, scrollTop(before.documentTop));
      check(
        `${label} narrow: the Overview's toggle ${shown ? "shows" : "is hidden"} ${where}`,
        after.toggle === shown,
        after,
      );
    }

    // Opened with a full load, the scroll-spy follows the reader.
    const section = await scrollToSection(page, sectionId);
    check(
      `${label} narrow: scrolled to a section, its entry is the active one`,
      section.active === SECTION,
      section,
    );

    // Collapsing the README while reading it hides its toggle.
    const reading = await scrollTo(page, (await read(page)).documentTop + 600);
    const toggleButton = `${SHOWN}.view.querySelector(".folder-overview-panel-document .folder-overview-panel-toggle")`;
    await page.evaluate(`${toggleButton}.click(), true`);
    // Collapsed once the body's height transition has run to no height, which takes the
    // pane's scroll back with it.
    await page.waitFor(
      `${SHOWN}?.view.querySelector(".folder-overview-panel-document .folder-overview-panel-body-collapsed")?.getBoundingClientRect().height === 0`,
      5000,
    );
    const collapsed = await settled(page);
    check(
      `${label} narrow: collapsing the README while reading it hides the toggle`,
      reading.toggle && !collapsed.toggle,
      [reading, collapsed],
    );
    await page.evaluate(`${toggleButton}.click(), true`);
    await page.waitFor(
      `${SHOWN}?.view.querySelector(".folder-overview-panel-document .folder-overview-panel-body-collapsed") == null`,
      5000,
    );

    // The shared edge, at this width and at the narrower ones.
    await checkEdges(page, `${label} ${NARROW}px`, "narrow");
    for (const [width, band] of EDGE_WIDTHS) {
      await page.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 900,
        deviceScaleFactor: 1,
        mobile: false,
      });
      await page.waitFor(`!!${SHOWN}`, 20000);
      await read(page);
      await checkEdges(page, `${label} ${width}px`, band);
    }
    await page.send("Emulation.clearDeviceMetricsOverride");

    // Arriving in-app: the file stays in the pane while the shell lays the Overview out in
    // its stage, and the two hold the same heading ids.
    await open(page, "/view/README.md");
    await page.evaluate(`window.metabrowser.navigation.open({ path: "" }).then(() => true)`);
    await page.waitFor(`location.pathname === "/view/"`, 20000);
    const arrived = await ready(page);
    check(
      `${label} narrow: in-app navigation shows the folder's Overview`,
      arrived.overview && arrived.path === "/view/",
      arrived,
    );
    const inApp = await scrollToSection(page, sectionId);
    check(
      `${label} narrow: arriving in-app from the README's file, an entry follows the reader`,
      inApp.active === SECTION,
      inApp,
    );
  } finally {
    await page.close();
  }
  phase(`${label} narrow`);

  // The wide band: a deep link, the rail beside the card, and an entry's click.
  page = await launchChrome(process.env.CHROME_BIN, {
    profiles: process.env.CHROME_PROFILES,
    width: WIDE,
  });
  try {
    await page.send("Page.enable");
    // A deep link to a README heading, opened with a full load, lands it at the pane's top
    // once File Overview's rollup has grown the panel above it.
    const linked = await open(page, `/view/#${sectionId}`);
    const landed = await poll(
      page,
      `(() => {
        const { pane, host } = ${SHOWN};
        const heading = host.querySelector(${JSON.stringify(`[id="${sectionId}"]`)});
        return Math.abs(heading.getBoundingClientRect().top - pane.getBoundingClientRect().top) <= 2;
      })()`,
      5000,
    );
    check(
      `${label} wide: a deep link lands its heading at the pane's top on the Overview`,
      landed && linked.overview && linked.path === "/view/" && linked.hash === `#${sectionId}`,
      await read(page),
    );

    await open(page, "/view/README.md");
    const file = await scrollTo(page, 600);
    const overview = await open(page, "/view/");
    check(
      `${label} wide: the README's prose is the file's`,
      overview.prose.join() === file.prose.join(),
      [overview.prose, file.prose],
    );
    check(
      `${label} wide: the rail is where the file's is`,
      overview.rail.left === file.rail.left && overview.rail.position === "sticky",
      [overview.rail, file.rail],
    );
    const reading = await scrollTo(page, (await read(page)).documentTop + 600);
    check(
      `${label} wide: the rail sticks where the file's does`,
      reading.rail.top === file.rail.top,
      [reading.rail, file.rail],
    );
    await checkEdges(page, `${label} ${WIDE}px`, "wide");
    // At a 20px root the legend's names still meet the contents' entries: at 16px the
    // rail's rem-based gap and a fixed 6px one are equal, so only a larger root tells them
    // apart. The pane stays in the wide band.
    await page.evaluate(`document.documentElement.style.fontSize = "20px"`);
    await checkEdges(page, `${label} ${WIDE}px at a 20px root`, "wide");
    await page.evaluate(`document.documentElement.style.fontSize = ""`);

    // An entry, clicked through Chrome's input, scrolls the Overview to its heading: a middle
    // one, whose heading the pane can scroll to its top.
    const target = await page.evaluate(`(() => {
      const entries = [...${SHOWN}.host.querySelectorAll(".kpress-toc ol a")];
      const entry = entries[Math.floor(entries.length / 2)];
      const box = entry.getBoundingClientRect();
      return { href: entry.getAttribute("href"), x: box.x + box.width / 2, y: box.y + box.height / 2 };
    })()`);
    check(
      `${label} wide: an entry links a place on the page`,
      target.href.startsWith(`#${anchorPrefix}`),
      target,
    );
    for (const type of ["mousePressed", "mouseReleased"]) {
      await page.send("Input.dispatchMouseEvent", {
        type,
        x: target.x,
        y: target.y,
        button: "left",
        clickCount: 1,
      });
    }
    await page.waitFor(`location.hash === ${JSON.stringify(target.href)}`, 5000);
    const id = decodeURIComponent(target.href.slice(1));
    await page.waitFor(
      `(() => {
        const { pane, host } = ${SHOWN};
        const heading = host.querySelector(${JSON.stringify(`[id="${id}"]`)});
        return Math.abs(heading.getBoundingClientRect().top - pane.getBoundingClientRect().top) <= 2;
      })()`,
      5000,
    );
    const clicked = await read(page);
    check(
      `${label} wide: the click stays on the folder's Overview`,
      clicked.path === "/view/" && clicked.overview,
      clicked,
    );
  } finally {
    await page.close();
  }
  phase(`${label} wide`);
}

let stop = await serve([]);
phase("trusted server");
try {
  await checkProfile("trusted", "");
} finally {
  await stop();
}
stop = await serve(["--untrusted"]);
phase("untrusted server");
try {
  await checkProfile("untrusted", "user-content-");
} finally {
  await stop();
}
phase("closed");

if (failures.length) {
  process.stdout.write(`${failures.length} of ${checks} checks failed:\n${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(
  `overview README TOC in Chrome: ${checks - expected.length} checks passed\n${expected
    .map((line) => `${line}\n`)
    .join("")}`,
);
