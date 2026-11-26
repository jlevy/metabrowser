// The Pulls tab's readiness column (mb-3n21), laid out by headless Chrome: the production panel
// module, the shell's SDK, icon registry, and stylesheets, mounted on recorded answers.
//
//   CHROME_BIN=/path/to/chrome KPRESS_STATIC=/dir/with/css/and/fonts \
//     CHROME_PROFILES=/dir/the/caller/removes [MEASURE_OUT=<file>] [SHOTS_DIR=<dir>] \
//     node tests/dom/github-pulls-readiness-chrome.mjs
//
// tests/test_github_pulls_readiness_chrome.py copies KPress's faces into KPRESS_STATIC and owns
// CHROME_PROFILES, as tests/test_github_pull_header_chrome.py does.
//
// The page mounts builtin_plugins/github/pulls-panel.js with the shell's own SDK on the list,
// the stacks, and the statuses the server answered once the scan of every open pull request's
// status had ended (tests/fixtures/github-pulls-readiness-responses.json and
// github-stacks-responses.json): #7 and #8 are a stack's members, a level in, and the rows
// hold an open pull request of each tone, a merged one, and a closed one. Each row's lines are
// the recorded summary of #106's list (github-pull-files-summary-responses.json), "+1,093
// −493". The statuses' answer is held until the session lets it go, so each row is laid out
// before its readiness and again after. In the light theme and the dark, at every pane width
// from the 180 px minimum to 600 px, it holds that:
//
// - every pull request's row has the readiness's column between its toggle and its age, one
//   width on every row, flush or a level in, holding a glyph or not, so the glyphs down the list
//   start at one edge and the ages end at another;
// - the glyph is the app's one glyph size, centered on the last line, and the last line stays
//   one line tall: nothing in a row moves when its readiness arrives;
// - the glyph takes its tone's ink, the shell's or the plugin's token, and the label the text's;
// - the label follows the glyph exactly where the list is at least the container query's bound
//   (`@container github-pulls` in the plugin's styles.css), and is whole there, every label the
//   server gives a verdict (`SLOT_LABELS` in pull-readiness.js) in its room;
// - nothing scrolls sideways.
//
// Then, at a pane width set a pixel at a time from 300 to 600 px, it measures where a row a
// level in, a stack's member, has the room its lines need, `--github-pulls-lines-room`, and its
// chevron beside the column with its widest label and the age, and holds that the label is
// drawn from that width on and not before it: the bound the rule records. MEASURE_OUT names a
// file for what it measured, and SHOTS_DIR a directory for a screenshot of the list at the
// default pane and a wide one in each theme, at a device scale of 2.
import fs from "node:fs";
import http from "node:http";
import { createRequire } from "node:module";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const { agesFrom } = createRequire(import.meta.url)("./sdk-ref-fixture.js");

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const GITHUB = path.join(root, "src/metabrowser/builtin_plugins/github");
const KPRESS = process.env.KPRESS_STATIC ? path.resolve(process.env.KPRESS_STATIC) : null;
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const TOLERANCE_PX = 0.5;
const near = (a, b, tolerance = TOLERANCE_PX) =>
  typeof a === "number" && typeof b === "number" && Math.abs(a - b) <= tolerance;
const started = Date.now();
const lap = (what) => process.stderr.write(`${Date.now() - started} ms: ${what}\n`);

const fixture = (name) =>
  JSON.parse(fs.readFileSync(path.join(root, "tests/fixtures", name), "utf8"));
