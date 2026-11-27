// The table view, laid out by a real engine: a served folder of delimited files, the
// shell's own page, and headless Chrome.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/table-view-chrome.mjs METAB ROOT PORT STATE_DIR [SHOTS_DIR]
//
// tests/test_table_view_chrome.py writes the folder, owns the profile and STATE_DIR, runs
// this in a process group of its own, which Chrome and the server join, and judges what it
// prints: one JSON line of measurements. With SHOTS_DIR it also saves a screenshot of each
// table.
//
// What it measures is what no browserless DOM computes: that every row of a table is one
// height, one line or two as the table's longest values need, and a longer value is cut
// with its whole text in the shared tooltip, which shows only for a value cut short; that
// the header stays at the top of the grid's own scroll box as it scrolls, and the box,
// not the page, scrolls; that columns the reader chose keep their first column in place
// as they scroll sideways, and default columns too many for the pane hide from the right
// with a note; and that null is drawn in the muted ink, a number right-aligned in tabular
// numerals, and a date in the monospaced face; that a windowed table's print says which
// rows it printed; the browser's own history: that a run of key presses past Chrome's
// bound on history calls (200 in 10 seconds) still lets Enter push the record's address,
// whose Back link returns to the grid where the keys left it, and that a reload returns
// there too; and that the structured kind's Table tab draws a JSON list of records with
// nested values in the shared grid, and shows a mapping or mixed sequence in the
// structured node table. Which rows, columns, and cells exist, what a key does, and what the
// address holds run browserlessly in tests/dom/table-view-session.js.

// Key presses in a run: past the 200 history calls Chrome allows in 10 seconds.
const PRESSES = 260;

import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state, shots] = process.argv.slice(2);
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
      env: { ...process.env, METABROWSER_LOG_LEVEL: "WARNING", METABROWSER_EVENT_LOG: "0" },
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

// In the page: the shown table view's parts.
const VIEW = `window.__t = () => {
  const view = [...document.querySelectorAll(".table-view")].find((node) => node.getClientRects().length > 0);
  return {
    view,
    scroll: view?.querySelector(".table-scroll"),
    q: (selector) => view?.querySelector(selector),
    qa: (selector) => [...(view?.querySelectorAll(selector) ?? [])],
  };
}`;

const ROWS = `(() => {
  const rows = __t().qa("tbody tr:not(.table-spacer)");
  const round = (value) => Math.round(value * 10) / 10;
  const heights = [...new Set(rows.map((row) => round(row.getBoundingClientRect().height)))];
  const line = parseFloat(getComputedStyle(__t().view).getPropertyValue("--table-line-height"));
  const cells = __t().qa(".table-cell");
  const cut = cells.filter((cell) => cell.scrollWidth > cell.clientWidth + 1 || cell.scrollHeight > cell.clientHeight + 1);
  return {
    rows: rows.length,
    heights,
    line,
    lines: __t().q("table").classList.contains("table-lines-2") ? 2 : 1,
    cellHeights: [...new Set(cells.map((cell) => round(cell.getBoundingClientRect().height)))],
    cut: cut.map((cell) => cell.textContent.slice(0, 20)),
  };
})()`;

