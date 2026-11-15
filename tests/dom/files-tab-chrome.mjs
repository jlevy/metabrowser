// The Files tab's filter menus, laid out by a real engine: a served folder with many file
// types, the shell's own page, and headless Chrome.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/files-tab-chrome.mjs METAB ROOT PORT STATE_DIR
//
// tests/test_files_tab_chrome.py writes the folder, owns the profile and STATE_DIR, runs
// this in a process group of its own, which Chrome and the server join, and judges what it
// prints: one JSON line of measurements.
//
// What it measures is layout, which no browserless DOM computes: where a menu's group
// heading starts against its rows, and how tall an open menu is drawn against its rows and
// the window (docs/design-system.md, "Groups in a Menu" and "Menu Height"). The pure rule,
// `menuMaxHeight`, is checked without a browser in tests/dom/filter-controls-behavior.js.
import { spawn } from "node:child_process";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state] = process.argv.slice(2);
const base = `http://127.0.0.1:${port}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);

// The two windows: one with room for a full menu under the filter row, and one short enough
// that the room, not the row cap, sets the type menu's height. Chrome's viewport, which is
// what the page sees, is set directly so the numbers do not depend on window chrome.
const TALL = { width: 1280, height: 900 };
const SHORT = { width: 1280, height: 420 };

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
      await Promise.race([exited, sleep(20000)]);
      if (server.exitCode === null) {
        server.kill("SIGKILL");
        await exited;
      }
    },
  };
}

// In the page: an open menu's box, its rows, and where its headings' text starts.
const MEASURE = `(key) => {
  const wrap = document.querySelector('.chip-menu[data-chip-menu="' + key + '"]');
  const panel = wrap && wrap.querySelector(".chip-menu-panel");
  if (!panel || wrap.getAttribute("aria-expanded") !== "true") return null;
  const round = (value) => Math.round(value * 100) / 100;
  const box = panel.getBoundingClientRect();
  const style = getComputedStyle(panel);
  const textLeft = (element) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (node.textContent.trim()) {
        const range = document.createRange();
        range.selectNodeContents(node);
        return range.getBoundingClientRect().left;
      }
    }
    return null;
  };
  const rows = [...panel.querySelectorAll(".menu-item")];
  const first = rows[0];
  const firstBox = first.getBoundingClientRect();
  const rowInset = firstBox.left + parseFloat(getComputedStyle(first).paddingLeft);
  const headings = [...panel.querySelectorAll(".group-heading")].map((heading) => {
    const group = heading.parentElement;
    return {
      text: heading.textContent,
      fromRowInset: round(textLeft(heading) - rowInset),
      namesItsGroup:
        group.classList.contains("menu-group") &&
        group.getAttribute("role") === "group" &&
        group.getAttribute("aria-labelledby") === heading.id &&
        group.firstElementChild === heading &&
        group.querySelectorAll(".menu-item").length > 0,
      // The group's divider: its own top border, a rule the menu's separator draws.
      divider: round(parseFloat(getComputedStyle(group).borderTopWidth)),
    };
  });
  return {
    windowHeight: window.innerHeight,
    top: round(box.top),
    bottom: round(box.bottom),
    height: round(box.height),
    scrollHeight: panel.scrollHeight,
    clientHeight: panel.clientHeight,
    frame: round(
      parseFloat(style.paddingTop) + parseFloat(style.paddingBottom) +
        parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth),
    ),
    rowHeights: [...new Set(rows.map((row) => round(row.getBoundingClientRect().height)))],
    rows: rows.length,
    labelFromRowInset: round(textLeft(first.querySelector(".menu-item-label")) - rowInset),
    // The rule between the groups and the raw rows, whose 1px a scrolling menu keeps.
    separators: [...panel.querySelectorAll(":scope > .menu-separator")].map((rule) =>
      round(rule.getBoundingClientRect().height),
    ),
    headings,
  };
}`;

// The gear menu: where its title, its labelled row, and its foot start, against the menu.
const GEAR = `(() => {
  const menu = document.querySelector("#settings-control .settings-menu");
  const left = (element) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (node.textContent.trim()) {
        const range = document.createRange();
        range.selectNodeContents(node);
        return Math.round((range.getBoundingClientRect().left - menu.getBoundingClientRect().left) * 100) / 100;
      }
    }
    return null;
  };
  return {
    title: left(menu.querySelector(".menu-title")),
    labelledRow: left(menu.querySelector(".menu-row")),
    foot: left(menu.querySelector(".menu-version")),
  };
})()`;

const frames =
  "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))";

const profiles = process.env.CHROME_PROFILES;
if (!process.env.CHROME_BIN || !profiles) {
  throw new Error("CHROME_BIN and CHROME_PROFILES are required");
}
const server = await serve();
phase("served");
/** @type {Awaited<ReturnType<typeof launchChrome>> | null} */
let chrome = null;
try {
  chrome = await launchChrome(process.env.CHROME_BIN, { profiles });
  phase("chrome");
  const browser = chrome;
  const viewport = (size) =>
    browser.send("Emulation.setDeviceMetricsOverride", {
      ...size,
      deviceScaleFactor: 1,
      mobile: false,
    });
  /** Click a menu's trigger and wait until it reports the state asked for. */
  const toggle = async (key, open) => {
    await browser.evaluate(
      `document.querySelector('[data-chip-menu-toggle="${key}"]').click(), true`,
    );
    await browser.waitFor(
      `document.querySelector('.chip-menu[data-chip-menu="${key}"]')?.getAttribute("aria-expanded") === "${open}"`,
    );
    await browser.evaluate(frames);
  };
  const measure = (key) => browser.evaluate(`(${MEASURE})(${JSON.stringify(key)})`);

  await viewport(TALL);
  await browser.send("Page.enable");
  await browser.send("Page.navigate", { url: `${base}/view/` });
  // The type menu lists the folder's extensions once the tree's tally arrives.
  await browser.waitFor(
    `document.querySelectorAll('.chip-menu[data-chip-menu="types"] .chip-menu-item').length > 30`,
    30000,
  );
  await browser.evaluate("document.fonts.ready.then(() => true)");
  phase("loaded");
  // The gear menu's lines start on one inset.
  await browser.evaluate(`document.getElementById("settings-btn").click(), true`);
  await browser.waitFor(
    `document.getElementById("settings-control").getAttribute("aria-expanded") === "true"`,
  );
  await browser.evaluate(frames);
  const gear = await browser.evaluate(GEAR);
  await browser.evaluate(`document.getElementById("settings-btn").click(), true`);
  await browser.waitFor(
    `document.getElementById("settings-control").getAttribute("aria-expanded") === "false"`,
  );

  const result = { gear };
  await toggle("types", true);
  result.typesTall = await measure("types");
  // The window shrinks under the open menu: it is fitted again to the room left.
  await viewport(SHORT);
  await browser.waitFor(`window.innerHeight === ${SHORT.height}`);
  await browser.evaluate(frames);
  result.typesShortResized = await measure("types");
  // Closed and opened again in the short window, it is fitted when it opens.
  await toggle("types", false);
  await toggle("types", true);
  result.typesShortOpened = await measure("types");
  // The window grows back: the row cap applies again.
  await viewport(TALL);
  await browser.waitFor(`window.innerHeight === ${TALL.height}`);
  await browser.evaluate(frames);
  result.typesTallAgain = await measure("types");
  await toggle("types", false);
  // The age menu has few rows, so neither cap reaches it at either height.
  await toggle("recency", true);
  result.ageTall = await measure("recency");
  await viewport(SHORT);
  await browser.waitFor(`window.innerHeight === ${SHORT.height}`);
  await browser.evaluate(frames);
  result.ageShort = await measure("recency");
  await toggle("recency", false);
  phase("measured");
  process.stdout.write(`${JSON.stringify(result)}\n`);
} finally {
  await chrome?.close();
  await server.stop();
  phase("closed");
}
