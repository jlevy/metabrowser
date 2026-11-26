// The folder's name goes home, and `0` does the same, in headless Chrome against a live
// `metab` serving the GitHub stand-in's checkout.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> [SHOTS_DIR=<dir>] \
//     node tests/dom/folder-home-chrome.mjs <checkout URL>
//
// tests/test_folder_home_chrome.py serves it and owns the profile directory, and stops this
// process's whole group, Chrome included, however the run ends (tests/process_group.py).
//
// Home is the served folder's home view as a fresh load of `/view/` shows it
// (docs/design-system.md, "Home"). So the script first loads `/view/` and records what the
// page shows: the address, the tab in front, the main pane's file and view tab, the Files
// tab's filters, grouping, drawer, open folders, selection, and scroll, and the pane's
// scroll. Every route then leaves the page somewhere else, goes home, and must show exactly
// that record again: a click on the name from a pull request's Changes tab, `0` from a
// file's Source view with the Files tab grouped, filtered, opened, and scrolled, Shift-0
// from Commits, and `0` on the root itself showing another view. After Home, Pulls opens
// its list rather than the pull request it last showed, and `0` from a Pulls list whose
// Tab stop `J` moved and whose changed files Right opened, from its toggle, leaves it as
// a fresh load draws it: `P` then focuses the first row, with no stack closed and no files
// open. The name is announced as "Home: <folder>".
//
// Each step writes `phase <name> <ms since start>` to stderr, and `measure <name> <json>`
// for what Home cost: its time to the root's view, and any frame the pane was blank.
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES folder-home-chrome.mjs <URL>");
}
const SHOTS = process.env.SHOTS_DIR ?? null;
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
const measure = (name, value) => process.stderr.write(`measure ${name} ${JSON.stringify(value)}\n`);
// Each wait's bound: a page load, a key, or the fake gh's answer for a pull request.
const STEP_MS = 30000;
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    const failure = `${label}${detail ? `: ${detail}` : ""}`;
    failures.push(failure);
    // As it happens, so a run that stops later still says what failed before.
    process.stderr.write(`failed ${failure}\n`);
  }
};

// In the page: everything a fresh load of the home address decides, as a reader sees it.
const STATE = `(() => {
  const preview = document.getElementById("preview-pane");
  const scroller = document.getElementById("tree-content");
  const viewTab = preview.querySelector(":scope > .tab-bar > .tab-btn.active");
  const filters = window.metabrowser?.filterState?.get() ?? null;
  return {
    address: location.pathname + location.search + location.hash,
    tab: document.querySelector(".nav-tab-bar .tab-btn.active")?.dataset.tab ?? null,
    file: preview.dataset.renderedPath ?? null,
    view: viewTab?.textContent.trim() ?? null,
    paneScroll: preview.scrollTop,
    treeScroll: scroller.scrollTop,
    filters,
    drawer: document.getElementById("filter-drawer")?.dataset.open ?? null,
    sections: document.querySelectorAll("#tab-files > .tree-section").length,
    openFolders: [...document.querySelectorAll("#tab-files .tree-folder.expanded")]
      .map((row) => row.dataset.path).sort(),
    selected: [...document.querySelectorAll("#tab-files .tree-item.selected")]
      .map((row) => row.dataset.path),
  };
})()`;

// In the page: what the Pulls list decides that a fresh load draws, as a reader sees it,
// each row named as it reads: its stacks closed, the pull requests whose changed files are
// open, which their rows say (mb-1z7j), the row that takes Tab, and the row with focus, or
// a toggle, which never takes it.
const PULLS = `(() => {
  const rows = [...document.querySelectorAll("#tab-pulls .github-pulls-row")];
  const name = (row) =>
    !row ? null : row.dataset.stack ? "Stack #" + row.dataset.stack : "#" + row.dataset.number;
  const line = document.activeElement?.closest?.("#tab-pulls .github-pulls-change");
  return {
    first: name(rows[0]),
    closedStacks: rows
      .filter((row) => row.dataset.stack && row.getAttribute("aria-expanded") === "false")
      .map(name),
    filesOpen: rows
      .filter((row) => !row.dataset.stack && row.getAttribute("aria-expanded") === "true")
      .map(name),
    tabStop: name(rows.find((row) => row.getAttribute("tabindex") === "0")),
    focused: line ? "#" + line.dataset.number + " toggle" : name(document.activeElement?.closest?.(".github-pulls-row")),
  };
})()`;

