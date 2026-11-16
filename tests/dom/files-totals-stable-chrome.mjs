// The Files nav panel from first paint to settled, laid out by headless Chrome against two
// live `metab` servers: a folder with ignored files and one with none.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/files-totals-stable-chrome.mjs METAB IGNORING_ROOT CLEAN_ROOT PORT STATE_DIR
//
// tests/test_files_totals_stable_chrome.py writes both folders, owns the profile and
// STATE_DIR, runs this in a process group of its own, which Chrome and both servers join,
// and judges what it prints: one JSON line of measurements.
//
// The Files totals line's ignored count, "+ 7,898 ignored (132.5 MB)", arrived with the
// server's pass over every file, half a second to seconds after the tree, and in the
// default pane it took a second line and moved the tree down 19.5 px (mb-h3hc). What is
// promised is layout, which only a browser computes: from the frame the panel first shows
// rows to the frame it settles, no box in the navigation (the filter bar, each metadata
// line, the first rows) moves or changes size, and Chrome records no layout shift without
// input after that frame. Each load is recorded from the document's start, frame by
// frame, in both themes; with the server's tally answered at once and held 2 s ("slow");
// in the default pane and the narrowest; for the folder with ignored files and for the
// one with none.
//
// Five loads take the shell as a server drawn before the walk finished the root would
// send it, its inlined totals taken out ("unknown"): with ignored files the line holds the
// ignored line from first paint and the count fills it, in the narrowest pane too, where
// the count is cut short on its one line rather than wrapped; with none, the held line is taken
// away once the root's totals say so, which is the one move the design keeps
// (docs/design-system.md, "Navigation Metadata Line"), and this measures it.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import { spawn } from "node:child_process";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, ignoringRoot, cleanRoot, port, state] = process.argv.slice(2);
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
// How long the server's tally is held in a slow load: past the shell's quiet period and
// the refresh's debounce, as a pass over a large tree takes.
const SLOW_MS = 2000;
// Frames the panel must hold still after the tally has answered before it is settled.
const QUIET_MS = 700;
// One load's bound: a cold page, the held tally, and the quiet frames, on a loaded machine.
const LOAD_MS = 30000;
// The default pane (`--tree-pane-width`) and the narrowest the resize handle allows.
const WIDTHS = [300, 180];

