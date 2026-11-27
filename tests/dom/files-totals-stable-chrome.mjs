// The Files nav panel from first paint to settled, laid out by headless Chrome against
// three live `metab` servers: a folder with ignored files, the same with a longer tracked
// count, and one with nothing ignored.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/files-totals-stable-chrome.mjs METAB IGNORING_ROOT WIDE_ROOT CLEAN_ROOT \
//       PORT STATE_DIR
//
// tests/test_files_totals_stable_chrome.py writes the folders, owns the profile and
// STATE_DIR, runs this in a process group of its own, which Chrome and the servers join,
// and judges what it prints: one JSON line of measurements. Each server searches for a
// port from the one after the last server's, and the session reads the port it took from
// its banner.
//
// The Files totals line's ignored count, "+ 7,898 ignored (132.5 MB)", arrived with the
// server's pass over every file, half a second to seconds after the tree, and in the
// default pane it took a second line and moved the tree down 19.5 px (mb-h3hc). What is
// promised is layout, which only a browser computes: from the frame the panel first shows
// rows to the frame it settles, no box in the navigation (the filter bar, each metadata
// line, the first rows) moves or changes size, and Chrome records no layout shift without
// input at all. Each load is recorded from the document's start, frame by frame, in both
// themes; with the server's tally answered at once and held 2 s ("slow"); in the default
// pane and the narrowest; for the folder with ignored files and for the one with none.
// The folder with the longer tracked count is loaded in the default pane, where its two
// halves outgrew one line on main's code.
//
// Ten loads take the shell as a server drawn before the walk finished the root would
// send it, its inlined totals taken out ("unknown"): with ignored files the line holds the
// ignored line from first paint and the count fills it, in the narrowest pane too, where
// the count is cut short on its one line rather than wrapped; with none, the held line
// keeps its box and says "No ignored files" (docs/design-system.md, "Navigation Metadata
// Line"). Each also holds the event stream until the probe has recorded first paint: its
// snapshot carries the root's entry, whose totals are the ones the shell inlines, and
// that server sends them pending until the walk finishes the root (server.py,
// `_root_totals`). This does not replay that server's stream, whose snapshot comes at
// once with a root entry that has no totals, the finished root following in an
// `fs.change`: it sends one late snapshot with the finished totals, which stands in for
// that `fs.change` and reaches the line by the same path (app.js, `applyCellPatch` to
// `updateRootAggregatePresentation`); the reducer's handling of a pending entry is
// tests/dom/tree-summary-line-session.js's. Let through at once, the snapshot settled
// the line 17 to 100 ms after first paint for the folder with nothing ignored (CI, and a
// 4-CPU Linux run, on 2026-11-17), and once in CI before it, so no frame recorded the
// held line, though nothing moved. Two of them ("provisional") answer the first tally as
// the server does mid-walk, `tally_cache_status: "scanning"` with nothing ignored yet,
// and hold the stream until 1.5 s after it instead, so the held line must outlast a
// provisional tally that says nothing is ignored.
//
// Once a load settles, the tracked and ignored lines' tooltips are read as the shell
// decides them (`tipAddsInformation`): each shows only while its line is cut short.
//
// A last load fails filter-controls.js, so the filter bar is never filled and keeps the
// shell's placeholder: the tree, held while it does, must show at the hold's bound
// (styles.css, the rule after `.nav-filter-bar`). Its result is `failOpen`, apart from
// the thirty.
//
// One load holds Source Sans until the first visible tree rows. Its fallback layout
// stays in place after the slow font arrives.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import { spawn } from "node:child_process";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, ignoringRoot, wideRoot, cleanRoot, port, state] = process.argv.slice(2);
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
// How long a provisional load holds the event stream after its provisional tally.
const ENTRY_AFTER_MS = 1500;
// The server's first line names the port it took, which a port in use moves.
const SERVING = /Serving .* at http:\/\/127\.0\.0\.1:(\d+)\/view\//;
const TALLY = /\/api\/tree\?depth=0(&|$)/;
const CONTROLS = /\/static\/filter-controls\.js(\?|$)/;
const CHROME_SANS = /\/source-sans-3-latin-wght-normal\.woff2(\?|$)/;

