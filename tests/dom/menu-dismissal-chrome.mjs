// How every menu closes, in headless Chrome, with real presses (docs/design-system.md,
// "Every Menu Closes Alike"). tests/test_menu_dismissal_chrome.py serves a Git working
// tree with an HTML page and judges what this reports.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/menu-dismissal-chrome.mjs METAB ROOT PORT STATE
//
// For the Files tab's Group by, Modified within, and File type, the branch chooser, the
// gear, and the root details, it records whether a second press on the trigger, Escape,
// a press on a tree row, and a press in the HTML preview's frame close the menu, and where
// Escape leaves focus; for the Files dropdowns, a press on the bar beside them too. Then
// it records that a press which closes one menu still acts on what it lands on: the
// drawer's chevron, Show ignored, another dropdown's trigger, the branch chooser, the
// gear, and the root details. The last line is the JSON of all of it.
//
// A press here is the browser's own (Input.dispatchMouseEvent), so a press in the frame
// goes to the frame's document, as a reader's does.
import { spawn } from "node:child_process";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state] = process.argv.slice(2);
const base = `http://127.0.0.1:${port}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
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
      await Promise.race([exited, sleep(20000)]);
    },
  };
}

// Each menu: its trigger, and whether it is open.
const MENUS = {
  group: {
    trigger: '[data-chip-menu-toggle="group"]',
    open: `document.querySelector('.chip-menu[data-chip-menu="group"]')?.getAttribute("aria-expanded") === "true"`,
  },
  recency: {
    trigger: '[data-chip-menu-toggle="recency"]',
    drawer: true,
    open: `document.querySelector('.chip-menu[data-chip-menu="recency"]')?.getAttribute("aria-expanded") === "true"`,
  },
  types: {
    trigger: '[data-chip-menu-toggle="types"]',
    drawer: true,
    open: `document.querySelector('.chip-menu[data-chip-menu="types"]')?.getAttribute("aria-expanded") === "true"`,
  },
  branch: {
    trigger: "button.source-ref-selector-toggle",
    open: `document.querySelector("button.source-ref-selector-toggle")?.getAttribute("aria-expanded") === "true"`,
  },
  settings: {
    trigger: "#settings-btn",
    open: `document.getElementById("settings-control")?.getAttribute("aria-expanded") === "true"`,
  },
  rootDetails: {
    trigger: "#root-details > button",
    open: `document.getElementById("root-details-panel")?.hidden === false`,
  },
};
const DROPDOWNS = new Set(["group", "recency", "types"]);

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
  const page = chrome;
  await page.send("Page.enable");
  await page.send("Runtime.enable");
  await page.send("Page.navigate", { url: `${base}/` });
  await page.waitFor(`document.documentElement.dataset.shellToolsReady === "true"`, 60000);
  await page.waitFor(
    `!!document.querySelector('[data-chip-menu-toggle="group"]') && !!document.querySelector("button.source-ref-selector-toggle") && !!window.MetabrowserMenus`,
    30000,
  );
  phase("loaded");
  // Two frames, so what a press changed has painted and settled.
  const settle = () =>
    page.evaluate(
      "new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(() => done(true))))",
    );
  // The middle of what `selector` names, and whether a press there lands on it rather than
  // on a menu drawn over it.
  const point = (selector) =>
    page.evaluate(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return null;
      const box = el.getBoundingClientRect();
      const x = box.left + box.width / 2;
      const y = box.top + box.height / 2;
      const hit = document.elementFromPoint(x, y);
      return {x, y, uncovered: Boolean(hit && (el === hit || el.contains(hit)))};
    })()`);
  /** A press at a point, as a mouse makes one: move, down, up. */
  const pressAt = async (at) => {
    for (const type of ["mouseMoved", "mousePressed", "mouseReleased"]) {
      await page.send("Input.dispatchMouseEvent", {
        type,
        x: at.x,
        y: at.y,
        button: "left",
        clickCount: type === "mouseMoved" ? 0 : 1,
      });
    }
    await settle();
  };
  const press = async (selector) => {
    const at = await point(selector);
    if (!at) {
      throw new Error(`nothing to press at ${selector}`);
    }
    await pressAt(at);
  };
  const pressEscape = async () => {
    for (const type of ["keyDown", "keyUp"]) {
      await page.send("Input.dispatchKeyEvent", {
        type,
        key: "Escape",
        code: "Escape",
        windowsVirtualKeyCode: 27,
      });
    }
    await settle();
  };
  const isOpen = (name) => page.evaluate(MENUS[name].open);
  const openNow = async () => {
    const open = [];
    for (const name of Object.keys(MENUS)) {
      if (await isOpen(name)) {
        open.push(name);
      }
    }
    return open;
  };
  const drawerOpen = () =>
    page.evaluate(`document.getElementById("filter-drawer")?.dataset.open === "true"`);
  const showIgnored = () =>
    page.evaluate(`document.querySelector('[data-chip-check="showIgnored"]')?.checked ?? null`);
  /** Close everything, with focus back in this document, and the drawer as asked. */
  const reset = async ({ drawer = false } = {}) => {
    await page.evaluate("window.focus(), document.activeElement?.blur?.(), true");
    for (let tries = 0; tries < 3 && (await openNow()).length > 0; tries += 1) {
      await pressEscape();
    }
    if ((await drawerOpen()) !== drawer) {
      await press("[data-chip-key='drawer']");
      // The drawer's track grows over a transition; a trigger in it is clipped until then.
      await page.waitFor(
        `document.getElementById("filter-drawer").getAnimations({subtree: true}).length === 0`,
        10000,
      );
    }
    const left = await openNow();
    if (left.length > 0) {
      throw new Error(`could not close ${left.join(", ")}`);
    }
  };
  const open = async (name) => {
    await reset({ drawer: Boolean(MENUS[name].drawer) });
    await press(MENUS[name].trigger);
    if (!(await isOpen(name))) {
      throw new Error(`a press on ${name}'s trigger did not open it`);
    }
  };
  /** The focused control, named as the menus' triggers are. */
  const focused = () =>
    page.evaluate(`(() => {
      const active = document.activeElement;
      for (const [name, selector] of Object.entries(${JSON.stringify(
        Object.fromEntries(Object.entries(MENUS).map(([name, menu]) => [name, menu.trigger])),
      )})) {
        if (active === document.querySelector(selector)) return name + " trigger";
      }
      return active ? active.tagName.toLowerCase() : null;
    })()`);
  // A point on the filter bar that no control covers.
  const barGap = () =>
    page.evaluate(`(() => {
      const bar = document.getElementById("nav-filter-bar");
      const box = bar.getBoundingClientRect();
      for (let y = box.top + 2; y < box.bottom - 1; y += 3) {
        for (let x = box.left + 2; x < box.right - 1; x += 3) {
          const el = document.elementFromPoint(x, y);
          if (el && bar.contains(el) && !el.closest(".chip-menu, button, input, label, a")) {
            return {x, y};
          }
        }
      }
      return null;
    })()`);
  // The HTML page's preview, whose frame takes presses into a document of its own.
  const frame = async () => {
    if (!(await point("#preview-pane iframe"))) {
      await page.evaluate(`window.metabrowser.debug.selectFile("page.html")`);
      await page.waitFor(`!!document.querySelector("#preview-pane iframe")`, 30000);
      await settle();
    }
    return page.evaluate(`(() => {
      const box = document.querySelector("#preview-pane iframe").getBoundingClientRect();
      return {x: box.left + box.width / 2, y: box.top + 20};
    })()`);
  };

  const result = { menus: {}, pressesAct: {} };
  for (const name of Object.keys(MENUS)) {
    const seen = {};
    await open(name);
    await press(MENUS[name].trigger);
    seen.secondPressCloses = !(await isOpen(name));
    await open(name);
    await pressEscape();
    seen.escapeCloses = !(await isOpen(name));
    seen.focusAfterEscape = await focused();
    await open(name);
    // A tree row, a file's or a folder's, that the open menu does not cover.
    const row = await page.evaluate(`(() => {
      for (const row of document.querySelectorAll("#tab-files .tree-item")) {
        const box = row.getBoundingClientRect();
        const at = {x: box.left + Math.min(40, box.width / 2), y: box.top + box.height / 2};
        const hit = document.elementFromPoint(at.x, at.y);
        if (hit && row.contains(hit)) return at;
      }
      return null;
    })()`);
    if (!row) {
      throw new Error(`${name} covers every tree row`);
    }
    await pressAt(row);
    seen.treeRowCloses = !(await isOpen(name));
    if (DROPDOWNS.has(name)) {
      await open(name);
      const gap = await barGap();
      if (!gap) {
        throw new Error("no blank point on the filter bar");
      }
      await pressAt(gap);
      seen.barGapCloses = !(await isOpen(name));
    }
    const at = await frame();
    await open(name);
    await pressAt(at);
    seen.frameCloses = !(await isOpen(name));
    result.menus[name] = seen;
    phase(name);
  }

  /** Open one menu, press somewhere, and record what is open and what acted. */
  const across = async (name, target, read = async () => null) => {
    await open(name);
    const before = await read();
    const at = await point(target);
    if (!at) {
      throw new Error(`nothing to press at ${target}`);
    }
    await pressAt(at);
    return { open: await openNow(), landed: at.uncovered, before, after: await read() };
  };
  result.pressesAct.drawerChevron = await across("group", "[data-chip-key='drawer']", drawerOpen);
  // File type opens beside Show ignored; Modified within's rows cover it.
  result.pressesAct.showIgnored = await across(
    "types",
    '[data-chip-check="showIgnored"]',
    showIgnored,
  );
  result.pressesAct.otherDropdown = await across("types", MENUS.recency.trigger);
  result.pressesAct.branchFromGroup = await across("group", MENUS.branch.trigger);
  result.pressesAct.groupFromBranch = await across("branch", MENUS.group.trigger);
  result.pressesAct.gearFromGroup = await across("group", MENUS.settings.trigger);
  result.pressesAct.rootDetailsFromGear = await across("settings", MENUS.rootDetails.trigger);
  await reset();
  phase("across");
  process.stdout.write(`${JSON.stringify(result)}\n`);
} finally {
  await chrome?.close();
  await server.stop();
  phase("closed");
}