/** Start one server, resolving with its base URL once it says it is serving. */
async function serve(root, at, dir) {
  const base = `http://127.0.0.1:${at}`;
  const server = spawn(
    metab,
    [
      root,
      "--no-open",
      "--port",
      String(at),
      "--cache-dir",
      path.join(dir, "cache"),
      "--config-dir",
      path.join(dir, "config"),
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
    base,
    async stop() {
      server.kill("SIGTERM");
      await Promise.race([exited, sleep(20000)]);
    },
  };
}

// From the document's start: every frame's navigation boxes, kept when they change, and
// every layout shift.
const PROBE = `(() => {
  window.__frames = [];
  window.__shifts = [];
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (!entry.hadRecentInput) {
        const sources = (entry.sources || []).map((source) => source.node && source.node.nodeType === 1 ? source.node.tagName.toLowerCase() + (source.node.id ? "#" + source.node.id : "") + "." + String(source.node.className).trim().split(/\\s+/).join(".") : String(source.node && source.node.nodeName));
        window.__shifts.push({ at: Math.round(entry.startTime), value: entry.value, sources });
      }
    }
  }).observe({ type: "layout-shift", buffered: true });
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return [Math.round(r.top * 10) / 10, Math.round(r.height * 10) / 10];
  };
  let last = "";
  const sample = () => {
    const panel = document.getElementById("tab-files");
    const rows = panel ? [...panel.querySelectorAll(".tree-item")].slice(0, 12) : [];
    // First paint is the first frame with rows under a filled filter bar. In a pane too
    // narrow for it the bar, which the shell ships one line tall, wraps to two as
    // filter-controls.js fills it, the toolbar exemption of docs/design-system.md,
    // "Regions Keep Their Boxes" (H52 would server-render it): measured at 180 px, the
    // rows sometimes painted a frame before the bar filled and then moved 30 px with it.
    const filled = document.querySelectorAll("#nav-filter-bar .chip").length > 0;
    if (panel && rows.length > 0 && filled) {
      const boxes = { bar: box(document.getElementById("nav-filter-bar")) };
      panel.querySelectorAll(".nav-metadata").forEach((line, i) => { boxes["line " + i] = box(line); });
      rows.forEach((row, i) => { boxes["row " + i] = box(row); });
      const summary = panel.querySelector(".tree-summary");
      const frame = {
        at: Math.round(performance.now()),
        boxes,
        reads: summary ? summary.textContent.replace(/\\s+/g, " ").trim() : null,
        ignoredLine: panel.querySelector(".tree-summary-ignored") ? "counted" : panel.querySelector(".tree-summary-ignored-pending") ? "held" : "none",
      };
      const key = JSON.stringify([frame.boxes, frame.reads, frame.ignoredLine]);
      if (key !== last) {
        last = key;
        window.__frames.push(frame);
      }
    }
    requestAnimationFrame(sample);
  };
  requestAnimationFrame(sample);
})();`;

// Half a frame at 60 Hz: a shift Chrome reports within it of the first frame with rows
// belongs to that frame, whose rAF time is a moment before its layout.
const FRAME_MS = 8;
/** @param {{value: number}[]} shifts */
const sumShifts = (shifts) =>
  Math.round(shifts.reduce((sum, shift) => sum + shift.value, 0) * 100000) / 100000;

/** How far each box moved or changed size across *frames*, in px. */
function movement(frames) {
  const keys = new Set(frames.flatMap((frame) => Object.keys(frame.boxes)));
  const moved = {};
  for (const key of keys) {
    const seen = frames.map((frame) => frame.boxes[key]).filter(Boolean);
    const spread = (i) => Math.max(...seen.map((b) => b[i])) - Math.min(...seen.map((b) => b[i]));
    // A box that appears or goes away after first paint moved the boxes under it, which
    // those boxes record; its own absence is not a movement.
    moved[key] = Math.round(Math.max(spread(0), spread(1)) * 10) / 10;
  }
  return moved;
}

async function main() {
  const ignoring = await serve(ignoringRoot, Number(port), path.join(state, "ignoring"));
  const clean = await serve(cleanRoot, Number(port) + 1, path.join(state, "clean"));
  phase("servers");
  const browser = await launchChrome(process.env.CHROME_BIN, {
    profiles: process.env.CHROME_PROFILES,
    width: 1280,
    height: 900,
  });
  const results = [];
  try {
    phase("chrome");
    await browser.send("Page.enable");
    await browser.send("Network.enable");
    await browser.send("Network.setCacheDisabled", { cacheDisabled: true });
    await browser.send("Page.addScriptToEvaluateOnNewDocument", { source: PROBE });
    let holdMs = 0;
    let answered = 0;
    browser.on("Network.responseReceived", (params) => {
      if (/\/api\/tree\?depth=0(&|$)/.test(params.response.url)) {
        answered += 1;
      }
    });
    browser.on("Fetch.requestPaused", async (params) => {
      try {
        if (params.responseStatusCode !== undefined) {
          // The shell, as a server drawing it before the walk finished the root sends it.
          const body = await browser.send("Fetch.getResponseBody", {
            requestId: params.requestId,
          });
          const html = (
            body.base64Encoded ? Buffer.from(body.body, "base64").toString("utf8") : body.body
          ).replace(
            /(window\.METABROWSER_INITIAL_TREE=\{.*?), "summary": \{[^}]*\}/,
            (_, before) => before,
          );
          await browser.send("Fetch.fulfillRequest", {
            requestId: params.requestId,
            responseCode: params.responseStatusCode,
            responseHeaders: params.responseHeaders.filter(
              (header) => !/^content-(length|encoding)$/i.test(header.name),
            ),
            body: Buffer.from(html, "utf8").toString("base64"),
          });
          return;
        }
        const tally = /\/api\/tree\?depth=0(&|$)/.test(params.request.url);
        await sleep(tally ? holdMs : 0);
        await browser.send("Fetch.continueRequest", { requestId: params.requestId });
      } catch {
        // A request the page abandoned while it was held is gone already.
      }
    });
    let widthScript = null;
    const load = async ({ server, name, theme, width, slow, strip }) => {
      holdMs = slow ? SLOW_MS : 0;
      answered = 0;
      await browser.send("Emulation.setEmulatedMedia", {
        features: [{ name: "prefers-color-scheme", value: theme }],
      });
      if (widthScript) {
        await browser.send("Page.removeScriptToEvaluateOnNewDocument", {
          identifier: widthScript,
        });
      }
      widthScript = (
        await browser.send("Page.addScriptToEvaluateOnNewDocument", {
          source: `(() => {
            const set = () => document.documentElement.style.setProperty("--tree-pane-width", "${width}px");
            if (document.documentElement) set();
            else new MutationObserver((_, o) => { if (document.documentElement) { set(); o.disconnect(); } }).observe(document, { childList: true });
          })();`,
        })
      ).identifier;
      await browser.send("Fetch.enable", {
        patterns: [
          { urlPattern: "*/api/tree*", requestStage: "Request" },
          ...(strip
            ? [{ urlPattern: "*/view/*", requestStage: "Response", resourceType: "Document" }]
            : []),
        ],
      });
      await browser.send("Page.navigate", { url: `${server.base}/view/` });
      const deadline = Date.now() + LOAD_MS;
      let settled = false;
      while (Date.now() < deadline) {
        await sleep(100);
        const now = await browser.evaluate(
          "({ now: performance.now(), last: window.__frames?.at(-1)?.at ?? null, inline: !!window.METABROWSER_INITIAL_TREE?.summary })",
        );
        if (answered > 0 && now.last !== null && now.now - now.last > QUIET_MS) {
          settled = true;
          break;
        }
      }
      await browser.send("Fetch.disable");
      const page = await browser.evaluate(
        "({ frames: window.__frames, shifts: window.__shifts, inline: !!window.METABROWSER_INITIAL_TREE?.summary, paneWidth: Math.round(document.querySelector('.tree-pane').getBoundingClientRect().width), scheme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light' })",
      );
      const first = page.frames[0] ?? null;
      const last = page.frames.at(-1) ?? null;
      results.push({
        name,
        theme,
        width,
        slow,
        unknown: strip,
        settled,
        inline: page.inline,
        paneWidth: page.paneWidth,
        scheme: page.scheme,
        frames: page.frames.length,
        first: first && {
          reads: first.reads,
          ignoredLine: first.ignoredLine,
          line: first.boxes["line 0"],
        },
        last: last && {
          reads: last.reads,
          ignoredLine: last.ignoredLine,
          line: last.boxes["line 0"],
        },
        moved: movement(page.frames),
        // The shifts after first paint. One in that frame is the move into it: in the
        // narrowest pane, the filter bar's wrap as it is filled (above).
        shift: sumShifts(page.shifts.filter((s) => first && s.at > first.at + FRAME_MS)),
        before: sumShifts(page.shifts.filter((s) => !first || s.at <= first.at + FRAME_MS)),
        shifts: page.shifts,
        trail: page.frames.map(
          (frame) =>
            `${frame.at} ${frame.ignoredLine} ${frame.boxes["line 0"]?.join("/")} ${frame.boxes["row 0"]?.join("/")} ${frame.reads}`,
        ),
      });
      phase(name);
    };
    for (const theme of ["light", "dark"]) {
      for (const width of WIDTHS) {
        for (const slow of [false, true]) {
          await load({
            server: ignoring,
            name: `ignored ${slow ? "slow" : "fast"} ${width}px ${theme}`,
            theme,
            width,
            slow,
            strip: false,
          });
        }
      }
      for (const slow of [false, true]) {
        await load({
          server: clean,
          name: `none ${slow ? "slow" : "fast"} 300px ${theme}`,
          theme,
          width: 300,
          slow,
          strip: false,
        });
      }
      for (const width of WIDTHS) {
        await load({
          server: ignoring,
          name: `ignored unknown slow ${width}px ${theme}`,
          theme,
          width,
          slow: true,
          strip: true,
        });
      }
    }
    await load({
      server: clean,
      name: "none unknown slow 300px light",
      theme: "light",
      width: 300,
      slow: true,
      strip: true,
    });
  } finally {
    await browser.close();
    await ignoring.stop();
    await clean.stop();
  }
  process.stdout.write(`${JSON.stringify({ results })}\n`);
}

main().catch((error) => {
  process.stderr.write(`files totals session threw: ${error?.stack || error}\n`);
  process.exitCode = 1;
});