const recorded = fixture("github-pulls-readiness-responses.json");
const rowsOf = (answer) => answer.body.rows.map((row) => JSON.parse(row));
const summed = fixture("github-pull-files-summary-responses.json").summed.body;
const ANSWERS = {
  list: { ...recorded.list.body, rows: rowsOf(recorded.list) },
  stacks: fixture("github-stacks-responses.json").current.body,
  statuses: {
    ...recorded.scanned.body,
    rows: [...rowsOf(recorded.scanned), ...rowsOf(recorded.scanned_more)],
  },
  lines: { source: summed.source, row: summed.rows.find((row) => row.number === 106) },
};
// The rows the checks read: an open pull request of each tone, ready, waiting, and a draft
// with conflicts, a merged and a closed one, and the stack's members, a level in.
const ROWS = [106, 105, 10, 9, 8, 7];
const INDENTED = 7;
const WIDTHS = [180, 220, 260, 299, 340, 380, 420, 480, 560, 600];
const THEMES = ["light", "dark"];
const SDK = [
  "icons.js",
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
  "plugin-sdk.js",
  "plugin-sdk-views.js",
];
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>readiness</title>
<meta http-equiv="Content-Security-Policy" content="img-src 'self' data:">
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/github/styles.css">
<script>
  window.METABROWSER_SETTINGS = { SYNTAX_HIGHLIGHT_MAX_BYTES: 524288, SYNTAX_LANGUAGE_BY_BASENAME: {}, SYNTAX_LANGUAGE_BY_EXTENSION: {} };
