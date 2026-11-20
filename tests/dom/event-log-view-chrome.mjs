// Metabrowser's own event log, browsed in Metabrowser, laid out by a real engine: a served
// folder holding a log segment, the shell's own page, and headless Chrome.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/event-log-view-chrome.mjs METAB ROOT FILE PORT STATE_DIR [SHOTS_DIR]
//
// tests/test_event_log_view_chrome.py writes the folder, owns the profile and STATE_DIR,
// runs this in a process group of its own, which Chrome and the server join, and judges
// what it prints: one JSON line of measurements. With SHOTS_DIR it also saves a screenshot
// of each view, in the page's own theme.
//
// What it measures is what no browserless DOM computes: that the four views and Raw JSON
// are the file's tabs, in order, with the keys the manifest declares; that a row is one
// height and its bar sits where the log's time axis puts it; that an outcome is drawn in
// the shell's own status inks and a failure in a different one from success; that a
// nested row is indented by its depth; that Enter on a focused row opens it and the focus
// ring is drawn; that the distribution's tallest column is the full height and the others
// in proportion; that nothing overflows the pane at the default width and at a phone's,
// where the bar and offset give way; that the filter bar's every chip is inside the pane
// at that width; that the keyboard stays on a row that Enter opens; that Show in timeline
// in Errors opens the Timeline, opens the spans above the row, and focuses it; and that the
// keys V, L, B, and E switch views. The session's own state, the requests, and the filters
// run browserlessly in tests/dom/event-log-view-session.js.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, file, port, state, shots] = process.argv.slice(2);
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

// In the page: what each check reads.
const TABS = `[...document.querySelectorAll(".tab-bar:not(.nav-tab-bar) .tab-btn")].map((tab) => ({
  text: tab.textContent.trim(),
  selected: tab.getAttribute("aria-selected") === "true" || tab.classList.contains("active"),
}))`;

