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
// hold open pull requests in success, attention, and severe, a merged one, and a closed one,
// whose glyphs are each held to their tone's ink. Each row's lines are
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
  // The list's second page, by activity, which holds #8 and #7: the panel reads it once the
  // end of the first is in view.
  more: { ...recorded.more.body, rows: rowsOf(recorded.more) },
  stacks: fixture("github-stacks-responses.json").current.body,
  statuses: {
    ...recorded.scanned.body,
    rows: [...rowsOf(recorded.scanned), ...rowsOf(recorded.scanned_more)],
  },
  lines: { source: summed.source, row: summed.rows.find((row) => row.number === 106) },
};
// The rows the checks read: open pull requests ready, waiting, and a draft with conflicts, in
// success, attention, and severe, a merged and a closed one, and the stack's members, a level in.
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
    if (url.pathname === "/api/plugin/github/pulls") {
      const after = url.searchParams.get("after");
      return respond(after === String(answers.list.next_after) ? answers.more : answers.list);
    }
    if (url.pathname === "/api/plugin/github/stacks") return respond(answers.stacks);
    if (url.pathname === "/api/plugin/github/pulls-prefetch") return respond({ prefetch: "not_due" });
    return respond(null, 404);
  };
  const pane = document.getElementById("pane");
  // Tall enough that the window draws every row of both pages, the oldest, #8 and #7, among
  // them.
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

// Measure the wrapping heading and its trailing readiness and PR number.
const READ = `(() => {
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height };
  };
  const pane = document.getElementById("pane");
  const rows = {};
  for (const id of ${JSON.stringify(ROWS)}) {
    const row = pane.querySelector('a.github-pulls-row[data-number="' + id + '"]');
    if (row === null) { rows[id] = null; continue; }
    const head = row.querySelector(".github-pulls-heading");
    const copy = head.querySelector(".github-pull-row-copy");
    const end = row.querySelector(".github-pulls-tail > .github-pull-row-end");
    const cell = end.querySelector(".github-pulls-readiness");
    const glyph = cell.querySelector(".github-pull-readiness-icon");
    const number = end.querySelector(".github-pulls-number");
    const tail = row.querySelector(".github-pulls-tail");
    const bullet = tail.querySelector(".github-pull-stack-dot");
    const title = copy.querySelector(".github-pulls-title");
    const titleLines = [...title.getClientRects()];
    end.style.display = "none";
    const firstWithFullWidth = title.getClientRects()[0]?.width ?? 0;
    end.style.removeProperty("display");
    rows[id] = {
      level: row.closest("li").dataset.level,
      head: box(head), copy: box(copy), end: box(end), cell: box(cell), number: box(number),
      tail: box(tail), age: box(tail.querySelector(".github-pulls-age")),
      glyph: box(glyph?.querySelector("svg") ?? null), tone: glyph?.dataset.tone ?? null,
      ink: glyph ? getComputedStyle(glyph).color : null,
      next: cell.nextElementSibling === number,
      wraps: getComputedStyle(title).whiteSpace === "normal" && getComputedStyle(title).textOverflow === "clip",
      bullet: box(bullet),
      noSuffixInHeading: head.querySelector(".github-pull-row-end") === null,
      lineHeight: parseFloat(getComputedStyle(copy).lineHeight),
      titleLines: titleLines.length,
      firstLineUnchanged: titleLines[0]?.width === firstWithFullWidth,
    };
  }
  return { rows, scroll: [pane.scrollWidth, pane.clientWidth] };
})()`;

// In the page: a token's color, as a text's ink computes it.
const INK = `((name) => {
  const probe = document.createElement("span");
  probe.style.color = "var(" + name + ")";
  document.body.append(probe);
  const color = getComputedStyle(probe).color;
  probe.remove();
  return color;
})`;

const TONE_TOKENS = {
  success: "--status-success-text",
  attention: "--github-pull-attention",
  severe: "--status-warning-text",
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
        const drawn = ROWS.map((id) => after.rows[id]).filter(Boolean);
        check(`${at}: every row checked is drawn`, drawn.length === ROWS.length);
        const right = drawn[0]?.head.right;
        check(
          `${at}: age, bullet, readiness, and number end the summary line, including stack members`,
          drawn.every(
            (r) =>
              near(r.number.right, right) &&
              r.age.right <= r.bullet.left &&
              r.bullet.right <= r.cell.left,
          ) &&
            after.rows[INDENTED]?.level === "2" &&
            after.rows[106]?.level === "1",
          JSON.stringify(drawn.map((r) => [r.head.right, r.number.right, r.age.right])),
        );
        for (const id of ROWS) {
          const r = after.rows[id];
          const was = before.rows[id];
          if (!r || !was) {
            continue;
          }
          check(
            `${at}: #${id}'s glyph slot precedes the number below the heading`,
            r.next &&
              r.noSuffixInHeading &&
              near(r.head.bottom, r.tail.top) &&
              near(r.cell.width, 14) &&
              r.cell.right <= r.number.left + TOLERANCE_PX,
            JSON.stringify({ copy: r.copy, end: r.end, cell: r.cell, number: r.number }),
          );
          check(
            `${at}: #${id} keeps its heading size and number position when readiness arrives`,
            near(r.head.height, was.head.height) &&
              near(r.number.right, was.number.right) &&
              near(r.number.bottom - r.tail.top, was.number.bottom - was.tail.top),
          );
          check(`${at}: #${id} allows the title to wrap`, r.wraps);
          if (r.titleLines > 1) {
            check(
              `${at}: #${id}'s first title line gets the full text width`,
              r.firstLineUnchanged,
            );
          }
          const status = ANSWERS.statuses.rows.find((row) => row.number === id);
          const tone = status?.readiness?.tone ?? null;
          check(
            `${at}: #${id} draws its answer's glyph and color, or leaves the slot empty`,
            r.tone === tone &&
              (tone === null
                ? r.glyph === null
                : r.ink === inks[tone] &&
                  near(r.glyph.left, r.cell.left) &&
                  near(r.glyph.width, 14)),
            JSON.stringify({ tone, drawn: r.tone, glyph: r.glyph }),
          );
        }
        if (width === 180) {
          check(
            `${at}: a long heading wraps`,
            drawn.some((r) => r.copy.height > r.lineHeight),
          );
        }
        check(
          `${at}: nothing scrolls sideways`,
          after.scroll[0] <= after.scroll[1],
          JSON.stringify(after.scroll),
        );
        measured[at] = { right, rows: drawn };
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