</script>
<script src="/static/changed-files-tree.js"></script>
${SDK.map((name) => `<script src="/static/${name}"></script>`).join("\n")}
</head><body><div id="pane" class="tree-pane"></div></body></html>`;
const TYPES = {
  ".css": "text/css",
  ".js": "text/javascript",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
};

function serve() {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    let file = null;
    if (url.pathname === "/") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(PAGE);
      return;
    }
    if (url.pathname === "/answers.json") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify(ANSWERS));
      return;
    }
    if (url.pathname.startsWith("/static/")) {
      file = path.join(STATIC, url.pathname.slice(8));
    } else if (url.pathname.startsWith("/github/")) {
      file = path.join(GITHUB, url.pathname.slice(8));
    } else if (KPRESS && url.pathname.startsWith("/kpress/")) {
      file = path.join(KPRESS, url.pathname.slice(8));
    }
    const within = [root, KPRESS].filter(Boolean).some((dir) => file?.startsWith(dir));
    if (!file || !within || !fs.existsSync(file)) {
      response.writeHead(404);
      response.end();
      return;
    }
    response.writeHead(200, { "content-type": TYPES[path.extname(file)] ?? "text/plain" });
    fs.createReadStream(file).pipe(response);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

// In the page: mount the panel at *width* in *theme*, each statuses read held until
// `window.__release()`.
const MOUNT = `async (width, theme) => {
  window.__panel?.dispose();
  (await import("/github/row-readiness.js")).documentReadiness.clear();
  (await import("/github/row-lines.js")).documentRowLines.clear();
  (await import("/github/stack-lines.js")).documentStackLines.clear();
  (await import("/github/comparison-prefetch.js")).documentComparisons.clear();
  document.documentElement.dataset.theme = theme;
  const answers = window.__answers ??= await (await fetch("/answers.json")).json();
  const panel = window.__module ??= await import("/github/pulls-panel.js");
  const held = [];
  window.__release = () => held.splice(0).forEach((release) => release());
  window.__asked = [];
  const respond = (body, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  const statuses = new Map(answers.statuses.rows.map((row) => [row.number, row]));
  window.fetch = async (route) => {
    const url = new URL(route, location.href);
    const numbers = (url.searchParams.get("numbers") ?? "").split(",").map(Number);
    if (url.pathname === "/api/plugin/github/pull-statuses") {
      window.__asked.push(numbers);
      await new Promise((resolve) => held.push(resolve));
      return respond({ ...answers.statuses, rows: numbers.map((number) => statuses.get(number)).filter(Boolean) });
    }
    if (url.pathname === "/api/plugin/github/pull-files-summary") {
      return respond({ source: answers.lines.source, rows: numbers.map((number) => ({ ...answers.lines.row, number })) });
    }
    if (url.pathname === "/api/plugin/github/pulls") return respond(answers.list);
    if (url.pathname === "/api/plugin/github/stacks") return respond(answers.stacks);
    if (url.pathname === "/api/plugin/github/pulls-prefetch") return respond({ prefetch: "not_due" });
    return respond(null, 404);
  };
  const pane = document.getElementById("pane");
  // Tall enough that the window draws every row, the list's oldest, #10 and #9, among them.
  pane.style.cssText = "width:" + width + "px;height:12000px;overflow:auto;position:relative";
  const container = document.createElement("div");
  pane.replaceChildren(container);
  const sdk = window.metabrowser;
  const mb = {
    ...sdk,
    perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
    filterControls: { groupHtml: () => "<div></div>", bind: () => () => {} },
    ...(${agesFrom})(document, () => ({ label: "1m", className: "age-min" })),
    formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
    loadChangedFilesTree: () => Promise.resolve(window.MetabrowserChangedFilesTree),
    whenIdle: (callback) => {
      const handle = setTimeout(callback, 0);
      return () => clearTimeout(handle);
    },
  };
  window.__panel = panel.mountPullsPanel(container, {
    kind: "pull-request-list",
    pullsNav: {
      filter: "all", current: null, shown: true, refreshAhead: false, scrollRoot: pane,
      open() {}, file: null, fileHref: (number, file) => "/pull/" + number + "/files/" + file,
      pageFor: () => null, onPageChange: () => () => {}, filterChanged() {},
    },
  }, mb);
  await document.fonts.ready;
  return true;
}`;

// In the page: each checked row's last line, its readiness's column, glyph, and label.
const READ = `(() => {
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height };
  };
  const pane = document.getElementById("pane");
  const list = pane.querySelector(".github-pulls-list");
  const rows = {};
  for (const number of ${JSON.stringify(ROWS)}) {
    const row = document.querySelector('a.github-pulls-row[data-number="' + number + '"]');
    if (row === null) { rows[number] = null; continue; }
    const tail = row.querySelector(":scope > .github-pulls-tail");
    const cell = tail.querySelector(":scope > .github-pulls-readiness");
    const glyph = cell.querySelector(".github-pull-readiness-icon");
    const label = cell.querySelector(".github-pulls-readiness-label");
    const toggle = tail.querySelector(".github-pulls-toggle");
    const style = getComputedStyle(tail);
    rows[number] = {
      level: row.closest("li").dataset.level,
      item: box(row.closest("li")), tail: box(tail), cell: box(cell), age: box(tail.querySelector(".github-pulls-age")),
      change: box(tail.querySelector(".github-pulls-change")),
      glyph: box(glyph?.querySelector("svg") ?? null), tone: glyph?.dataset.tone ?? null,
      glyphInk: glyph ? getComputedStyle(glyph).color : null,
      label: box(label), labelShown: label !== null && getComputedStyle(label).display !== "none",
      labelWhole: label === null || label.scrollWidth <= label.clientWidth + 0.5,
      labelInk: label ? getComputedStyle(label).color : null,
      columns: style.gridTemplateColumns.split(" ").map(parseFloat),
      gap: parseFloat(style.columnGap),
      content: tail.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
      toggleRoom: toggle ? toggle.getBoundingClientRect().width + parseFloat(getComputedStyle(toggle).marginInlineStart) : null,
    };
  }
  return { rows, list: list.getBoundingClientRect().width, listFont: parseFloat(getComputedStyle(list).fontSize), scroll: [pane.scrollWidth, pane.clientWidth] };
})()`;

// In the page: a length of the row's, in px, by a probe inside a row's last line, so its em is
// the row's.
const LENGTH = `((name) => {
  const tail = document.querySelector("a.github-pulls-row .github-pulls-tail");
  const probe = document.createElement("span");
  probe.style.cssText = "position:absolute;visibility:hidden;width:var(" + name + ")";
  tail.append(probe);
  const width = probe.getBoundingClientRect().width;
  probe.remove();
  return width;
})`;

// In the page: a token's color, as a text's ink computes it.
const INK = `((name) => {
  const probe = document.createElement("span");
  probe.style.color = "var(" + name + ")";
  document.body.append(probe);
  const color = getComputedStyle(probe).color;
  probe.remove();
  return color;
})`;

// In the page: whether each label the server gives a verdict is whole in a shown label's room.
const LABELS = `((labels) => {
  const label = document.querySelector('a.github-pulls-row[data-number="106"] .github-pulls-readiness-label');
  const was = label.textContent;
  const widths = {};
  for (const text of labels) {
    label.textContent = text;
    widths[text] = { natural: label.scrollWidth, room: label.clientWidth };
  }
  label.textContent = was;
  return widths;
})`;

const TONE_TOKENS = {
  success: "--status-success-text",
  attention: "--github-pull-attention",
  danger: "--status-error-text",
};

async function main() {
  const bin = process.env.CHROME_BIN;
  const profiles = process.env.CHROME_PROFILES;
  if (!bin || !profiles) {
    throw new Error("CHROME_BIN and CHROME_PROFILES are required");
  }
  const server = await serve();
  const browser = await launchChrome(bin, { profiles });
  lap("Chrome started");
  const measured = {};
  const frames = () =>
    browser.evaluate(
      `new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))`,
    );
  const shot = async (name, width, from = 0) => {
    if (!process.env.SHOTS_DIR) {
      return;
    }
    await browser.send("Emulation.setDeviceMetricsOverride", {
      width: 1280,
      height: 900,
      deviceScaleFactor: 2,
      mobile: false,
    });
    await frames();
    const { data } = await browser.send("Page.captureScreenshot", {
      format: "png",
      clip: { x: 0, y: from, width: width + 16, height: 600, scale: 1 },
      captureBeyondViewport: true,
    });
    await browser.send("Emulation.clearDeviceMetricsOverride");
    await frames();
    fs.mkdirSync(process.env.SHOTS_DIR, { recursive: true });
    fs.writeFileSync(path.join(process.env.SHOTS_DIR, `${name}.png`), Buffer.from(data, "base64"));
  };
  try {
    await browser.send("Runtime.enable");
    await browser.send("Page.enable");
    await browser.send("Page.navigate", { url: `http://127.0.0.1:${server.address().port}/` });
    await browser.waitFor(
      `document.readyState === "complete" && Boolean(window.metabrowser?.changeLine) && Boolean(window.MetabrowserIcons?.toggle)`,
    );
    await browser.evaluate(
      `Promise.all([...document.fonts].map((face) => face.load().catch(() => null))).then(() => document.fonts.ready).then(() => true)`,
    );
    const labels = await browser.evaluate(
      `import("/github/pull-readiness.js").then((module) => [...module.SLOT_LABELS])`,
    );
    lap("the page loaded");
    for (const theme of THEMES) {
      for (const width of WIDTHS) {
        const at = `${width} px ${theme}`;
        await browser.evaluate(`(${MOUNT})(${width}, ${JSON.stringify(theme)})`);
        const asked = await browser.waitFor(`window.__asked.length > 0`, 5000).then(
          () => true,
          () => false,
        );
        check(`${at}: the panel reads its rows' readiness`, asked);
        if (!asked) {
          continue;
        }
        await frames();
        const before = await browser.evaluate(READ);
        await browser.waitFor(
          `(window.__release(), document.querySelector('a.github-pulls-row[data-number="106"] .github-pull-readiness-icon') !== null)`,
        );
        await frames();
        const after = await browser.evaluate(READ);
        const inks = Object.fromEntries(
          await Promise.all(
            Object.entries(TONE_TOKENS).map(async ([tone, token]) => [
              tone,
              await browser.evaluate(`(${INK})(${JSON.stringify(token)})`),
            ]),
          ),
        );
        const textInk = await browser.evaluate(`(${INK})("--text")`);
        const drawn = ROWS.map((number) => after.rows[number]).filter(Boolean);
        check(`${at}: every row checked is drawn`, drawn.length === ROWS.length);
        const first = drawn[0];
        // One column on every row, flush or a level in, with a glyph or none.
        check(
          `${at}: the readiness's column is one width at one edge on every row, and the ages end at one edge`,
          drawn.every(
            (r) =>
              near(r.cell.left, first.cell.left) &&
              near(r.cell.width, first.cell.width) &&
              near(r.age.right, first.age.right),
          ),
          JSON.stringify(drawn.map((r) => ({ cell: r.cell, age: r.age, level: r.level }))),
        );
        check(
          `${at}: a stack's member, a level in, has the column every row has`,
          after.rows[INDENTED]?.level === "2" && after.rows[106]?.level === "1",
          JSON.stringify({ indented: after.rows[INDENTED]?.level, flush: after.rows[106]?.level }),
        );
        // Nothing moves when the readiness arrives, and the last line stays one line tall.
        check(
          `${at}: nothing in a row moves when its readiness arrives`,
          ROWS.every((number) => {
            const was = before.rows[number];
            const now = after.rows[number];
            return (
              was !== null &&
              now !== null &&
              ["item", "tail", "cell", "age", "change"].every(
                (part) =>
                  near(was[part].top, now[part].top) &&
                  near(was[part].left, now[part].left) &&
                  near(was[part].width, now[part].width) &&
                  near(was[part].height, now[part].height),
              )
            );
          }),
          JSON.stringify(
            ROWS.map((number) => [before.rows[number]?.cell, after.rows[number]?.cell]),
          ),
        );
        for (const number of ROWS) {
          const r = after.rows[number];
          if (r === null) {
            continue;
          }
          const status = ANSWERS.statuses.rows.find((row) => row.number === number);
          const tone = status?.readiness?.tone ?? null;
          check(
            `${at}: #${number} draws its answer's tone, or none`,
            r.tone === tone,
            String(r.tone),
          );
          if (tone === null) {
            check(`${at}: #${number}'s column is empty`, r.glyph === null && r.label === null);
            continue;
          }
          check(
            `${at}: #${number}'s glyph is the app's one size, at the column's start, centered on the last line`,
            near(r.glyph.width, 14) &&
              near(r.glyph.left, r.cell.left) &&
              near(r.glyph.top + r.glyph.height / 2, r.tail.top + (r.tail.height - 2) / 2, 1),
            JSON.stringify({ glyph: r.glyph, cell: r.cell, tail: r.tail }),
          );
          check(
            `${at}: #${number}'s glyph takes the ${tone} tone's ink, and its label the text's`,
            r.glyphInk === inks[tone] && r.labelInk === textInk,
            JSON.stringify({
              glyph: r.glyphInk,
              label: r.labelInk,
              ink: inks[tone],
              text: textInk,
            }),
          );
          check(
            `${at}: #${number}'s label, where it is shown, is whole and follows the glyph`,
            !r.labelShown ||
              (r.labelWhole &&
                r.label.left >= r.glyph.right &&
                r.label.right <= r.cell.right + TOLERANCE_PX),
            JSON.stringify({ label: r.label, glyph: r.glyph, cell: r.cell }),
          );
        }
        check(
          `${at}: every row shows its label or none alike`,
          drawn
            .filter((r) => r.tone !== null)
            .every((r) => r.labelShown === drawn.find((each) => each.tone !== null).labelShown),
        );
        check(
          `${at}: nothing scrolls sideways`,
          after.scroll[0] <= after.scroll[1],
          JSON.stringify(after.scroll),
        );
        measured[at] = {
          list: after.list,
          listFont: after.listFont,
          column: first.cell.width,
          labelShown: drawn.find((r) => r.tone !== null)?.labelShown ?? null,
        };
        if (after.rows[106].labelShown) {
          const widths = await browser.evaluate(`(${LABELS})(${JSON.stringify(labels)})`);
          check(
            `${at}: every label the server gives a verdict is whole in the label's room`,
            Object.values(widths).every((each) => each.natural <= each.room + TOLERANCE_PX),
            JSON.stringify(widths),
          );
          measured[at].labels = widths;
        }
        if ((width === 299 || width === 480) && process.env.SHOTS_DIR) {
          await shot(`readiness-${theme}-${width}`, width);
          // The list's end, where the draft with conflicts, #10, and the closed #9 are.
          const end = await browser.evaluate(
            `document.querySelector('a.github-pulls-row[data-number="12"]').getBoundingClientRect().top + window.scrollY - 8`,
          );
          await shot(`readiness-${theme}-${width}-end`, width, end);
        }
        lap(at);
      }
    }

    // The bound: a pane set a pixel at a time, read where the label shows and where a row a
    // level in has its lines' room beside the column with its widest label and the age.
    await browser.evaluate(`(${MOUNT})(300, "light")`);
    await browser.waitFor(`window.__asked.length > 0`);
    await browser.waitFor(
      `(window.__release(), document.querySelector('a.github-pulls-row[data-number="106"] .github-pull-readiness-icon') !== null)`,
    );
    await frames();
    const linesRoom = await browser.evaluate(`(${LENGTH})("--github-pulls-lines-room")`);
    const labelRoom = await browser.evaluate(`(${LENGTH})("--github-pulls-readiness-label-room")`);
    const gap = await browser.evaluate(`(${LENGTH})("--github-pulls-readiness-gap")`);
    const sweep = [];
    for (let width = 300; width <= 600; width += 1) {
      await browser.evaluate(`document.getElementById("pane").style.width = "${width}px"`);
      await frames();
      const read = await browser.evaluate(READ);
      const r = read.rows[INDENTED];
      const [, column, age] = r.columns;
      const full = 14 + gap + labelRoom;
      // The first column's width with the column at its widest, on the row a level in.
      const room = r.content - full - age - 2 * r.gap;
      sweep.push({
        width,
        list: read.list,
        shown: r.labelShown,
        fits: room >= linesRoom + r.toggleRoom - TOLERANCE_PX,
        room,
        column,
      });
    }
    const shownFrom = sweep.find((each) => each.shown)?.width ?? null;
    const fitsFrom = sweep.find((each) => each.fits)?.width ?? null;
    check(
      "the label is shown from the width at which a stack's member has its lines' room beside the widest column, and not before it",
      shownFrom !== null &&
        fitsFrom !== null &&
        shownFrom >= fitsFrom &&
        shownFrom - fitsFrom <= 1 &&
        sweep.every((each) => each.shown === each.width >= shownFrom),
      JSON.stringify({ shownFrom, fitsFrom }),
    );
    measured.bound = {
      shownFrom,
      fitsFrom,
      listFont: sweep[0] ? (await browser.evaluate(READ)).listFont : null,
      linesRoom,
      labelRoom,
      gap,
      atFit: sweep.find((each) => each.width === fitsFrom) ?? null,
    };
    lap(`the bound: shown from ${shownFrom} px, fits from ${fitsFrom} px`);
  } finally {
    if (process.env.MEASURE_OUT) {
      fs.writeFileSync(process.env.MEASURE_OUT, `${JSON.stringify(measured, null, 2)}\n`);
    }
    await browser.close();
    server.close();
  }
  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.stdout.write(`readiness in Chrome: ${failures.length} of ${checks} checks failed\n`);
    process.exit(1);
  }
  process.stdout.write(`readiness in Chrome: ${checks} checks passed\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
