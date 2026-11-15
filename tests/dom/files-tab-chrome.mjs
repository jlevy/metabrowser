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
// heading starts against its rows, how tall an open menu is drawn against its rows and
// the window, which controls the bar's row and closed drawer hold, whether the row fits
// its pane, and which take keyboard numbers, where a Group by section's heading starts
// against its tree, and whether a refresh after a write keeps the scroll position and the
// focused row, and a tree row's leading slot, a folder's chevron and a file's icon, against
// the name after it (docs/design-system.md, "Groups in a Menu", "Menu Height", "Grouping
// the Files Tree", and "One Glyph Size"). The requests and sections themselves run browserlessly in
// tests/dom/files-group-by-session.js. The pure rule, `menuMaxHeight`, is checked without
// a browser in tests/dom/filter-controls-behavior.js.
import { spawn } from "node:child_process";
import fs from "node:fs";
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

// A tree row's leading slot: a folder's chevron and a file's type icon, at one depth, each
// in its box from the row's content edge, and where the name after it starts. The box is
// `--tree-icon-slot` wide (styles.css, mb-hmv7); a folder's chevron is its toggle's margin
// box, as a container row's is.
const SLOTS = `(() => {
  const round = (value) => Math.round(value * 100) / 100;
  const tree = document.querySelector('#tab-files [role="tree"]');
  const measure = (row, slot) => {
    const box = row.getBoundingClientRect();
    const style = getComputedStyle(row);
    const inset = box.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft);
    const r = slot.getBoundingClientRect();
    const s = getComputedStyle(slot);
    const glyph = slot.querySelector("svg").getBoundingClientRect();
    const left = r.left - parseFloat(s.marginLeft);
    return {
      slot: round(r.width + parseFloat(s.marginLeft) + parseFloat(s.marginRight)),
      fromInset: round(left - inset),
      glyph: round(glyph.width),
      glyphFromSlot: round(glyph.left - left),
      name: round(row.querySelector(".tree-item-name").getBoundingClientRect().left - inset),
      gap: parseFloat(style.columnGap),
    };
  };
  const folder = tree.querySelector('.tree-folder[data-path="src"]');
  const file = tree.querySelector('.tree-file[data-path="README.md"]');
  return {
    token: getComputedStyle(document.documentElement).getPropertyValue("--tree-icon-slot").trim(),
    folder: measure(folder, folder.querySelector(":scope > .tree-toggle")),
    file: measure(file, file.querySelector(":scope > .tree-item-icon")),
  };
})()`;

// The bar's row and drawer: which controls each holds.
const ROW = `(() => ({
  row: [...document.querySelector(".nav-filter-bar-main").children].map((child) =>
    child.matches(".chip-menu") ? "menu:" + child.dataset.chipMenu : child.className),
  drawer: [...document.querySelectorAll("#filter-drawer [data-chip-menu-toggle], #filter-drawer [data-chip-check]")]
    .map((control) => control.dataset.chipMenuToggle || control.dataset.chipCheck),
  drawerOpen: document.getElementById("filter-drawer").dataset.open,
  drawerInert: document.getElementById("filter-drawer").inert,
}))()`;

// Whether the row fits its pane: Group by's trigger and Show ignored at their natural
// widths, the room to spare before Clear and the chevron, and what the badge counts.
// `spare` is the space between Show ignored and the trailing span beyond the row's gap,
// less how far that span runs past the row's edge: positive when the row fits with room
// left, negative by the overflow when it does not (the span's auto margin is 0 then, so
// the space alone cannot say).
const ROW_FIT = `(() => {
  const row = document.querySelector(".nav-filter-bar-main");
  const trigger = row.querySelector('[data-chip-menu-toggle="group"]');
  const check = row.querySelector(".filter-check");
  const end = row.querySelector(".nav-filter-bar-end");
  const round = (value) => Math.round(value * 100) / 100;
  const rowBox = row.getBoundingClientRect();
  const endBox = end.getBoundingClientRect();
  const gap = parseFloat(getComputedStyle(row).columnGap);
  const overflow = Math.max(0, endBox.right - rowBox.right);
  return {
    trigger: trigger.textContent.trim(),
    pane: round(document.getElementById("nav-filter-bar").getBoundingClientRect().width),
    row: row.clientWidth,
    content: row.scrollWidth,
    spare: round(endBox.left - check.getBoundingClientRect().right - gap - overflow),
    triggerClipped: trigger.scrollWidth > trigger.clientWidth,
    checkClipped: check.scrollWidth > check.clientWidth,
    clear: Boolean(end.querySelector("[data-chip-clear]")),
    badge: end.querySelector(".chip-badge")?.textContent.trim() || null,
  };
})()`;