async function main() {
  const profiles = process.env.CHROME_PROFILES;
  if (!process.env.CHROME_BIN || !profiles) {
    throw new Error("CHROME_BIN and CHROME_PROFILES are required");
  }
  const server = await serve();
  phase("server");
  /** @type {Awaited<ReturnType<typeof launchChrome>> | null} */
  let chrome = null;
  const measured = {};
  try {
    chrome = await launchChrome(process.env.CHROME_BIN, { profiles });
    phase("chrome");
    await chrome.send("Page.enable");
    await chrome.send("Runtime.enable");
    const problems = [];
    chrome.on("Runtime.exceptionThrown", (p) =>
      problems.push(JSON.stringify(p.exceptionDetails).slice(0, 300)),
    );
    const shot = async (name) => {
      if (!shots) {
        return;
      }
      fs.mkdirSync(shots, { recursive: true });
      const { data } = await chrome.send("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(path.join(shots, `${name}.png`), Buffer.from(data, "base64"));
    };
    const open = async (address, rows) => {
      await chrome.send("Page.navigate", { url: `${base}/view/${address}` });
      await chrome.evaluate(VIEW);
      await chrome.waitFor(
        `(() => { try { ${VIEW}; return __t().qa("tbody tr:not(.table-spacer)").length >= ${rows}; } catch { return false; } })()`,
      );
      await chrome.evaluate(VIEW);
      await sleep(200);
    };
    const hover = async (selectorExpression) => {
      const box = await chrome.evaluate(
        `(() => { const r = (${selectorExpression}).getBoundingClientRect(); return {x: r.left + 5, y: r.top + r.height / 2}; })()`,
      );
      await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1, y: 1 });
      await sleep(100);
      await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: box.x, y: box.y });
      await sleep(1200);
      return chrome.evaluate(
        `(() => { const tip = document.querySelector(".custom-tooltip"); return tip && getComputedStyle(tip).display !== "none" ? tip.textContent : null; })()`,
      );
    };

    // One line a row: every row one height, a long value cut on its line, its whole text
    // in the tooltip, and no tooltip for a value shown whole.
    await open("short.csv", 3);
    measured.progressPaint = await chrome.evaluate(`(() => {
      const sidebar = document.querySelector("#index-progress");
      const inline = document.createElement("div");
      document.querySelector("#preview-pane").append(inline);
      window.metabrowser.renderIndexProgress(inline, "Indexing collection…");
      const paint = (status) => {
        const text = getComputedStyle(status.querySelector(".index-progress-text"));
        const spinner = getComputedStyle(status.querySelector(".index-progress-spinner"));
        return [text.color, text.fontFamily, text.fontSize, text.lineHeight, spinner.width,
          spinner.height, spinner.borderTop, spinner.borderRight, spinner.animationName,
          spinner.animationDuration];
      };
      const equal = JSON.stringify(paint(sidebar)) === JSON.stringify(paint(inline));
      inline.remove();
      return equal;
    })()`);
    measured.short = await chrome.evaluate(ROWS);
    measured.short.tip = await hover(
      `__t().qa(".table-cell").find((cell) => cell.textContent.startsWith("表表"))`,
    );
    measured.short.wholeTip = await hover(
      `__t().qa(".table-cell").find((cell) => cell.textContent === "Ada")`,
    );
    measured.short.paint = await chrome.evaluate(`(() => {
      const probe = document.createElement("span");
      document.body.append(probe);
      const token = (name) => { probe.style.color = "var(" + name + ")"; return getComputedStyle(probe).color; };
      const ink = { muted: token("--muted"), text: token("--text") };
      probe.remove();
      const nullCell = __t().q(".table-cell-null");
      const number = __t().q("td.data-num");
      const date = __t().q(".table-cell.data-literal:not(.table-cell-null)");
      const name = __t().q(".table-cell:not(.data-literal)");
      return {
        nullInk: getComputedStyle(nullCell).color === ink.muted,
        textInk: getComputedStyle(name).color === ink.text,
        numberAlign: getComputedStyle(number).textAlign,
        numberNumerals: getComputedStyle(number).fontVariantNumeric,
        dateFace: getComputedStyle(date).fontFamily !== getComputedStyle(name).fontFamily,
        dateMono: getComputedStyle(date).fontFamily === getComputedStyle(document.documentElement).getPropertyValue("--font-mono").trim() || getComputedStyle(date).fontFamily.toLowerCase().includes("mono"),
      };
    })()`);
    await shot("1-short");
    phase("short");

    // Two lines a row: a value with more than the column holds wraps to a second line and
    // is cut there.
    await open("long-text.csv", 2);
    measured.twoLines = await chrome.evaluate(ROWS);
    await shot("2-two-lines");
    phase("two-lines");

    // A long table, printed before it has read past its first page: the page says which
    // rows it printed, and the toolbar, with the count, is not printed.
    await open("many.csv", 20);
    await chrome.send("Emulation.setEmulatedMedia", { media: "print" });
    measured.print = await chrome.evaluate(`(() => {
      window.dispatchEvent(new Event("beforeprint"));
      const note = __t().q(".table-print-note");
      const shown = {
        note: note.textContent,
        noteShown: getComputedStyle(note).display !== "none",
        toolbarShown: getComputedStyle(__t().q(".table-toolbar")).display !== "none",
        rows: __t().qa("tbody tr:not(.table-spacer)").length,
      };
      window.dispatchEvent(new Event("afterprint"));
      return shown;
    })()`);
    // A table read past PRINT_MAX_ROWS: the printout draws that many and says so.
    await chrome.send("Emulation.setEmulatedMedia", { media: "" });
    await open("printed.csv", 20);
    measured.printBound = await chrome.evaluate(`(async () => {
      const scroll = __t().scroll;
      const rowPx = __t().q("tbody tr:not(.table-spacer)").getBoundingClientRect().height;
      const held = () => Math.round(__t().q("tbody").getBoundingClientRect().height / rowPx);
      for (let wait = 0; wait < 400 && held() < 2500; wait++) {
        scroll.scrollTop = scroll.scrollHeight;
        await new Promise((resolve) => setTimeout(resolve, 25));
      }
      const heldBefore = held();
      window.dispatchEvent(new Event("beforeprint"));
      const printed = {
        held: heldBefore,
        rows: __t().qa("tbody tr:not(.table-spacer)").length,
        note: __t().q(".table-print-note").textContent,
      };
      window.dispatchEvent(new Event("afterprint"));
      return printed;
    })()`);

    // A long table: the grid's own box scrolls, and its header stays at the box's top.
    measured.sticky = await chrome.evaluate(`(async () => {
      const scroll = __t().scroll;
      const head = __t().q("thead th");
      const pane = document.querySelector(".preview-pane");
      const before = { box: scroll.getBoundingClientRect().top, head: head.getBoundingClientRect().top };
      scroll.scrollTop = 2000;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const after = { box: scroll.getBoundingClientRect().top, head: head.getBoundingClientRect().top };
      return {
        scrolled: scroll.scrollTop,
        headAtTop: Math.abs(after.head - after.box) < 1,
        headStill: Math.abs(after.head - before.head) < 1,
        boxScrolls: scroll.scrollHeight > scroll.clientHeight,
        paneStill: pane.scrollTop === 0,
        boxInPane: scroll.getBoundingClientRect().bottom <= pane.getBoundingClientRect().bottom + 1,
        firstDrawn: Number(__t().q("tbody tr:not(.table-spacer)").dataset.index),
      };
    })()`);
    await shot("3-sticky");
    phase("sticky");

    // A run of key presses, then Enter: the view writes its place once the keys stop, not
    // a press each, so Chrome still takes the record's push; the Back link returns to the
    // grid at the row and scroll the keys left, and so does a reload.
    await open("many.csv", 20);
    measured.history = await chrome.evaluate(`(async () => {
      const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const until = async (test) => {
        for (let wait = 0; wait < 200 && !test(); wait++) {
          await new Promise((resolve) => setTimeout(resolve, 25));
        }
        return test();
      };
      const calls = { pushState: 0, replaceState: 0 };
      for (const name of Object.keys(calls)) {
        const original = history[name].bind(history);
        history[name] = (...args) => {
          calls[name] += 1;
          return original(...args);
        };
      }
      const press = (key) =>
        document.activeElement.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
      __t().q("tbody tr:not(.table-spacer)").focus();
      for (let index = 0; index < ${PRESSES}; index++) {
        press("ArrowDown");
        if (index % 20 === 19) {
          await frames();
        }
      }
      const whilePressing = { ...calls };
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const afterPause = { ...calls };
      const row = Number(document.activeElement.dataset.index);
      press("Enter");
      const opened = await until(() => __t().q(".table-record-title")?.textContent);
      const recordAddress = location.search;
      const scrollBefore = __t().scroll.scrollTop;
      __t().q(".table-back").click();
      await until(() => __t().q(".table-record").hidden);
      await frames();
      return {
        whilePressing,
        afterPause,
        row,
        opened,
        recordAddress,
        backAddress: location.search,
        gridShown: !__t().scroll.hidden && __t().q(".table-record").hidden,
        tabStop: __t().q("tbody tr[tabindex='0']")?.dataset.index ?? null,
        scrollTop: __t().scroll.scrollTop,
      };
    })()`);
    await chrome.evaluate("window.__beforeReload = true");
    await chrome.send("Page.reload", {});
    await chrome.waitFor(
      `(() => { try { ${VIEW}; return !window.__beforeReload && __t().qa("tbody tr:not(.table-spacer)").length >= 20; } catch { return false; } })()`,
    );
    await chrome.evaluate(VIEW);
    await sleep(500);
    measured.reload = await chrome.evaluate(`({
      scrollTop: __t().scroll.scrollTop,
      tabStop: __t().q("tbody tr[tabindex='0']")?.dataset.index ?? null,
    })`);
    phase("history");

    // Default columns too many for the pane hide from the right, with a note; columns the
    // reader chose all show, and the first stays in place as they scroll sideways.
    await open("wide.csv", 2);
    measured.fit = await chrome.evaluate(`({
      headers: __t().qa("thead th").length,
      note: __t().q(".table-fit-note").hidden ? null : __t().q(".table-fit-note").textContent,
      overflows: __t().scroll.scrollWidth > __t().scroll.clientWidth + 1,
    })`);
    // The toolbar keeps its box as the Live pill and the new-rows offer come and go: the
    // controls before them stay put, and once shown each keeps its slot while hidden.
    measured.toolbar = await chrome.evaluate(`(async () => {
      const frame = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const pill = __t().q(".table-live-pill");
      const offer = __t().q(".table-offer");
      const columns = __t().q(".table-columns-button");
      const note = __t().q(".table-fit-note");
      const bar = __t().q(".table-toolbar");
      const box = () => {
        const at = columns.getBoundingClientRect();
        const noteAt = note.getBoundingClientRect();
        return [at.left, at.top, noteAt.left, noteAt.top, bar.getBoundingClientRect().height].map(Math.round).join(",");
      };
      for (let tries = 0; tries < 100 && pill.hidden; tries += 1) {
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      const pillLive = !pill.hidden;
      const live = box();
      // The watch drops to waiting, as on a reconnect: the pill hides in its slot.
      pill.hidden = true;
      await frame();
      const waiting = box();
      pill.hidden = false;
      // Rows arrive above the reader's place, and the offer is taken.
      offer.textContent = "1,234 new rows";
      offer.dataset.slot = "";
      offer.hidden = false;
      await frame();
      const offered = box();
      offer.hidden = true;
      await frame();
      const taken = box();
      return { pillLive, live, waiting, offered, taken };
    })()`);
    await shot("4-fit");
    // `cols` names one field a parameter, repeated (docs/plugins.md, "Table Sources").
    const all = Array.from({ length: 24 }, (_, i) => `cols=column_name_${i + 1}`).join("&");
    await open(`wide.csv?${all}`, 2);
    measured.pinned = await chrome.evaluate(`(async () => {
      const scroll = __t().scroll;
      const first = __t().q("tbody tr:not(.table-spacer) > :first-child");
      const second = __t().q("tbody tr:not(.table-spacer) > :nth-child(2)");
      const before = { first: first.getBoundingClientRect().left, second: second.getBoundingClientRect().left };
      scroll.scrollLeft = 600;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      return {
        headers: __t().qa("thead th").length,
        note: __t().q(".table-fit-note").hidden ? null : __t().q(".table-fit-note").textContent,
        pinned: __t().q("table").classList.contains("table-pinned"),
        scrolledLeft: scroll.scrollLeft,
        firstStill: Math.abs(first.getBoundingClientRect().left - before.first) < 1,
        secondMoved: before.second - second.getBoundingClientRect().left,
      };
    })()`);
    await shot("5-pinned");
    phase("fit");

    // Standalone structured tables use the record grid for record lists and the node
    // table for other shapes.
    const tableTab = async (address) => {
      await chrome.send("Page.navigate", { url: `${base}/view/${address}` });
      await chrome.waitFor(
        `(() => { const pane = document.querySelector("#preview-pane"); const tab = pane?.querySelector('.tab-btn[data-tab="table"]'); if (pane?.dataset.renderedPath !== ${JSON.stringify(address)} || !tab) { return false; } tab.click(); return true; })()`,
      );
      await chrome.evaluate(VIEW);
    };
    const captureCopy = `Object.defineProperty(navigator, "clipboard", {
      value: { writeText: async (value) => { window.__rowCopy = value; } },
      configurable: true,
    })`;
    await tableTab("records.json");
    await chrome.waitFor(
      `(() => { try { ${VIEW}; return __t().qa("tbody tr:not(.table-spacer)").length >= 2; } catch { return false; } })()`,
    );
    await chrome.evaluate(VIEW);
    measured.records = await chrome.evaluate(`({
      tab: document.querySelector('#preview-pane .tab-btn.active')?.dataset.tab ?? null,
      headers: __t().qa("thead th").map((th) => th.textContent.replace("▾", "").trim()).filter(Boolean),
      rows: __t().qa("tbody tr:not(.table-spacer)").length,
    })`);
    await chrome.evaluate(captureCopy);
    await chrome.evaluate(`__t().q('button[aria-label="Copy record 1"]').click()`);
    await chrome.waitFor(`typeof window.__rowCopy === "string"`);
    measured.records.copy = await chrome.evaluate("window.__rowCopy");
    await chrome.evaluate(`__t().q(".table-position").click()`);
    await chrome.waitFor(
      `(() => { try { ${VIEW}; return __t().qa(".table-record-json .structured-tree").length >= 2; } catch { return false; } })()`,
    );
    measured.records.trees = await chrome.evaluate(
      `__t().qa(".table-record-json .structured-tree").map((tree) => tree.textContent.replace(/\\s+/g, " ").trim())`,
    );
    await shot("6-record");
    await chrome.send("Page.navigate", { url: `${base}/view/mapping.json` });
    await chrome.waitFor(
      `(() => { const pane = document.querySelector("#preview-pane"); return pane?.dataset.renderedPath === "mapping.json" && Boolean(pane.querySelector(".data-grid tbody tr")); })()`,
    );
    measured.mappingTabs = await chrome.evaluate(
      `[...document.querySelectorAll("#preview-pane .tab-btn")].map((tab) => tab.dataset.tab)`,
    );
    measured.mappingRow = await chrome.evaluate(
      `[...document.querySelectorAll("#preview-pane .data-grid tbody tr > :not(.structured-row-action)")].map((cell) => cell.textContent)`,
    );
    const mappingCopy = `document.querySelector('button[aria-label="Copy name"]')`;
    const copyPaint = (opacity, pointerEvents) =>
      `getComputedStyle(${mappingCopy}).opacity === "${opacity}" && getComputedStyle(${mappingCopy}).pointerEvents === "${pointerEvents}"`;
    await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 2, y: 2 });
    await chrome.waitFor(copyPaint(0, "none"));
    const mappingPoint = await chrome.evaluate(`(() => {
      const row = ${mappingCopy}.closest("tr").getBoundingClientRect();
      return { x: row.left + 10, y: row.top + row.height / 2 };
    })()`);
    await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", ...mappingPoint });
    await chrome.waitFor(copyPaint(1, "auto"));
    await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 2, y: 2 });
    await chrome.waitFor(copyPaint(0, "none"));
    await chrome.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Tab", code: "Tab" });
    await chrome.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Tab", code: "Tab" });
    await chrome.evaluate(`${mappingCopy}.focus()`);
    await chrome.waitFor(copyPaint(1, "auto"));
    await chrome.evaluate(captureCopy);
    await chrome.evaluate(`${mappingCopy}.click()`);
    await chrome.waitFor(`typeof window.__rowCopy === "string"`);
    measured.mappingCopy = await chrome.evaluate("window.__rowCopy");
    await tableTab("mixed.json");
    const mixedGrid = 'document.querySelector("#preview-pane .data-grid")';
    await chrome.waitFor(`${mixedGrid}?.tBodies[0].rows.length === 3`);
    measured.mixed = await chrome.evaluate(
      `[...${mixedGrid}.tBodies[0].rows].map((row) => [...row.cells].filter(
        (cell) => !cell.classList.contains("structured-row-action"),
      ).map(
        (cell) => (cell.querySelector(":scope > button") ?? cell).textContent,
      ))`,
    );
    measured.branchLayout = await chrome.evaluate(`(() => {
      const rows = ${mixedGrid}.tBodies[0].rows;
      const first = rows[0];
      const button = first.querySelector(".structured-branch-toggle");
      const icon = button.querySelector(".toggle-chevron").getBoundingClientRect();
      const box = button.getBoundingClientRect();
      const label = document.createRange();
      label.selectNodeContents(button.firstChild);
      return {
        usesTableTextSize: getComputedStyle(button).fontSize === getComputedStyle(button.closest("td")).fontSize,
        iconAfterLabel: label.getBoundingClientRect().right <= icon.left,
        iconCentered: Math.abs((icon.top + icon.bottom - box.top - box.bottom) / 2) <= 1,
        rowHeightMatches: Math.abs(first.getBoundingClientRect().height - rows[2].getBoundingClientRect().height) <= 1,
      };
    })()`);
    await chrome.send("Emulation.setDeviceMetricsOverride", {
      width: 720,
      height: 840,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await chrome.send("Page.navigate", { url: `${base}/view/frontmatter.md` });
    const frontmatter = "details.kpress-frontmatter";
    await chrome.waitFor(`Boolean(document.querySelector("${frontmatter} > summary"))`);
    await chrome.evaluate(`document.querySelector("${frontmatter} > summary").click()`);
    const frontGrid = `document.querySelector("${frontmatter} .data-grid")`;
    const rowNamed = (name) =>
      `[...document.querySelectorAll("${frontmatter} .data-grid tbody tr")].find(
        (candidate) => candidate.querySelector("th")?.textContent === ${JSON.stringify(name)}
      )`;
    await chrome.waitFor(`Boolean((${rowNamed("slot")})?.querySelector(".disclosure-toggle"))`);
    measured.initialFrontmatter = await chrome.evaluate(`({
      keys: [...${frontGrid}.tBodies[0].rows].map((row) => row.cells[0].textContent),
      pickers: document.querySelectorAll("${frontmatter} select").length,
      slotOpen: (${rowNamed("slot")}).querySelector(".disclosure-toggle").getAttribute("aria-expanded"),
    })`);
    await chrome.evaluate(captureCopy);
    await chrome.evaluate(`(${rowNamed("slot")}).lastElementChild.querySelector("button").click()`);
    await chrome.waitFor(`typeof window.__rowCopy === "string"`);
    measured.branchCopy = await chrome.evaluate("window.__rowCopy");
    await chrome.evaluate(
      `window.__frontGrid = ${frontGrid}; window.__titleRow = ${rowNamed("title")}`,
    );
    for (const name of ["slot", "roles"]) {
      const row = rowNamed(name);
      await chrome.waitFor(
        `(${row})?.querySelector(".disclosure-toggle")?.getAttribute("aria-expanded") === "false"`,
      );
      await chrome.evaluate(`(${row}).querySelector(".disclosure-toggle").click()`);
    }
    await chrome.waitFor(
      `[...document.querySelectorAll("${frontmatter} .data-grid tbody td")].some((cell) => cell.textContent === '"host"')`,
    );
    measured.inlineExpansion = await chrome.evaluate(
      `window.__frontGrid === ${frontGrid} && window.__titleRow === ${rowNamed("title")}`,
    );
    measured.frontmatterFits = await chrome.evaluate(
      `${frontGrid}.getBoundingClientRect().right <= document.querySelector("${frontmatter}").getBoundingClientRect().right`,
    );
    await chrome.evaluate(
      `[...document.querySelectorAll("${frontmatter} button")].find((button) => button.textContent === "Source").click()`,
    );
    await chrome.waitFor(
      `Boolean(document.querySelector("${frontmatter} [data-mb-copy-payload]"))`,
    );
    measured.frontmatter = await chrome.evaluate(`(() => {
      const details = document.querySelector("${frontmatter}");
      return {
        firstLine: Number(details.querySelector(".source-line-numbers").textContent.split(String.fromCharCode(10))[0]),
        copy: details.querySelector("[data-mb-copy-payload]").textContent,
      };
    })()`);
    await chrome.send("Emulation.clearDeviceMetricsOverride");
    const fences = `document.querySelectorAll("details.metabrowser-structured-fence")`;
    const yamlFence = `${fences}[0]`;
    const jsonFence = `${fences}[1]`;
    await chrome.waitFor(`${fences}.length === 2`);
    await chrome.evaluate(`${yamlFence}.querySelector("summary").click()`);
    await chrome.evaluate(`${jsonFence}.querySelector("summary").click()`);
    await chrome.waitFor(
      `Boolean(${yamlFence}.querySelector(".structured-node-grid") && ${jsonFence}.querySelector(".structured-node-grid"))`,
    );
    await chrome.evaluate(`${yamlFence}.querySelector('[data-chip-value="Source"]').click()`);
    const hasSourceColor = (fence, language) => `(() => {
      const token = ${fence}.querySelector(".language-${language}.hljs .hljs-attr");
      return token && getComputedStyle(token).color !== getComputedStyle(token.closest("code")).color;
    })()`;
    await chrome.waitFor(hasSourceColor(yamlFence, "yaml"));
    await chrome.evaluate(`${yamlFence}.querySelector('[data-chip-value="Table"]').click()`);
    await chrome.evaluate(`${jsonFence}.querySelector('[data-chip-value="Tree"]').click()`);
    await chrome.waitFor(`Boolean(${jsonFence}.querySelector(".structured-tree"))`);
    await chrome.evaluate(`${jsonFence}.querySelector('[data-chip-value="Source"]').click()`);
    await chrome.waitFor(`Boolean(${jsonFence}.querySelector("[data-mb-copy-payload]"))`);
    await chrome.waitFor(hasSourceColor(jsonFence, "json"));
    measured.fencedViews = await chrome.evaluate(`(() => {
      const json = ${jsonFence};
      const firstLine = Number(json.querySelector(".source-line-numbers").textContent.split(String.fromCharCode(10))[0]);
      const source = json.querySelector("[data-mb-copy-payload]").textContent;
      json.querySelector("summary").click();
      return { firstLine, source, yamlTableStaysOpen: ${yamlFence}.open && Boolean(${yamlFence}.querySelector(".structured-node-grid")) };
    })()`);
    await chrome.waitFor(`!${jsonFence}.nextElementSibling.hidden`);
    measured.fencedViews.jsonFallbackReturns = true;
    phase("records");
    const hasCell = (text) =>
      `__t().qa(".table-cell").some((cell) => cell.textContent === ${JSON.stringify(text)})`;
    const waitForCell = (text) => chrome.waitFor(hasCell(text));
    const initialise = (db, text) => {
      db.exec("CREATE TABLE events (id INTEGER PRIMARY KEY, note TEXT NOT NULL)");
      db.prepare("INSERT INTO events VALUES (?, ?)").run(1, text);
    };
    const livePath = path.join(root, "active.sqlite");
    const writer = new DatabaseSync(livePath);
    try {
      writer.exec("PRAGMA journal_mode=WAL; PRAGMA wal_autocheckpoint=0");
      initialise(writer, "first WAL entry");
      await open("active.sqlite/events", 1);
      await waitForCell("first WAL entry");
      const checkpoint = fs.readFileSync(livePath);
      const walBytes = fs.statSync(`${livePath}-wal`).size;
      writer.prepare("INSERT INTO events VALUES (?, ?)").run(2, "WAL-only update");
      assert.ok(fs.statSync(`${livePath}-wal`).size > walBytes);
      assert.deepEqual(fs.readFileSync(livePath), checkpoint);
      await waitForCell("WAL-only update");
    } finally {
      writer.close();
    }

    const ordinaryPath = path.join(root, "ordinary.sqlite");
    const build = (file, text) => {
      const db = new DatabaseSync(file);
      try {
        initialise(db, text);
      } finally {
        db.close();
      }
    };
    build(ordinaryPath, "ordinary original");
    await open("ordinary.sqlite/events", 1);
    await waitForCell("ordinary original");
    const replacement = path.join(state, "replacement.sqlite");
    build(replacement, "ordinary replacement");
    fs.renameSync(replacement, ordinaryPath);
    await waitForCell("ordinary replacement");
    measured.sqliteRefresh = true;
    phase("sqlite-refresh");

    const searchDb = new DatabaseSync(path.join(root, "search.sqlite"));
    try {
      searchDb.exec(
        "CREATE TABLE notes (id INTEGER PRIMARY KEY, text TEXT); " +
          "WITH RECURSIVE n(i) AS (VALUES(1) UNION ALL SELECT i+1 FROM n WHERE i<16400) " +
          "INSERT INTO notes SELECT i, CASE WHEN i=16400 THEN 'last needle' ELSE 'other' END FROM n",
      );
    } finally {
      searchDb.close();
    }
    await open("search.sqlite/notes?q=needle", 0);
    const resume = `__t().q(".table-continue")`;
    const examined = `Number(__t().q(".table-empty")?.textContent.match(/first (.+?) rows\\./)?.[1]?.replace(/\\D/g, "") ?? 0)`;
    await chrome.waitFor(`${resume}?.textContent === "Continue search" && ${examined} > 0`);
    const first = await chrome.evaluate(examined);
    await chrome.evaluate(`${resume}.click()`);
    // The first click ends before the match. A time budget can shorten any scan window.
    await chrome.waitFor(`${examined} > ${first}`);
    const found = hasCell("last needle");
    for (let step = 0; step < 6 && !(await chrome.evaluate(found)); step++) {
      await chrome.waitFor(`${resume}?.disabled === false`);
      const previous = await chrome.evaluate(examined);
      await chrome.evaluate(`${resume}.click()`);
      await chrome.waitFor(`${found} || ${examined} > ${previous}`);
    }
    await waitForCell("last needle");
    measured.sqliteSearch = await chrome.evaluate(`!__t().q(".table-continue")`);
    phase("sqlite-search");
    measured.exceptions = problems;
  } finally {
    if (chrome) {
      await chrome.close();
    }
    await server.stop();
  }
  process.stdout.write(`${JSON.stringify(measured)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack ?? error}\n`);
  process.exit(1);
});