/** Start one server searching from port *at*, resolving once it says where it serves. */
async function serve(root, at, dir) {
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
  /** @type {number} */
  const took = await new Promise((resolve, reject) => {
    const bound = setTimeout(() => reject(new Error(`no server: ${output}`)), 30000);
    const read = (chunk) => {
      output += chunk;
      const serving = SERVING.exec(output);
      if (serving) {
        clearTimeout(bound);
        resolve(Number(serving[1]));
      }
    };
    server.stdout.on("data", read);
    server.stderr.on("data", read);
    server.once("exit", () => reject(new Error(`server exited: ${output}`)));
  });
  return {
    base: `http://127.0.0.1:${took}`,
    port: took,
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
  // When the parser inserts the tree, no later than the hold on it starts (styles.css).
  new MutationObserver((_, observer) => {
    if (document.getElementById("tree-content")) {
      window.__treeAt = performance.now();
      observer.disconnect();
    }
  }).observe(document, { childList: true, subtree: true });
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (!entry.hadRecentInput) {
        const sources = (entry.sources || []).map((source) => source.node && source.node.nodeType === 1 ? source.node.tagName.toLowerCase() + (source.node.id ? "#" + source.node.id : "") + "." + String(source.node.className).trim().split(/\\s+/).join(".") : String(source.node && source.node.nodeName));
        // Where each source was and went, [x, y, width, height] in CSS px, so a failure
        // says which way a node moved and by how much, not only that it did (mb-r5s7).
        const rect = (r) => r ? [r.x, r.y, r.width, r.height].map((v) => Math.round(v * 100) / 100) : null;
        const moves = (entry.sources || []).map((source) => [rect(source.previousRect), rect(source.currentRect)]);
        window.__shifts.push({ at: Math.round(entry.startTime), value: entry.value, sources, moves, viewport: [innerWidth, innerHeight] });
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
    // First paint is the first frame with rows shown, whether or not the filter bar is
    // filled yet. In a pane too narrow for it the bar, which the shell ships one line
    // tall, wraps to two as app.js fills it, and rows shown before that moved 30 px with
    // it (mb-a5pa, mb-kiqm), so the tree is hidden until the bar is filled (styles.css,
    // the rule after \`.nav-filter-bar\`): a row under that rule is in place, not shown.
    const shown = rows.length > 0 && getComputedStyle(rows[0]).visibility === "visible";
    if (panel && shown) {
      const boxes = { bar: box(document.getElementById("nav-filter-bar")) };
      // The totals and their remarks are the band over the panel, outside its scroller.
      const band = document.getElementById("nav-metadata-files");
      band.querySelectorAll(".nav-metadata").forEach((line, i) => { boxes["line " + i] = box(line); });
      rows.forEach((row, i) => { boxes["row " + i] = box(row); });
      const summary = band.querySelector(".tree-summary");
      const frame = {
        at: Math.round(performance.now()),
        boxes,
        reads: summary ? summary.textContent.replace(/\\s+/g, " ").trim() : null,
        ignoredLine: band.querySelector(".tree-summary-ignored-none") ? "no ignored files" : band.querySelector(".tree-summary-ignored") ? "counted" : band.querySelector(".tree-summary-ignored-pending") ? "held" : "none",
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
  const wide = await serve(wideRoot, ignoring.port + 1, path.join(state, "wide"));
  const clean = await serve(cleanRoot, wide.port + 1, path.join(state, "clean"));
  phase("servers");
  const browser = await launchChrome(process.env.CHROME_BIN, {
    profiles: process.env.CHROME_PROFILES,
    width: 1280,
    height: 900,
  });
  const results = [];
  /** @type {any[]} */
  const lateFonts = [];
  /** @type {any[]} */
  const failed = [];
  try {
    phase("chrome");
    await browser.send("Page.enable");
    await browser.send("Network.enable");
    await browser.send("Network.setCacheDisabled", { cacheDisabled: true });
    await browser.send("Page.addScriptToEvaluateOnNewDocument", { source: PROBE });
    let holdMs = 0;
    let answered = 0;
    // A provisional load: its first tally answered as mid-walk, and the event stream, which
    // brings the root's entry, held until ENTRY_AFTER_MS after that.
    let provisional = false;
    let tallies = 0;
    /** @type {string[]} */
    let heldStreams = [];
    let streamsReleased = true;
    // A load whose filter-controls.js fails, so the filter bar is never filled.
    let failControls = false;
    let holdingSans = false;
    /** @type {string | null} */
    let heldSans = null;
    const releaseStreams = async () => {
      streamsReleased = true;
      for (const requestId of heldStreams.splice(0)) {
        await browser.send("Fetch.continueRequest", { requestId }).catch(() => {});
      }
    };
    browser.on("Network.responseReceived", (params) => {
      if (TALLY.test(params.response.url)) {
        answered += 1;
      }
    });
    /** @param {any} params @param {(text: string) => string} rewrite */
    const fulfill = async (params, rewrite) => {
      const body = await browser.send("Fetch.getResponseBody", { requestId: params.requestId });
      const text = body.base64Encoded
        ? Buffer.from(body.body, "base64").toString("utf8")
        : body.body;
      await browser.send("Fetch.fulfillRequest", {
        requestId: params.requestId,
        responseCode: params.responseStatusCode,
        responseHeaders: params.responseHeaders.filter(
          (header) => !/^content-(length|encoding)$/i.test(header.name),
        ),
        body: Buffer.from(rewrite(text), "utf8").toString("base64"),
      });
    };
    browser.on("Fetch.requestPaused", async (params) => {
      try {
        const url = params.request.url;
        if (holdingSans && CHROME_SANS.test(url)) {
          holdingSans = false;
          heldSans = params.requestId;
          return;
        }
        if (failControls && CONTROLS.test(url)) {
          await browser.send("Fetch.failRequest", {
            requestId: params.requestId,
            errorReason: "Failed",
          });
          return;
        }
        if (params.responseStatusCode !== undefined && TALLY.test(url)) {
          tallies += 1;
          if (tallies > 1) {
            await fulfill(params, (text) => text);
            return;
          }
          // The first tally, as the server answers it mid-walk: provisional, and with the
          // ignored files the walk has not reached yet not counted.
          await fulfill(params, (text) => {
            const answer = JSON.parse(text);
            answer.tally_cache_status = "scanning";
            answer.summary = { ...answer.summary, ignored_files: 0, ignored_size: 0 };
            return JSON.stringify(answer);
          });
          setTimeout(releaseStreams, ENTRY_AFTER_MS);
          return;
        }
        if (params.responseStatusCode !== undefined && params.resourceType !== "Document") {
          // A provisional load's other tree answers, as the server sent them.
          await fulfill(params, (text) => text);
          return;
        }
        if (params.responseStatusCode !== undefined) {
          // The shell, as a server drawing it before the walk finished the root sends it.
          await fulfill(params, (html) =>
            html.replace(
              /(window\.METABROWSER_INITIAL_TREE=\{.*?), "summary": \{[^}]*\}/,
              (_, before) => before,
            ),
          );
          return;
        }
        if (/\/api\/events/.test(url) && !streamsReleased) {
          heldStreams.push(params.requestId);
          return;
        }
        await sleep(TALLY.test(url) ? holdMs : 0);
        await browser.send("Fetch.continueRequest", { requestId: params.requestId });
      } catch {
        // A request the page abandoned while it was held is gone already.
      }
    });
    let widthScript = null;
    const load = async ({
      server,
      name,
      theme,
      width,
      slow,
      strip,
      early = false,
      failing = false,
      lateFont = false,
      into = results,
    }) => {
      holdMs = slow ? SLOW_MS : 0;
      failControls = failing;
      holdingSans = lateFont;
      heldSans = null;
      let releasedSans = false;
      answered = 0;
      provisional = early;
      tallies = 0;
      heldStreams = [];
      streamsReleased = !strip;
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
          ...(lateFont
            ? [{ urlPattern: "*source-sans-3-latin-wght-normal.woff2*", requestStage: "Request" }]
            : []),
          ...(strip
            ? [
                { urlPattern: "*/view/*", requestStage: "Response", resourceType: "Document" },
                { urlPattern: "*/api/events*", requestStage: "Request" },
              ]
            : []),
          ...(provisional ? [{ urlPattern: "*/api/tree*", requestStage: "Response" }] : []),
          ...(failing
            ? [{ urlPattern: "*/static/filter-controls.js*", requestStage: "Request" }]
            : []),
        ],
      });
      await browser.send("Page.navigate", { url: `${server.base}/view/` });
      const deadline = Date.now() + LOAD_MS;
      let settled = false;
      while (Date.now() < deadline) {
        await sleep(100);
        const now = await browser.evaluate(
          "({ now: performance.now(), painted: (window.__frames?.length ?? 0) > 0, last: window.__frames?.at(-1)?.at ?? null, held: window.__frames?.at(-1)?.ignoredLine === 'held' })",
        );
        if (now.painted && heldSans !== null) {
          await browser.send("Fetch.continueRequest", { requestId: heldSans });
          heldSans = null;
          releasedSans = true;
        }
        // An unknown load's stream goes once first paint is recorded, so the root's
        // finished entry reaches the page after it, as its `fs.change` does from a server
        // still walking the root: an order, not a margin. A provisional load's goes on its
        // own timer.
        if (!streamsReleased && !provisional && now.painted) {
          await releaseStreams();
        }
        // A held line is never settled: it waits for the root's totals, so a load whose
        // line stays held runs to LOAD_MS and fails as never settled.
        if (
          answered > 0 &&
          streamsReleased &&
          (!lateFont || releasedSans) &&
          now.last !== null &&
          !now.held &&
          now.now - now.last > QUIET_MS
        ) {
          settled = true;
          break;
        }
      }
      await releaseStreams();
      await browser.send("Fetch.disable");
      if (lateFont) {
        await browser.evaluate(
          "document.fonts.ready.then(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))))",
        );
      }
      const page = await browser.evaluate(
        `({
          frames: window.__frames,
          sansResponseEnd: performance.getEntriesByType("resource").find((entry) => entry.name.includes("source-sans-3-latin-wght-normal.woff2"))?.responseEnd ?? null,
          shifts: window.__shifts,
          treeAt: window.__treeAt ?? null,
          barPending: !!document.querySelector('#nav-filter-bar .tally-pending'),
          inline: !!window.METABROWSER_INITIAL_TREE?.summary,
          paneWidth: Math.round(document.querySelector('.tree-pane').getBoundingClientRect().width),
          scheme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
          tip: (() => {
            const line = document.querySelector('#nav-metadata-files .tree-summary-ignored:not(.tree-summary-ignored-none)');
            return line && { text: line.dataset.tipText, cut: tipAnchorIsCut(line), shows: tipAddsInformation(line) };
          })(),
          trackedTip: (() => {
            const line = document.querySelector('#nav-metadata-files .tree-summary-line[data-tip-text]');
            return line && { text: line.dataset.tipText, cut: tipAnchorIsCut(line), shows: tipAddsInformation(line) };
          })(),
        })`,
      );
      const first = page.frames[0] ?? null;
      const last = page.frames.at(-1) ?? null;
      // Every shift from the document's start, the move into first paint too: nothing in
      // the panel moves into it either. No window after first paint could set that move
      // apart: CI reported the filter bar's wrap at 180 px, when it moved the tree 30 px,
      // 24, 72, and 111 ms after the rAF of the frame it moved into (mb-kiqm).
      const counted = page.shifts;
      into.push({
        name,
        theme,
        width,
        slow,
        unknown: strip,
        provisional: early,
        settled,
        fontArrivedAfterRows: releasedSans && first !== null && page.sansResponseEnd > first.at,
        inline: page.inline,
        paneWidth: page.paneWidth,
        scheme: page.scheme,
        frames: page.frames.length,
        // From the tree's insertion to its first frame with rows shown, and whether the
        // filter bar still held the shell's placeholder when the load settled.
        shownAfter: first && page.treeAt !== null ? Math.round(first.at - page.treeAt) : null,
        barPending: page.barPending,
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
        lines: page.frames
          .map((frame) => frame.ignoredLine)
          .filter((one, i, all) => i === 0 || all[i - 1] !== one),
        tip: page.tip,
        trackedTip: page.trackedTip,
        moved: movement(page.frames),
        shift: sumShifts(counted),
        counted,
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
          for (const [server, folder] of [
            [ignoring, "ignored"],
            [clean, "none"],
          ]) {
            await load({
              server,
              name: `${folder} ${slow ? "slow" : "fast"} ${width}px ${theme}`,
              theme,
              width,
              slow,
              strip: false,
            });
          }
        }
      }
      for (const slow of [false, true]) {
        await load({
          server: wide,
          name: `ignored wide ${slow ? "slow" : "fast"} 300px ${theme}`,
          theme,
          width: 300,
          slow,
          strip: false,
        });
      }
      for (const width of WIDTHS) {
        for (const [server, folder] of [
          [ignoring, "ignored"],
          [clean, "none"],
        ]) {
          await load({
            server,
            name: `${folder} unknown slow ${width}px ${theme}`,
            theme,
            width,
            slow: true,
            strip: true,
          });
        }
      }
      await load({
        server: ignoring,
        name: `ignored unknown provisional 300px ${theme}`,
        theme,
        width: 300,
        slow: false,
        strip: true,
        early: true,
      });
    }
    await load({
      server: ignoring,
      name: "ignored late font 300px dark",
      theme: "dark",
      width: 300,
      slow: false,
      strip: false,
      lateFont: true,
      into: lateFonts,
    });
    // The hold's bound: with filter-controls.js failed the bar is never filled, and the
    // tree, held while the bar holds its placeholder, is shown at the bound (styles.css).
    await load({
      server: ignoring,
      name: "ignored filter controls failed 300px light",
      theme: "light",
      width: 300,
      slow: false,
      strip: false,
      failing: true,
      into: failed,
    });
  } finally {
    await browser.close();
    await ignoring.stop();
    await wide.stop();
    await clean.stop();
  }
  process.stdout.write(
    `${JSON.stringify({ results, lateFont: lateFonts[0] ?? null, failOpen: failed[0] ?? null })}\n`,
  );
}

main().catch((error) => {
  process.stderr.write(`files totals session threw: ${error?.stack || error}\n`);
  process.exitCode = 1;
});