// Which filter menu is open, and whether the drawer is.
const OPEN_MENU = `({
  menu: document.querySelector('.chip-menu[aria-expanded="true"]')?.dataset.chipMenu ?? null,
  drawerOpen: document.getElementById("filter-drawer").dataset.open,
})`;

// Each Group by section: its heading against its rows, and how the heading names it.
const SECTIONS = `[...document.querySelectorAll(".tree-section")].map((section) => {
  const heading = section.querySelector(":scope > .tree-section-heading");
  const label = heading.querySelector(".tree-section-label");
  const range = document.createRange();
  range.selectNodeContents(label);
  const row = section.querySelector(".tree-item");
  const box = row.getBoundingClientRect();
  const style = getComputedStyle(row);
  const tree = section.querySelector(":scope > [role='tree']");
  return {
    key: section.dataset.treeGroup,
    label: label.textContent,
    count: heading.querySelector(".tree-section-count").textContent,
    headingClasses: [...heading.classList],
    fromRowInset: Math.round((range.getBoundingClientRect().left - box.left -
      parseFloat(style.borderLeftWidth) - parseFloat(style.paddingLeft)) * 100) / 100,
    namesItsTree: section.getAttribute("aria-labelledby") === heading.id &&
      tree?.getAttribute("aria-labelledby") === heading.id,
    divider: parseFloat(getComputedStyle(section).borderTopWidth),
  };
})`;

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
  /** Press one key, as the reader does, at the page. */
  /** @type {Record<string, number>} */
  const NAMED_KEYS = { Escape: 27, ArrowLeft: 37, ArrowRight: 39 };
  const press = async (key) => {
    const named = key in NAMED_KEYS;
    const code = named ? key : `Digit${key}`;
    const windowsVirtualKeyCode = named ? NAMED_KEYS[key] : key.charCodeAt(0);
    await browser.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key,
      code,
      windowsVirtualKeyCode,
      ...(named ? {} : { text: key }),
    });
    await browser.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key,
      code,
      windowsVirtualKeyCode,
    });
    await browser.evaluate(frames);
  };

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
  // Group by and Show ignored are the row; the three filters wait in the closed drawer.
  result.row = await browser.evaluate(ROW);
  // The row at its widest: a filter set, so Clear and the badge show, under each Group by
  // value. Then Show ignored off alone: Clear shows, and the badge leaves it out.
  const setFilters = async (patch) => {
    await browser.evaluate(`window.metabrowser.filterState.set(${JSON.stringify(patch)}), true`);
    await browser.evaluate(frames);
  };
  await setFilters({ size: "1m" });
  result.rowFit = {};
  for (const group of ["none", "age", "type"]) {
    await setFilters({ group });
    result.rowFit[group] = await browser.evaluate(ROW_FIT);
  }
  await setFilters({ size: "all", group: "none", showIgnored: false });
  result.ignoredOff = await browser.evaluate(ROW_FIT);
  await setFilters({ showIgnored: true });
  await browser.waitFor("document.querySelectorAll('.tree-section').length === 0", 30000);
  await browser.waitFor(
    `document.querySelectorAll('.chip-menu[data-chip-menu="types"] .chip-menu-item').length > 30`,
    30000,
  );
  await browser.evaluate(frames);
  // The numbers: 1 is Group by, and the drawer's filters keep theirs while it is closed,
  // on stand-ins beside the chevron.
  await press("1");
  result.keyOneOpens = await browser.evaluate(OPEN_MENU);
  await press("Escape");
  await browser.waitFor(`!document.querySelector('.chip-menu[aria-expanded="true"]')`);
  // 3 is File type: it opens the closed drawer with its menu.
  await press("3");
  await browser.waitFor(`document.getElementById("filter-drawer").dataset.open === "true"`);
  await sleep(400);
  result.keyThreeOpens = await browser.evaluate(OPEN_MENU);
  await press("Escape");
  await browser.waitFor(`!document.querySelector('.chip-menu[aria-expanded="true"]')`);
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
  await viewport(TALL);
  await browser.waitFor(`window.innerHeight === ${TALL.height}`);
  phase("measured");

  // Group by File type: one section per group, headed in the menu group pattern.
  await toggle("group", true);
  await browser.evaluate(
    `document.querySelector('#filter-group-menu [data-chip-value="type"]').click(), true`,
  );
  await browser.waitFor("document.querySelectorAll('.tree-section').length > 1", 30000);
  await browser.evaluate(frames);
  result.byType = await browser.evaluate(SECTIONS);
  // A folder inside a section opens under that section's group.
  await browser.evaluate(
    `document.querySelector('.tree-section[data-tree-group="type:code"] .tree-folder[data-path="src"]').click(), true`,
  );
  await browser.waitFor(
    `document.querySelectorAll('.tree-section[data-tree-group="type:code"] .tree-file').length > 3`,
    30000,
  );
  result.codeFiles = await browser.evaluate(
    `[...document.querySelectorAll('.tree-section[data-tree-group="type:code"] .tree-file')].map((row) => row.dataset.path)`,
  );
  // src also stands in Documentation. With focus on Code's copy, the keys that close and
  // open it are mutations the tree repairs focus after: focus stays on Code's copy.
  const FOCUSED = `(() => { const row = document.activeElement; return { section: row?.closest(".tree-section")?.dataset.treeGroup ?? null, path: row?.dataset?.path ?? null, expanded: row?.getAttribute("aria-expanded") ?? null }; })()`;
  await browser.evaluate(
    `document.querySelector('.tree-section[data-tree-group="type:code"] .tree-folder[data-path="src"]').focus(), true`,
  );
  await press("ArrowLeft");
  await browser.evaluate(frames);
  result.focusAfterClose = await browser.evaluate(FOCUSED);
  await press("ArrowRight");
  await browser.waitFor(
    `document.querySelector('.tree-section[data-tree-group="type:code"] .tree-folder[data-path="src"]').getAttribute("aria-expanded") === "true"`,
  );
  await browser.evaluate(frames);
  result.focusAfterOpen = await browser.evaluate(FOCUSED);
  // A file written into a folder open two levels down refreshes the sections in place: the
  // folder stays open with the new file in it, and the scroll position and the focused row
  // inside it are kept. A headless page has no window focus, so its rows hear no focus
  // events, which a reader's window does; the emulation gives it that.
  await browser.send("Emulation.setFocusEmulationEnabled", { enabled: true });
  const LIB = `.tree-section[data-tree-group="type:code"] .tree-folder[data-path="src/lib"]`;
  await browser.evaluate(`document.querySelector('${LIB}').click(), true`);
  await browser.waitFor(
    `document.querySelector('${LIB}')?.getAttribute("aria-expanded") === "true"`,
  );
  const FOCUS_ROW = `.tree-section[data-tree-group="type:code"] .tree-file[data-path="src/lib/k06.py"]`;
  // The row takes focus once its folder's opening has made it visible; scrolled to the top
  // of the tree, it leaves the tree scrolled.
  await browser.waitFor(
    `(() => { const row = document.querySelector('${FOCUS_ROW}'); if (!row) return false; row.focus({ preventScroll: true }); return document.activeElement === row; })()`,
    30000,
  );
  await browser.evaluate(
    `document.querySelector('${FOCUS_ROW}').scrollIntoView({ block: "start" }), true`,
  );
  await browser.evaluate(frames);
  const REFRESH_STATE = `({ scrollTop: document.getElementById("tree-content").scrollTop, focused: document.activeElement?.dataset?.treeId ?? null, libOpen: document.querySelector('${LIB}')?.getAttribute("aria-expanded") ?? null, written: Boolean(document.querySelector('.tree-section[data-tree-group="type:code"] .tree-file[data-path="src/lib/k99.py"]')) })`;
  const beforeWrite = await browser.evaluate(REFRESH_STATE);
  fs.writeFileSync(path.join(root, "src", "lib", "k99.py"), "x99\n");
  const written = Date.now();
  let afterWrite = await browser.evaluate(REFRESH_STATE);
  while (!afterWrite.written && Date.now() - written < 15000) {
    await sleep(100);
    afterWrite = await browser.evaluate(REFRESH_STATE);
  }
  await browser.evaluate(frames);
  result.refresh = { before: beforeWrite, after: await browser.evaluate(REFRESH_STATE) };
  phase("refreshed");
  // No grouping is the one tree again.
  await toggle("group", true);
  await browser.evaluate(
    `document.querySelector('#filter-group-menu [data-chip-any]').click(), true`,
  );
  await browser.waitFor("document.querySelectorAll('.tree-section').length === 0", 30000);
  result.ungrouped = await browser.evaluate(
    `({ sections: document.querySelectorAll('.tree-section').length, trees: [...document.querySelectorAll('#tab-files [role="tree"]')].map((tree) => tree.getAttribute("aria-label")) })`,
  );
  result.slots = await browser.evaluate(SLOTS);
  phase("grouped");
  process.stdout.write(`${JSON.stringify(result)}\n`);
} finally {
  await chrome?.close();
  await server.stop();
  phase("closed");
}