const TIMELINE = `(() => {
  const pane = __v().body;
  const rows = [...pane.querySelectorAll(".event-log-row")];
  const head = (row) => row.querySelector(".event-log-row-head");
  const box = (element) => element.getBoundingClientRect();
  const round = (value) => Math.round(value * 100) / 100;
  const byKey = (key) => pane.querySelector('[data-key="' + key + '"]');
  const tone = (name) =>
    getComputedStyle(pane.querySelector('[data-tone="' + name + '"] .event-log-outcome')).color;
  const probe = document.createElement("span");
  document.body.append(probe);
  /** The computed color of a token, as the engine resolves it. */
  const token = (name) => {
    probe.style.color = "var(" + name + ")";
    return getComputedStyle(probe).color;
  };
  const tokens = {
    success: token("--status-success-text"),
    error: token("--status-error-text"),
    warning: token("--status-warning-text"),
    muted: token("--muted"),
  };
  probe.remove();
  const slow = byKey("7007:3");
  const track = slow.querySelector(".event-log-bar");
  const fill = slow.querySelector(".event-log-bar-fill");
  const trackBox = box(track);
  const fillBox = box(fill);
  const pageBox = box(__v().body);
  return {
    rows: rows.length,
    headHeights: [...new Set(rows.map((row) => round(box(head(row)).height)))],
    rowHeightToken: getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height").trim(),
    outcomeInks: { ok: tone("ok"), failed: tone("failed"), quiet: tone("quiet") },
    tokens,
    barLeftShare: round((fillBox.left - trackBox.left) / trackBox.width),
    barWidthShare: round(fillBox.width / trackBox.width),
    hairline: round(box(byKey("7007:1").querySelector(".event-log-bar-fill")).width),
    noOverflow: __v().body.scrollWidth <= pageBox.width + 1,
    chipsDrawn: __v().qa(".event-log-filters .chip").length,
    noticeSeverity: __v().q(".event-log-head .notice")?.getAttribute("data-severity") ?? null,
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
    const press = async (key, code = key) => {
      for (const type of ["keyDown", "keyUp"]) {
        await chrome.send("Input.dispatchKeyEvent", {
          type,
          key,
          code,
          text:
            type === "keyDown"
              ? key === "Enter"
                ? "\r"
                : key.length === 1
                  ? key
                  : undefined
              : undefined,
          windowsVirtualKeyCode: key === "Enter" ? 13 : key.toUpperCase().charCodeAt(0),
        });
      }
    };
    const rowsDrawn = (min) => `__v().qa(".event-log-row").length >= ${min}`;
    // The page's own theme follows the browser's: `EVENT_LOG_VIEW_SCHEME=light` shoots it light.
    if (process.env.EVENT_LOG_VIEW_SCHEME) {
      await chrome.send("Emulation.setEmulatedMedia", {
        features: [{ name: "prefers-color-scheme", value: process.env.EVENT_LOG_VIEW_SCHEME }],
      });
    }
    await chrome.send("Page.navigate", { url: `${base}/view/${file}` });
    await chrome.evaluate(`window.__v = () => {
      const body = [...document.querySelectorAll(".event-log-body")].find(
        (candidate) => candidate.getClientRects().length > 0,
      );
      const root = body?.closest(".content-body") ?? document;
      return {
        body,
        q: (selector) => root.querySelector(selector),
        qa: (selector) => [...root.querySelectorAll(selector)],
      };
    }`);
    await chrome.waitFor(rowsDrawn(40));
    phase("timeline");

    measured.tabs = await chrome.evaluate(TABS);
    measured.timeline = await chrome.evaluate(TIMELINE);
    await shot("1-timeline");

    // A row opens to what is below it, and is indented by its depth.
    await chrome.evaluate(`__v().q('[data-key="7007:22"] .event-log-row-head').click()`);
    await chrome.waitFor(`__v().q('[data-key="7007:23"]') !== null`);
    await chrome.evaluate(`__v().q('[data-key="7007:23"] .event-log-row-head').click()`);
    await chrome.waitFor(`__v().q('[data-key="7007:24"]') !== null`);
    measured.nesting = await chrome.evaluate(`(() => {
      const left = (key) => __v().q('[data-key="' + key + '"] .event-log-row-head').getBoundingClientRect().left;
      const indent = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--event-log-indent"));
      const nameLeft = (key) => __v().q('[data-key="' + key + '"] .event-log-name').getBoundingClientRect().left;
      return {
        indentToken: indent,
        jobFromRequest: Math.round((left("7007:23") - left("7007:22")) * 100) / 100,
        processFromJob: Math.round((left("7007:24") - left("7007:23")) * 100) / 100,
        nameStepsRight: nameLeft("7007:24") > nameLeft("7007:23") && nameLeft("7007:23") > nameLeft("7007:22"),
        expanded: ["7007:22", "7007:23"].map((key) =>
          __v().q('[data-key="' + key + '"] .event-log-row-head').getAttribute("aria-expanded")),
        detailShown: __v().q('[data-key="7007:22"] .event-log-detail') !== null,
        chevronTurned: getComputedStyle(__v().q('[data-key="7007:22"] .event-log-chevron')).transform !== "none",
      };
    })()`);
    await chrome.evaluate(`__v().q('[data-key="7007:22"]').scrollIntoView({block: "start"})`);
    await sleep(150);
    await shot("2-timeline-open");

    // A row a key reaches: focus drawn, Enter toggles.
    measured.keyboard = await (async () => {
      await press("Shift");
      await chrome.evaluate(`__v().q('[data-key="7007:1"] .event-log-row-head').focus()`);
      const focused = await chrome.evaluate(`(() => {
        const head = document.activeElement;
        const style = getComputedStyle(head);
        return {
          onRow: head.classList.contains("event-log-row-head"),
          outlineStyle: style.outlineStyle,
          outlineWidth: style.outlineWidth,
          expanded: head.getAttribute("aria-expanded"),
        };
      })()`);
      await press("Enter");
      await sleep(100);
      const after = await chrome.evaluate(
        `__v().q('[data-key="7007:1"] .event-log-row-head').getAttribute("aria-expanded")`,
      );
      // The row was drawn again as a new node; the keyboard is on that node's header.
      const kept = await chrome.evaluate(
        `document.activeElement === __v().q('[data-key="7007:1"] .event-log-row-head')`,
      );
      return { ...focused, afterEnter: after, keptFocus: kept };
    })();

    // A phone's width: the bar and the offset give way, and nothing overflows.
    measured.narrow = {};
    await chrome.send("Emulation.setDeviceMetricsOverride", {
      width: 560,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await sleep(300);
    measured.narrow = await chrome.evaluate(`(() => {
      const body = __v().body;
      const row = __v().q('[data-key="7007:2"]');
      const bar = __v().q(".event-log-filters");
      const barBox = bar.getBoundingClientRect();
      const chips = [...bar.querySelectorAll(".chip")];
      return {
        barShown: getComputedStyle(row.querySelector(".event-log-bar")).display !== "none",
        whenShown: getComputedStyle(row.querySelector(".event-log-when")).display !== "none",
        noOverflow: body.scrollWidth <= body.getBoundingClientRect().width + 1,
        nameShown: row.querySelector(".event-log-name").getBoundingClientRect().width > 40,
        // Every choice of the bar is inside the pane, the last "at least" among them:
        // a group that clipped at its edge left the slowest choices out of reach.
        filterBar: {
          chips: chips.length,
          everyChipInside: chips.every((chip) => {
            const box = chip.getBoundingClientRect();
            return box.left >= barBox.left - 1 && box.right <= barBox.right + 1;
          }),
          noOverflow: bar.scrollWidth <= bar.clientWidth + 1,
          lastLeastChip: [...bar.querySelectorAll('.chip[data-chip-key="event-log-minimum"]')]
            .at(-1)
            .getBoundingClientRect().right <= barBox.right + 1,
          width: Math.round(barBox.width),
        },
      };
    })()`);
    await shot("3-timeline-narrow");
    await chrome.send("Emulation.clearDeviceMetricsOverride");
    await sleep(200);

    // The keys the manifest declares switch the views.
    measured.keys = {};
    for (const [key, view, ready] of [
      ["l", "latency", `__v().q(".event-log-histogram") !== null`],
      ["b", "kinds", `__v().q(".event-log-table") !== null`],
      ["e", "errors", `__v().q(".event-log-cause") !== null`],
      ["v", "timeline", `__v().qa(".event-log-row").length > 20`],
    ]) {
      await chrome.evaluate(`document.activeElement?.blur()`);
      await press(key);
      await chrome.waitFor(ready);
      measured.keys[view] = await chrome.evaluate(
        `(${TABS}).find((tab) => tab.selected)?.text ?? null`,
      );
      if (view === "latency") {
        await sleep(150);
        measured.latency = await chrome.evaluate(`(() => {
          const columns = [...__v().qa(".event-log-hist-column")];
          const height = (column) => column.querySelector(".event-log-hist-bar").getBoundingClientRect().height;
          const counts = columns.map((column) => Number(column.querySelector(".event-log-hist-count").textContent));
          const tallest = Math.max(...columns.map(height));
          return {
            columns: columns.length,
            counts,
            tallestPx: Math.round(tallest * 100) / 100,
            // Each column's bar is its count's share of the largest, to the pixel.
            shares: columns.map((column, index) => Math.round((height(column) / tallest) * 100) / 100),
            expectedShares: counts.map((count) => Math.round((count / Math.max(...counts)) * 100) / 100),
            rows: __v().qa(".event-log-row").length,
            barsInFirstRows: [...__v().qa(".event-log-row")].slice(0, 3).map((row) =>
              Math.round(row.querySelector(".event-log-bar-fill").getBoundingClientRect().width / row.querySelector(".event-log-bar").getBoundingClientRect().width * 100) / 100),
            noOverflow: __v().body.scrollWidth <= __v().q(".event-log-body").getBoundingClientRect().width + 1,
          };
        })()`);
        await shot("4-latency");
      } else if (view === "kinds") {
        measured.kinds = await chrome.evaluate(`(() => {
          const body = __v().body;
          const tables = [...__v().qa(".event-log-table")];
          return {
            sections: __v().qa(".event-log-kind-section").length,
            tablesFit: tables.every((table) => table.getBoundingClientRect().right <= body.getBoundingClientRect().right + 1),
            numbersAlignRight: getComputedStyle(tables[0].querySelector("td:nth-child(2)")).textAlign === "end" ||
              getComputedStyle(tables[0].querySelector("td:nth-child(2)")).textAlign === "right",
          };
        })()`);
        await shot("5-kinds");
      } else if (view === "errors") {
        measured.errors = await chrome.evaluate(`(() => {
          const cause = __v().q(".event-log-cause-name");
          const probe = document.createElement("span");
          document.body.append(probe);
          probe.style.color = "var(--status-error-text)";
          const error = getComputedStyle(probe).color;
          probe.remove();
          return {
            causes: __v().qa(".event-log-cause").length,
            causeInk: getComputedStyle(cause).color,
            errorInk: error,
            headings: __v().qa(".section-heading").map((h) => h.textContent.trim()),
            filterBar: __v().q(".event-log-filters") !== null,
          };
        })()`);
        await shot("6-errors");
      }
    }

    // Show in timeline: from an example in Errors to its row in the Timeline, which opens
    // each span above it, scrolls to it, and puts the keyboard on it. The spans are shut
    // first, so the row is reached only by opening them.
    await chrome.evaluate(`__v().q('[data-key="7007:22"] .event-log-row-head').click()`);
    await chrome.waitFor(`__v().q('[data-key="7007:23"]') === null`);
    await chrome.evaluate(`document.activeElement?.blur()`);
    await press("e");
    await chrome.waitFor(`__v().q(".event-log-cause") !== null`);
    await chrome.evaluate(`__v().q(".event-log-examples .event-log-show").click()`);
    try {
      await chrome.waitFor(
        `document.activeElement?.closest?.("[data-key]")?.getAttribute("data-key") === "7007:25"`,
        8000,
      );
    } catch (error) {
      const seen = await chrome.evaluate(
        `JSON.stringify({tab: (${TABS}).find((tab) => tab.selected)?.text, active: document.activeElement?.outerHTML.slice(0, 160), rows: __v().qa(".event-log-row").length, note: __v().q(".event-log-reveal-note")?.textContent, open: [...__v().qa('.event-log-row-head[aria-expanded="true"]')].map((h) => h.parentNode.getAttribute("data-key"))})`,
      );
      throw new Error(`${error.message}; the page: ${seen}`);
    }
    await sleep(150);
    measured.shown = await chrome.evaluate(`(() => {
      const row = document.activeElement.closest(".event-log-row");
      const box = row.getBoundingClientRect();
      const open = (key) =>
        __v().q('[data-key="' + key + '"] .event-log-row-head').getAttribute("aria-expanded");
      return {
        tab: (${TABS}).find((tab) => tab.selected)?.text ?? null,
        focusedKey: row.getAttribute("data-key"),
        revealed: row.hasAttribute("data-revealed"),
        ancestorsOpen: [open("7007:22"), open("7007:23")],
        inView: box.top >= 0 && box.bottom <= window.innerHeight,
        tint: getComputedStyle(row).backgroundColor,
        plain: getComputedStyle(__v().q('[data-key="7007:23"]')).backgroundColor,
      };
    })()`);
    await shot("8-shown-in-timeline");

    // A filter a chip chooses narrows the timeline to the jobs, with the requests that
    // started them as context.
    await chrome.evaluate(
      `__v().q('.event-log-filters .chip[data-chip-key="event-log-kind"][data-chip-value="job"]').click()`,
    );
    try {
      await chrome.waitFor(
        `__v().qa(".event-log-row").length > 0 && __v().qa(".event-log-row").length < 10`,
        8000,
      );
    } catch (error) {
      const seen = await chrome.evaluate(
        `JSON.stringify({rows: __v().qa(".event-log-row").length, chips: [...__v().qa('.event-log-filters .chip[aria-pressed="true"]')].map((c) => c.textContent), body: __v().body?.textContent.slice(0, 160), tab: [...document.querySelectorAll(".tab-bar:not(.nav-tab-bar) .tab-btn.active")].map((t) => t.textContent)})`,
      );
      throw new Error(`${error.message}; the page: ${seen}`);
    }
    measured.filtered = await chrome.evaluate(`(() => {
      const rows = [...__v().qa(".event-log-row")];
      return {
        rows: rows.length,
        pressed: __v().q('.event-log-filters .chip[data-chip-value="job"]').getAttribute("aria-pressed"),
        context: rows.filter((row) => row.hasAttribute("data-context")).length,
        contextInk: getComputedStyle(rows[0].querySelector(".event-log-name")).color,
        matchedInk: null,
      };
    })()`);
    await shot("7-filtered");

    // Raw JSON is the JSONL renderer's.
    const rawPane = `[...document.querySelectorAll(".content-body")].find(
      (pane) => pane.getClientRects().length > 0 && pane.querySelector(".event-log-body") === null,
    )`;
    await chrome.evaluate(
      `[...document.querySelectorAll(".tab-bar:not(.nav-tab-bar) .tab-btn")].find((tab) => tab.textContent.trim().startsWith("Raw"))?.click()`,
    );
    await chrome.waitFor(`(${rawPane})?.textContent.includes("server.start") === true`);
    measured.raw = true;
    measured.exceptions = problems;
    phase("done");
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