// In the page: the tooltip as a reader sees it.
const TIP = `(() => {
  const tip = document.querySelector(".custom-tooltip");
  return {
    shown: tip !== null && tip.style.display === "block" && tip.classList.contains("visible"),
    text: tip?.textContent ?? "",
  };
})()`;

const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
  width: 1280,
  height: 800,
});
try {
  phase("chrome");
  const { evaluate, send } = chrome;
  const pageErrors = [];
  chrome.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    pageErrors.push(exceptionDetails.exception?.description ?? exceptionDetails.text),
  );
  await send("Runtime.enable");
  await send("Page.enable");
  await send("DOM.enable");
  await send("Accessibility.enable");
  const waitFor = async (expression, what) => {
    try {
      return await chrome.waitFor(expression, STEP_MS);
    } catch (error) {
      const state = await evaluate(STATE).catch(() => null);
      throw new Error(
        `${what}: ${error.message}\nstate: ${JSON.stringify(state)}\npage errors: ${pageErrors.join("\n")}`,
      );
    }
  };
  const frames = () =>
    evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))");
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const load = async (url) => {
    const loaded = new Promise((resolve) => chrome.on("Page.loadEventFired", resolve));
    await send("Page.navigate", { url });
    await loaded;
    // The keys are bound once the shell's tools have loaded after the first tree.
    await waitFor(
      `document.documentElement.dataset.shellToolsReady === "true"`,
      `the shell's tools at ${url}`,
    );
  };
  const shot = async (name) => {
    if (SHOTS === null) {
      return;
    }
    await frames();
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    fs.mkdirSync(SHOTS, { recursive: true });
    fs.writeFileSync(path.join(SHOTS, `${name}.png`), Buffer.from(data, "base64"));
  };
  /** A real key, as the keyboard sends it, to the focused element. */
  const press = async (key, { code, keyCode, modifiers = 0, text }) => {
    await send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key,
      code,
      modifiers,
      windowsVirtualKeyCode: keyCode,
      text,
    });
    await send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key,
      code,
      modifiers,
      windowsVirtualKeyCode: keyCode,
    });
    await frames();
  };
  const ZERO = { code: "Digit0", keyCode: 48, text: "0" };
  const SHIFT_ZERO = { code: "Digit0", keyCode: 48, modifiers: 8, text: ")" };
  const P_KEY = { code: "KeyP", keyCode: 80, text: "p" };
  const J_KEY = { code: "KeyJ", keyCode: 74, text: "j" };
  const RIGHT = { code: "ArrowRight", keyCode: 39 };
  const PULL_ROWS = `document.querySelectorAll("#tab-pulls .github-pulls-row").length > 1`;
  const ROW_FOCUSED = `document.activeElement?.matches?.("#tab-pulls .github-pulls-row") === true`;
  const pointer = (type, at) =>
    send("Input.dispatchMouseEvent", {
      type,
      x: at.x,
      y: at.y,
      button: type === "mouseMoved" ? "none" : "left",
      clickCount: type === "mouseMoved" ? 0 : 1,
    });
  const heading = async () =>
    evaluate(`(() => {
      const box = document.querySelector(".header-path").getBoundingClientRect();
      return { x: Math.round(box.left + Math.min(box.width / 2, 30)), y: Math.round(box.top + box.height / 2) };
    })()`);
  // Far from the name, over the main pane, where no tooltip answers.
  const AWAY = { x: 900, y: 700 };

  /**
   * Record every frame of the main pane from now until Home has drawn the root, so a blank
   * pane or a spinner between the two is seen, and how long Home took.
   */
  const watchFrames = () =>
    evaluate(`(() => {
      const frames = [];
      const begun = performance.now();
      window.__homeFrames = frames;
      window.__homeBegun = begun;
      const sample = () => {
        const preview = document.getElementById("preview-pane");
        frames.push({
          ms: Math.round(performance.now() - begun),
          address: location.pathname,
          file: preview.dataset.renderedPath ?? null,
          // The pane's own placeholder, not a spinner inside a view it shows.
          blank: preview.childElementCount === 0 ||
            preview.querySelector(":scope > :is(.loading, .spinner, .preview-empty, .mb-delayed-loading)") !== null,
          shows: preview.firstElementChild?.className ?? null,
        });
        if (performance.now() - begun < 2000) {
          requestAnimationFrame(sample);
        }
      };
      requestAnimationFrame(sample);
    })()`);
  const framesSeen = async (label) => {
    await sleep(2100);
    const seen = await evaluate("window.__homeFrames");
    // What Home asked the server for, with how long each took.
    const requests = await evaluate(`performance.getEntriesByType("resource")
      .filter((entry) => entry.startTime >= window.__homeBegun)
      .map((entry) => { const url = new URL(entry.name); return \`\${url.pathname}\${url.search} \${Math.round(entry.duration)} ms\`; })`);
    const home = seen.find((frame) => frame.address === "/view/" && frame.file === "");
    const blank = seen.filter((frame) => frame.blank).length;
    measure(label, {
      msToRoot: home?.ms ?? null,
      frames: seen.length,
      blankFrames: blank,
      blank: seen.filter((frame) => frame.blank).slice(0, 3),
      requests,
    });
    check(`${label}: the root is drawn within the frames watched`, home !== undefined);
    check(`${label}: no frame shows a blank pane or a spinner`, blank === 0, `${blank} frames`);
  };

  /** Home has settled into exactly what a fresh load showed, or the step fails with both. */
  const isFresh = async (label, fresh) => {
    const same = `JSON.stringify(${STATE}) === ${JSON.stringify(JSON.stringify(fresh))}`;
    await chrome.waitFor(same, STEP_MS).catch(() => {});
    const now = await evaluate(STATE);
    for (const [field, value] of Object.entries(fresh)) {
      check(
        `${label}: ${field} is a fresh load's`,
        JSON.stringify(now[field]) === JSON.stringify(value),
        `${JSON.stringify(now[field])}, fresh ${JSON.stringify(value)}`,
      );
    }
    return now;
  };

  // ── What a fresh load of the home address shows ──────────────
  await load(`${base}/view/`);
  await waitFor(
    `document.getElementById("preview-pane").dataset.renderedPath === "" && document.querySelector("#preview-pane > .tab-bar > .tab-btn.active") !== null`,
    "the root's view",
  );
  await frames();
  const fresh = await evaluate(STATE);
  phase("fresh");
  measure("fresh", fresh);
  check("a fresh load: Files is in front", fresh.tab === "files", JSON.stringify(fresh));
  check("a fresh load: nothing is selected", fresh.selected.length === 0, JSON.stringify(fresh));
  const views = await evaluate(
    `[...document.querySelectorAll("#preview-pane > .tab-bar > .tab-btn")].map((tab) => tab.textContent.trim())`,
  );
  measure("root views", views);

  // The name is a link home: its accessible name, from Chrome's own accessibility tree.
  const { root } = await send("DOM.getDocument", { depth: 0 });
  const { nodeId } = await send("DOM.querySelector", {
    nodeId: root.nodeId,
    selector: ".header-path",
  });
  const { nodes } = await send("Accessibility.getPartialAXTree", {
    nodeId,
    fetchRelatives: false,
  });
  const named = nodes.find((node) => !node.ignored);
  const folder = await evaluate(`document.querySelector(".header-path").textContent.trim()`);
  check(
    "the name is called Home and the folder",
    named?.name?.value === `Home: ${folder}` && named?.role?.value === "link",
    JSON.stringify({ name: named?.name?.value, role: named?.role?.value }),
  );

  // Hover paints the name as a link in the navigation does.
  const rest = await evaluate(
    `getComputedStyle(document.querySelector(".header-path")).backgroundColor`,
  );
  await pointer("mouseMoved", await heading());
  await frames();
  const hovered = await evaluate(
    `getComputedStyle(document.querySelector(".header-path")).backgroundColor`,
  );
  const hoverToken = await evaluate(`(() => {
    const probe = document.createElement("div");
    probe.style.background = "var(--hover-bg)";
    document.body.append(probe);
    const value = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return value;
  })()`);
  check(
    "hover paints the name with the hover token",
    hovered === hoverToken && hovered !== rest,
    JSON.stringify({ rest, hovered, hoverToken }),
  );
  await shot("hover");

  // Holding Shift reveals `0` on the name: a keycap over the name's own end, inside the
  // header, and in the revealed strip.
  await pointer("mouseMoved", { x: 900, y: 700 });
  await evaluate("document.activeElement?.blur?.()");
  await send("Input.dispatchKeyEvent", {
    type: "rawKeyDown",
    key: "Shift",
    code: "ShiftLeft",
    modifiers: 8,
    windowsVirtualKeyCode: 16,
  });
  await waitFor(`document.documentElement.hasAttribute("data-key-reveal")`, "the Shift reveal");
  await sleep(300);
  const badge = await evaluate(`(() => {
    const name = document.querySelector(".header-path").getBoundingClientRect();
    const header = document.querySelector(".app-header").getBoundingClientRect();
    const badge = [...document.querySelectorAll(".kbd-badge")].find((node) => node.textContent.trim() === "0");
    const box = badge?.getBoundingClientRect();
    const strip = [...document.querySelectorAll(".nav-shortcut-hints *")].some((node) => node.textContent.replace(/\\s+/g, "").startsWith("0Home"));
    return box ? {
      overNameEnd: box.left < name.right && box.right > name.right - box.width - 2,
      inHeader: box.top >= header.top && box.bottom <= header.bottom,
      strip,
      at: [Math.round(box.left), Math.round(box.right), Math.round(name.left), Math.round(name.right)],
    } : { strip };
  })()`);
  await shot("reveal");
  await send("Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Shift",
    code: "ShiftLeft",
    modifiers: 0,
    windowsVirtualKeyCode: 16,
  });
  measure("reveal badge", badge);
  check(
    "Shift reveals 0 on the name's end, inside the header, and in the strip",
    badge.overNameEnd === true && badge.inHeader === true && badge.strip === true,
    JSON.stringify(badge),
  );

  // What a fresh load's Pulls list shows, before any route has worked on it: no stack
  // closed, no pull request's changed files open, and `P` focusing the first row.
  await evaluate(`document.querySelector('.nav-tab-bar .tab-btn[data-tab="pulls"]').click()`);
  await waitFor(PULL_ROWS, "a fresh load's Pulls rows");
  await evaluate("document.activeElement?.blur?.()");
  await press("p", P_KEY);
  await waitFor(ROW_FOCUSED, "P focuses a row of a fresh load's Pulls");
  const freshPulls = await evaluate(PULLS);
  measure("fresh Pulls", freshPulls);
  check(
    "a fresh load's Pulls: P focuses the first row, and nothing is closed or open",
    freshPulls.first !== null &&
      freshPulls.focused === freshPulls.first &&
      freshPulls.tabStop === freshPulls.first &&
      freshPulls.closedStacks.length === 0 &&
      freshPulls.filesOpen.length === 0,
    JSON.stringify(freshPulls),
  );

  // ── 1. A click on the name, from a pull request's Changes tab ─
  await load(`${base}/pull/7/files`);
  await waitFor(
    `document.querySelector('#preview-pane .tab-btn.active[aria-selected="true"]')?.textContent.trim() === "Changes"`,
    "#7's Changes tab",
  );
  phase("pull request");
  await shot("changes");
  const at = await heading();
  await pointer("mouseMoved", at);
  await watchFrames();
  await pointer("mousePressed", at);
  await pointer("mouseReleased", at);
  await framesSeen("click from a pull request's Changes tab");
  await isFresh("a click from a pull request's Changes tab", fresh);
  await shot("home-from-changes");

  // Every tab forgot where it was: Pulls opens its list, not the pull request it showed.
  await evaluate(`document.querySelector('.nav-tab-bar .tab-btn[data-tab="pulls"]').click()`);
  await waitFor(`location.pathname.startsWith("/pull")`, "Pulls opens");
  await frames();
  const pulls = await evaluate("location.pathname + location.search");
  check("after Home, Pulls opens its list", pulls === "/pulls", pulls);

  // ── 1b. `0` from the Pulls list, its rows worked on ───────────
  // The reader walks the list with `J`, which moves the Tab stop and opens the next pull
  // request, and opens that one's changed files with Right, as on a folder's, focus staying
  // on its row (mb-1z7j). Home then leaves the list as a fresh load draws it, so `P`
  // afterwards focuses the first row, with no files open.
  await waitFor(PULL_ROWS, "the Pulls rows");
  await evaluate("document.activeElement?.blur?.()");
  await press("p", P_KEY);
  await waitFor(ROW_FOCUSED, "P focuses a Pulls row");
  await press("j", J_KEY);
  await waitFor(`location.pathname.startsWith("/pull/")`, "J opens the next pull request");
  const walked = await evaluate(PULLS);
  await press("ArrowRight", RIGHT);
  await waitFor(
    `document.querySelector('#tab-pulls a.github-pulls-row[aria-expanded="true"]:not(.github-pulls-stack-row):not(.github-pulls-whole-row)') !== null`,
    "Right on the row opens its changed files",
  );
  const workedPulls = await evaluate(PULLS);
  measure("worked-on Pulls", { walked, workedPulls });
  check(
    "the Pulls list is worked on before Home: the Tab stop moved, and Right on its row opened its files, focus staying on the row",
    workedPulls.tabStop !== freshPulls.first &&
      walked.filesOpen.length === 0 &&
      workedPulls.focused === workedPulls.tabStop &&
      JSON.stringify(workedPulls.filesOpen) === JSON.stringify([workedPulls.tabStop]),
    JSON.stringify({ walked, workedPulls }),
  );
  await shot("pulls-worked-on");
  await evaluate("document.activeElement?.blur?.()");
  await press("0", ZERO);
  await isFresh("0 from the Pulls list worked on", fresh);
  await press("p", P_KEY);
  await waitFor(
    `location.pathname === "/pulls" && ${ROW_FOCUSED}`,
    "P after Home opens the list and focuses a row",
  );
  const homedPulls = await evaluate(PULLS);
  measure("Pulls after Home", homedPulls);
  for (const field of ["closedStacks", "filesOpen", "tabStop", "focused"]) {
    check(
      `after Home, Pulls: ${field} is a fresh load's`,
      JSON.stringify(homedPulls[field]) === JSON.stringify(freshPulls[field]),
      `${JSON.stringify(homedPulls[field])}, fresh ${JSON.stringify(freshPulls[field])}`,
    );
  }
  await shot("pulls-after-home");
  phase("0 from the Pulls list");

  await pointer("mouseMoved", at);
  await pointer("mousePressed", at);
  await pointer("mouseReleased", at);
  await isFresh("a click from the Pulls list", fresh);
  await pointer("mouseMoved", AWAY);

  // ── 2. `0` from a file's Source view, the Files tab worked on ─
  await evaluate(`document.querySelector('#tab-files .tree-item[data-path="README.md"]').click()`);
  await waitFor(`location.pathname === "/view/README.md"`, "README.md opens");
  await waitFor(
    `[...document.querySelectorAll("#preview-pane > .tab-bar > .tab-btn")].some((tab) => tab.textContent.trim() === "Source")`,
    "README.md's Source tab",
  );
  await evaluate(
    `[...document.querySelectorAll("#preview-pane > .tab-bar > .tab-btn")].find((tab) => tab.textContent.trim() === "Source").click()`,
  );
  // Open the long folder, which a first paint leaves closed, and scroll the tree into it.
  await evaluate(
    `toggleTreeFolder(document.querySelector('#tab-files .tree-folder[data-path="long"]'))`,
  );
  // Open, and done travelling: the scroller is tall enough to scroll only once it is.
  await waitFor(
    `(() => {
      const scroller = document.getElementById("tree-content");
      const open = document.querySelector('#tab-files .tree-item[data-path="long/f100.txt"]') !== null;
      const children = document.querySelector('#tab-files .tree-folder[data-path="long"]')?.nextElementSibling;
      return open && scroller.scrollHeight > scroller.clientHeight + 1200 &&
        children?.getAnimations({ subtree: true }).length === 0;
    })()`,
    "the long folder opens",
  );
  await evaluate(`document.getElementById("tree-content").scrollTop = 1200`);
  await waitFor(`document.getElementById("tree-content").scrollTop > 0`, "the tree scrolls");
  await frames();
  const worked = await evaluate(STATE);
  check(
    "the Files tab is worked on before Home",
    worked.view === "Source" &&
      worked.treeScroll > 0 &&
      worked.openFolders.includes("long") &&
      worked.selected.includes("README.md"),
    JSON.stringify(worked),
  );
  await shot("worked-on");
  await evaluate("document.activeElement?.blur?.()");
  await watchFrames();
  await press("0", ZERO);
  await framesSeen("0 from a file's Source view");
  await isFresh("0 from a file's Source view", fresh);
  phase("0 from a file");

  // Group by, a filter, and the drawer: Home draws the tree as a fresh load does.
  await evaluate(`window.metabrowser.filterState.set({ group: "type", size: "100k" })`);
  await waitFor(
    `document.querySelectorAll("#tab-files > .tree-section").length > 0 || document.querySelector("#tab-files .recent-empty") !== null`,
    "the tree is grouped",
  );
  await evaluate(`document.querySelector("[data-chip-key='drawer']")?.click()`);
  await waitFor(
    `document.getElementById("filter-drawer")?.dataset.open === "true"`,
    "the filter drawer opens",
  );
  await evaluate("document.activeElement?.blur?.()");
  await press("0", ZERO);
  await isFresh("0 with a grouping, a filter, and the drawer open", fresh);
  phase("0 with filters");

  // ── 3. Shift-0 from Commits ───────────────────────────────────
  await evaluate(`document.querySelector('.nav-tab-bar .tab-btn[data-tab="git"]').click()`);
  await waitFor(`location.pathname.startsWith("/commit/")`, "Commits lands on its newest commit");
  await evaluate("document.activeElement?.blur?.()");
  await watchFrames();
  await press(")", SHIFT_ZERO);
  await framesSeen("Shift-0 from Commits");
  await isFresh("Shift-0 from Commits", fresh);
  const tipAfterKey = await evaluate(TIP);
  check("a key shows no tooltip", !tipAfterKey.shown, JSON.stringify(tipAfterKey));
  phase("Shift-0 from Commits");

  // ── 4. `0` on the root it shows, at another view ──────────────
  // A route whose precondition fails is a failure, not a route skipped.
  check("the root has a second view", views.length > 1, JSON.stringify(views));
  if (views.length > 1) {
    const other = views.find((label) => label !== fresh.view);
    await evaluate(
      `[...document.querySelectorAll("#preview-pane > .tab-bar > .tab-btn")].find((tab) => tab.textContent.trim() === ${JSON.stringify(other)}).click()`,
    );
    await waitFor(
      `document.querySelector("#preview-pane > .tab-bar > .tab-btn.active")?.textContent.trim() === ${JSON.stringify(other)}`,
      `the root's ${other} view`,
    );
    await evaluate("document.activeElement?.blur?.()");
    await watchFrames();
    await press("0", ZERO);
    await framesSeen(`0 on the root at ${other}`);
    await isFresh(`0 on the root at ${other}`, fresh);
    phase("0 on the root");
  }

  // A text field keeps its 0: the settings menu's text width, with Commits in front. The
  // menu opens after the tab's click, which a click outside it closes, and a field in a
  // closed menu takes no focus.
  await evaluate(`document.querySelector('.nav-tab-bar .tab-btn[data-tab="git"]').click()`);
  await waitFor(`location.pathname.startsWith("/commit/")`, "Commits again");
  await evaluate(`document.getElementById("settings-btn").click()`);
  await frames();
  await evaluate(`document.getElementById("doc-max-chars-input").focus()`);
  const fieldFocused = await evaluate(`document.activeElement?.id === "doc-max-chars-input"`);
  check("the settings field takes focus", fieldFocused);
  if (fieldFocused) {
    await press("0", ZERO);
    await sleep(300);
    const stayed = await evaluate("location.pathname");
    check("0 in a text field is the field's", stayed.startsWith("/commit/"), stayed);
  }

  check("no script error on the page", pageErrors.length === 0, pageErrors.join("\n"));
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`folder home in Chrome: ${checks} checks passed\n`);
