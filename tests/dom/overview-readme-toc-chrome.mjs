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
// - both bands: the README's prose has the file's left edge and width;
// - wide: the rail is where the file's is, and sticks at the file's offset once scrolled;
// - an entry clicked on the Overview scrolls the Overview to its heading and puts the
//   fragment on the folder's address.
//
// Each step writes `phase <name> <ms since start>` to stderr. It prints
// `overview README TOC in Chrome: <n> checks passed`, or the failures and exits 1.
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
// KPress's toggle threshold (toc.js), which builtin_plugins/markdown/toc-toggle.js follows.
const THRESHOLD = 100;

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
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

// In the page: the pane, the document's host, and its table of contents, in pane
// coordinates, after two frames so a scroll's update has run.
const STATE = `(async () => {
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const pane = document.getElementById("preview-pane");
  const top = pane.getBoundingClientRect().top;
  const host = document.querySelector(".metabrowser-kpress-host");
  const prose = host.querySelector(".kpress-prose").getBoundingClientRect();
  const toc = host.querySelector(".kpress-toc");
  const toggle = host.querySelector(".kpress-toc-toggle");
  const rail = toc.getBoundingClientRect();
  return {
    path: location.pathname,
    hash: location.hash,
    scrollTop: pane.scrollTop,
    documentTop: Math.round(host.getBoundingClientRect().top - top + pane.scrollTop),
    overview: document.querySelector(".folder-overview-stack") !== null,
    prose: [Math.round(prose.left), Math.round(prose.width)],
    rail: { position: getComputedStyle(toc).position, left: Math.round(rail.left), top: Math.round(rail.top - top) },
    toggle: toggle.classList.contains("show-toggle"),
    toggleDisplay: getComputedStyle(toggle).display,
  };
})()`;

/** Open *address* in *page* and wait for its table of contents to run. */
async function open(page, address) {
  await page.send("Page.navigate", { url: `${base}${address}` });
  await page.waitFor(
    `document.querySelector(".metabrowser-kpress-host .kpress-toc ol a") !== null &&
     (document.querySelector("[data-kpress-toc-bound]") !== null ||
      document.querySelector(".kpress-toc a.toc-link") !== null)`,
    20000,
  );
  await page.evaluate("document.fonts.ready.then(() => true)");
  return page.evaluate(STATE);
}

/** Scroll the pane to *scrollTop* and read the state once the toggle's fade has ended. */
async function scrollTo(page, scrollTop) {
  await page.evaluate(`document.getElementById("preview-pane").scrollTop = ${scrollTop}`);
  const read = await page.evaluate(STATE);
  if (read.toggleDisplay !== "none") {
    // The fade (KPress's --kpress-transition-fade) has ended when the computed opacity
    // is the end the class names.
    await page.waitFor(
      `getComputedStyle(document.querySelector(".metabrowser-kpress-host .kpress-toc-toggle")).opacity === "${read.toggle ? "1" : "0"}"`,
      5000,
    );
  }
  return read;
}

async function checkProfile(label, anchorPrefix) {
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
    const readmeTop = overview.documentTop;
    check(
      `${label} narrow: the README starts below the threshold's reach`,
      overview.overview && readmeTop > THRESHOLD + 70,
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
      ["past the threshold, above the README", THRESHOLD + 50, false],
      ["just above the README", readmeTop - 20, false],
      ["at the README's beginning", readmeTop + 5, true],
      ["reading the README", readmeTop + 600, true],
      ["back above the README", THRESHOLD + 50, false],
    ];
    for (const [where, scrollTop, shown] of steps) {
      const read = await scrollTo(page, scrollTop);
      check(
        `${label} narrow: the Overview's toggle ${shown ? "shows" : "is hidden"} ${where}`,
        read.toggle === shown,
        read,
      );
    }
  } finally {
    await page.close();
  }
  phase(`${label} narrow`);

  // The wide band: the rail beside the card, and an entry's click.
  page = await launchChrome(process.env.CHROME_BIN, {
    profiles: process.env.CHROME_PROFILES,
    width: WIDE,
  });
  try {
    await page.send("Page.enable");
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
    const reading = await scrollTo(page, overview.documentTop + 600);
    check(
      `${label} wide: the rail sticks where the file's does`,
      reading.rail.top === file.rail.top,
      [reading.rail, file.rail],
    );

    // An entry, clicked through Chrome's input, scrolls the Overview to its heading: a middle
    // one, whose heading the pane can scroll to its top.
    const target = await page.evaluate(`(() => {
      const entries = [...document.querySelectorAll(".metabrowser-kpress-host .kpress-toc ol a")];
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
      `Math.abs(document.getElementById(${JSON.stringify(id)}).getBoundingClientRect().top - document.getElementById("preview-pane").getBoundingClientRect().top) <= 2`,
      5000,
    );
    const clicked = await page.evaluate(STATE);
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
process.stdout.write(`overview README TOC in Chrome: ${checks} checks passed\n`);
