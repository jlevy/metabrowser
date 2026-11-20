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
// rows it printed; and the browser's own history: that a run of key presses past Chrome's
// bound on history calls (200 in 10 seconds) still lets Enter push the record's address,
// whose Back link returns to the grid where the keys left it, and that a reload returns
// there too. Which rows, columns, and cells exist, what a key does, and what the address
// holds run browserlessly in tests/dom/table-view-session.js.

// Key presses in a run: past the 200 history calls Chrome allows in 10 seconds.
const PRESSES = 260;

import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
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
    await chrome.send("Emulation.setEmulatedMedia", { media: "" });

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
    await shot("4-fit");
    // `cols` names one field a parameter.
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
