// Each Pulls row's third line, its brief change line (mb-d0a3), laid out by headless Chrome: the
// production panel module, the shell's SDK, icon registry, and stylesheets, mounted on recorded
// answers.
//
//   CHROME_BIN=/path/to/chrome KPRESS_STATIC=/dir/with/css/and/fonts \
//     CHROME_PROFILES=/dir/the/caller/removes [MEASURE_OUT=<file>] [SHOTS_DIR=<dir>] \
//     node tests/dom/github-pulls-row-lines-chrome.mjs
//
// tests/test_github_pulls_row_lines_chrome.py copies KPress's faces into KPRESS_STATIC and owns
// CHROME_PROFILES, as tests/test_github_pull_header_chrome.py does.
//
// The page mounts builtin_plugins/github/pulls-panel.js with the shell's own SDK and its icon
// registry (static/icons.js, so the chevron paints), on the recorded All list with no stacks
// and #105 the open pull request. Its rows' change lines are the summary route's recorded
// answer `summed` (tests/fixtures/github-pull-files-summary-responses.json): #106's and #105's
// lists are summed, #104's is not cached, and #103's is filling; a row the recording does not
// name answers as its not-cached row does. The summary's answer is held until the session lets
// it go, so each row is laid out while it waits, in the shell's pending placeholder past the
// quiet period, and again once its line has arrived. At every pane width from 420 px to the
// 180 px minimum, in the light theme and the dark, it holds that:
//
// - each pull request's row is three lines: its link's two, the state icon and the number's
//   line, then the title, and its change line under the title, which holds the chevron in the
//   first icon slot and the line in the title's column; the link holds no chevron;
// - nothing moves when the line arrives: the item, the link, the change line, the chevron, the
//   state icon, the title, and the placeholder's start, which is the line's;
// - the change line stays one line: whole, its statuses cut short with its totals whole, or out
//   of view entirely, never cut through its totals; nothing scrolls sideways;
// - the line's inks and weights are the component's, part for part, as the same line drawn by
//   the SDK outside the row resolves them in that theme, and its item's name says it in words;
// - #104 and #103, whose lists cannot be had, show the chevron alone, no placeholder, once
//   answered;
// - the open row's highlight carries onto its change line: its background and its left bar.
//
// At 299 px, the default pane, in each theme, with real pointer and keyboard input, it holds
// that the change line hovers on its own and takes the focus ring on its own; that a press on a
// row's title opens the pull request and expands nothing; and that a press on the chevron, and
// one on the line, open and close the files under the change line, and open no page. The keys
// need the shell's registry, which this page has not: tests/dom/github-pulls-stacks-chrome.mjs
// holds them in the running app.
//
// It also lays out the change lines of this repository's own pull requests (`REAL_LINES`), to
// say how wide a typical line is, which the placeholder's width is judged against.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

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
const near = (a, b) =>
  typeof a === "number" && typeof b === "number" && Math.abs(a - b) <= TOLERANCE_PX;
const started = Date.now();
const lap = (what) => process.stderr.write(`${Date.now() - started} ms: ${what}\n`);

const fixture = (name) =>
  JSON.parse(fs.readFileSync(path.join(root, "tests/fixtures", name), "utf8"));
const lists = fixture("github-pulls-panel-responses.json");
const rowsOf = (rows) =>
  Array.isArray(rows)
    ? rows.map((row) => JSON.parse(row))
    : [rows.same_as].flat().flatMap((holder) => rowsOf(lists[holder].body.rows));
// The recording holds a changed file as one line of JSON.
const twoFiles = fixture("github-pull-files-responses.json").comparison;
const ANSWERS = {
  list: { ...lists.current.body, rows: rowsOf(lists.current.body.rows) },
  stacks: fixture("github-stacks-responses.json").empty.body,
  summed: fixture("github-pull-files-summary-responses.json").summed.body,
  // A row's list of changed files, once its chevron opens it: the recorded two-file list.
  files: { ...twoFiles, rows: twoFiles.rows.map((row) => JSON.parse(row)) },
};
// The rows the checks read: two with a line, one whose list is not cached, one filling.
const SHOWN = [106, 105];
const NONE = [104, 103];
const OPEN = 105;

// This repository's pull requests #440 to #488, as GitHub listed their changed files on
// 2026-11-16 (`GET /repos/{owner}/{repo}/pulls/{n}/files`), summed as the summary route sums a
// cached list: [number, added, modified, removed, renamed, additions, deletions].
const REAL_LINES = [
  [440, 1, 1, 0, 0, 607, 0],
  [441, 10, 6, 0, 0, 3138, 131],
  [442, 1, 8, 0, 0, 3178, 228],
  [444, 3, 19, 0, 0, 1360, 21],
  [445, 8, 58, 0, 0, 4789, 371],
  [447, 2, 6, 0, 0, 569, 5],
  [448, 7, 32, 0, 0, 3914, 468],
  [449, 3, 11, 0, 0, 2907, 58],
  [450, 5, 33, 0, 0, 3908, 663],
  [451, 2, 15, 0, 0, 1409, 149],
  [452, 33, 167, 8, 10, 11410, 11471],
  [453, 1, 1, 0, 0, 1372, 0],
  [455, 8, 27, 0, 0, 3789, 40],
  [456, 0, 7, 0, 0, 164, 21],
  [457, 2, 38, 0, 0, 1779, 411],
  [458, 1, 24, 0, 0, 1553, 122],
  [459, 0, 23, 0, 0, 1876, 185],
  [460, 1, 19, 0, 0, 666, 110],
  [461, 0, 12, 0, 0, 396, 175],
  [462, 4, 24, 0, 0, 1459, 41],
  [463, 2, 26, 0, 0, 1521, 384],
  [464, 4, 16, 0, 0, 4071, 138],
  [465, 2, 35, 0, 0, 1303, 195],
  [466, 0, 31, 0, 0, 3232, 343],
  [467, 0, 10, 0, 0, 390, 359],
  [468, 0, 1, 0, 0, 2, 1],
  [469, 0, 12, 0, 0, 370, 103],
  [470, 2, 34, 0, 0, 2076, 224],
  [471, 8, 31, 0, 0, 3649, 252],
  [472, 1, 17, 0, 0, 795, 53],
  [473, 0, 18, 0, 0, 661, 151],
  [474, 0, 37, 0, 0, 1108, 188],
  [475, 0, 8, 0, 0, 130, 14],
  [476, 0, 19, 0, 0, 1661, 302],
  [477, 2, 38, 0, 0, 2073, 220],
  [478, 0, 25, 0, 0, 2493, 151],
  [479, 2, 37, 0, 0, 2532, 464],
  [480, 6, 5, 0, 0, 241, 3],
  [481, 0, 17, 0, 0, 694, 64],
  [482, 0, 11, 0, 0, 604, 64],
  [484, 10, 18, 0, 0, 3328, 70],
  [485, 1, 1, 0, 0, 610, 0],
  [486, 0, 14, 0, 0, 321, 161],
  [487, 4, 27, 0, 0, 1760, 326],
  [488, 0, 1, 0, 0, 12, 3],
];

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
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>row lines</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/github/styles.css">
<script>
  window.METABROWSER_SETTINGS = { SYNTAX_HIGHLIGHT_MAX_BYTES: 524288, SYNTAX_LANGUAGE_BY_BASENAME: {}, SYNTAX_LANGUAGE_BY_EXTENSION: {} };
</script>
<script src="/static/changed-files-tree.js"></script>
${SDK.map((name) => `<script src="/static/${name}"></script>`).join("\n")}
</head><body><div id="pane" class="tree-pane"></div><div id="reference"></div></body></html>`;

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

// In the page: mount the panel at *width* in *theme* on the recorded answers, each summary read
// held until `window.__release()`. `fresh` clears what the document keeps of earlier mounts.
const MOUNT = `async (width, theme, fresh = true) => {
  window.__panel?.dispose();
  if (fresh) {
    // On a build with no row lines there is nothing to clear, and no row waits for one.
    (await import("/github/row-lines.js").catch(() => null))?.documentRowLines.clear();
    (await import("/github/stack-lines.js").catch(() => null))?.documentStackLines.clear();
    (await import("/github/comparison-prefetch.js")).documentComparisons.clear();
  }
  document.documentElement.dataset.theme = theme;
  const answers = window.__answers ??= await (await fetch("/answers.json")).json();
  const panel = window.__module ??= await import("/github/pulls-panel.js");
  const held = [];
  window.__release = () => held.splice(0).forEach((release) => release());
  window.__asked = [];
  window.__opened = [];
  const respond = (body, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  const summed = new Map(answers.summed.rows.map((row) => [row.number, row]));
  const absent = answers.summed.rows.find((row) => row.reason === "not_cached");
  window.fetch = async (route) => {
    const url = new URL(route, location.href);
    if (url.pathname === "/api/plugin/github/pull-files-summary") {
      const numbers = (url.searchParams.get("numbers") ?? "").split(",").map(Number);
      window.__asked.push(numbers);
      await new Promise((resolve) => held.push(resolve));
      return respond({
        source: answers.summed.source,
        rows: numbers.map((number) => summed.get(number) ?? { ...absent, number }),
      });
    }
    if (url.pathname === "/api/plugin/github/pull-files") {
      // The row's list, of the refresh its line was summed from, so the tree's read of it does
      // not ask for the line again.
      const number = Number(url.searchParams.get("number"));
      return respond({ ...answers.files, number, generation: summed.get(number)?.generation ?? answers.files.generation });
    }
    if (url.pathname === "/api/plugin/github/pulls") return respond(answers.list);
    if (url.pathname === "/api/plugin/github/stacks") return respond(answers.stacks);
    if (url.pathname === "/api/plugin/github/pulls-prefetch") return respond({ prefetch: "not_due" });
    return respond(null, 404);
  };
  const pane = document.getElementById("pane");
  pane.style.cssText = "width:" + width + "px;height:600px;overflow:auto;position:relative";
  const container = document.createElement("div");
  pane.replaceChildren(container);
  const sdk = window.metabrowser;
  const mb = {
    ...sdk,
    perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
    filterControls: { groupHtml: () => "<div></div>", bind: () => () => {} },
    formatAge: () => ({ label: "1m", className: "age-min" }),
    formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
    loadChangedFilesTree: () => Promise.resolve(window.MetabrowserChangedFilesTree),
  };
  window.__panel = panel.mountPullsPanel(container, {
    kind: "pull-request-list",
    pullsNav: {
      filter: "all", current: ${OPEN}, shown: true, refreshAhead: false, scrollRoot: pane,
      open(route) { window.__opened.push(route.number); },
      file: null, fileHref: (number, file) => "/pull/" + number + "/files/" + file,
      pageFor: () => null, onPageChange: () => () => {}, filterChanged() {},
    },
  }, mb);
  await document.fonts.ready;
  return true;
}`;

// In the page: each checked row's geometry and what its third line shows.
const READ = `(() => {
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height };
  };
  const inset = (el) => {
    if (!el) return null;
    const style = getComputedStyle(el);
    return el.getBoundingClientRect().left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft);
  };
  const pane = document.getElementById("pane");
  const rows = {};
  for (const number of ${JSON.stringify([...SHOWN, ...NONE])}) {
    const row = document.querySelector('a.github-pulls-row[data-number="' + number + '"]');
    if (row === null) {
      rows[number] = null;
      continue;
    }
    const item = row.closest("li");
    const change = item.querySelector(".github-pulls-change");
    const line = change?.querySelector(".github-pulls-change-line") ?? null;
    const pending = line?.querySelector(".github-pulls-change-pending") ?? null;
    const said = line?.querySelector(".change-line") ?? null;
    const stats = said?.querySelector(".change-line-stats") ?? null;
    const statuses = said?.querySelector(".change-line-statuses") ?? null;
    const toggle = change?.querySelector(".github-pulls-toggle") ?? null;
    const style = getComputedStyle(row);
    rows[number] = {
      item: box(item), row: box(row), meta: box(row.querySelector(".github-pulls-meta")),
      title: box(row.querySelector(".github-pulls-title")), age: box(row.querySelector(".github-pulls-age")),
      icon: box(row.querySelector(".github-pull-state-icon")),
      rowToggles: row.querySelectorAll(".github-pulls-toggle").length,
      inset: inset(row), changeInset: inset(change),
      slot: parseFloat(style.getPropertyValue("--tree-icon-slot")), gap: parseFloat(style.columnGap),
      change: box(change), toggle: box(toggle), chevron: box(toggle?.querySelector("svg")),
      changeLine: box(line), pending: box(pending), block: box(pending?.querySelector(".tally-pending")),
      pendingShown: pending !== null && getComputedStyle(pending).visibility === "visible",
      line: box(said), stats: box(stats),
      statsWhole: stats === null || stats.scrollWidth <= stats.clientWidth + 0.5,
      statusesCut: statuses !== null && statuses.scrollWidth > statuses.clientWidth + 0.5,
      text: line?.textContent ?? null, nodes: line?.childNodes.length ?? null,
      name: change?.getAttribute("aria-label") ?? null,
      expanded: change?.getAttribute("aria-expanded") ?? null,
      files: box(item.querySelector(".github-pull-files")),
    };
  }
  return { rows, scroll: [pane.scrollWidth, pane.clientWidth] };
})()`;

// In the page: the inks and weights of the line's parts in #106's row, and of the same line
// drawn by the SDK in a plain block of the page, the component outside any host; the name the
// SDK gives it; and the open row's highlight on its link and its change line.
const INKS = `(() => {
  const parts = [".summary-number", ".file-change-status", ".change-line-statuses > .summary-punctuation", ".change-line-group > .summary-punctuation", ".diff-stat-add", ".diff-stat-del"];
  const read = (host) => Object.fromEntries(parts.map((selector) => {
    const el = host?.querySelector(selector);
    const style = el ? getComputedStyle(el) : null;
    return [selector, style ? [style.color, style.fontWeight] : null];
  }));
  const host = document.querySelector('.github-pulls-change[data-number="106"] .github-pulls-change-line');
  const reference = document.getElementById("reference");
  const summary = window.__answers.summed.rows.find((row) => row.number === 106);
  const tree = window.MetabrowserChangedFilesTree;
  const said = window.metabrowser.changeLine({
    statuses: tree.statusBreakdown(summary.statuses.flatMap((entry) => Array.from({ length: entry.count }, () => entry.status))),
    additions: summary.additions, deletions: summary.deletions,
  });
  reference.replaceChildren(...window.metabrowser.changeLineNodes(said));
  const open = document.querySelector('a.github-pulls-row[data-number="${OPEN}"]');
  const openChange = document.querySelector('.github-pulls-change[data-number="${OPEN}"]');
  const other = document.querySelector('.github-pulls-change[data-number="104"]');
  const paint = (el) => el ? [getComputedStyle(el).backgroundColor, getComputedStyle(el).borderLeftColor, getComputedStyle(el).borderLeftWidth] : null;
  return {
    row: read(host), reference: read(reference), text: reference.textContent, label: said.label,
    highlight: { selected: open?.classList.contains("selected") ?? false, row: paint(open), change: paint(openChange), other: paint(other) },
  };
})()`;

// In the page: a token's color, as a background, through a probe.
const TOKEN = `((name) => {
  const probe = document.createElement("span");
  probe.style.background = "var(" + name + ")";
  document.body.append(probe);
  const color = getComputedStyle(probe).backgroundColor;
  probe.remove();
  return color;
})`;

// In the page: how wide each real pull request's line is in the change line's type, whole, and
// its floor, its totals and the gap before them, which the line keeps whole.
const REAL = `((lines) => {
  const tree = window.MetabrowserChangedFilesTree;
  const container = document.querySelector(".github-pulls-change-line");
  const host = document.createElement("span");
  // Beside the rows, at its own widest: the change line's type, the nav's.
  host.style.cssText = "position:absolute;visibility:hidden;width:max-content;white-space:nowrap;font-size:var(--nav-font-size)";
  document.getElementById("pane").append(host);
  const em = parseFloat(getComputedStyle(host).fontSize);
  const round = (value) => Math.round(value * 100) / 100;
  const widths = lines.map(([number, added, modified, removed, renamed, additions, deletions]) => {
    const statuses = Object.entries({ added, modified, removed, renamed }).flatMap(([status, count]) => Array.from({ length: count }, () => status));
    const said = window.metabrowser.changeLine({ statuses: tree.statusBreakdown(statuses), additions, deletions });
    host.replaceChildren(...window.metabrowser.changeLineNodes(said));
    const line = host.querySelector(".change-line");
    const width = line.getBoundingClientRect().width;
    const gap = line.querySelector(".change-line-group") === null ? 0 : parseFloat(getComputedStyle(line).columnGap);
    const floor = gap + line.querySelector(".change-line-stats").getBoundingClientRect().width;
    return { number, text: said.text, px: round(width), em: round(width / em), floorEm: round(floor / em) };
  });
  const font = [getComputedStyle(host).fontFamily, container === null ? null : getComputedStyle(container).fontFamily];
  host.remove();
  const sorted = (key) => widths.map((each) => each[key]).sort((a, b) => a - b);
  const quantile = (values, q) => values[Math.min(values.length - 1, Math.floor(q * values.length))];
  const summary = (key) => {
    const values = sorted(key);
    return { min: values[0], p25: quantile(values, 0.25), median: quantile(values, 0.5), p75: quantile(values, 0.75), p90: quantile(values, 0.9), max: values[values.length - 1] };
  };
  const byWidth = [...widths].sort((a, b) => a.px - b.px);
  return {
    em, font, n: widths.length, em_: summary("em"), floorEm: summary("floorEm"),
    shortest: byWidth[0], median: byWidth[Math.floor(byWidth.length / 2)], longest: byWidth[byWidth.length - 1],
    widths,
  };
})`;

const WIDTHS = [420, 380, 340, 299, 260, 220, 200, 180];
const THEMES = ["light", "dark"];
const PARTS = ["item", "row", "change", "toggle", "chevron", "icon", "title", "changeLine"];

/** Whether *r*'s parts are its three lines: the link's two and the change line under them. */
function threeLines(r) {
  if (!r?.change || !r.toggle || !r.chevron || !r.changeLine) {
    return { ok: false, why: "no change line" };
  }
  const middle = (b) => (b.top + b.bottom) / 2;
  const within = (inner, outer) =>
    inner.top >= outer.top - TOLERANCE_PX && inner.bottom <= outer.bottom + TOLERANCE_PX;
  const parts = {
    // The state icon and the number's line are the first line, the title alone the second.
    iconOnFirst:
      middle(r.icon) >= r.meta.top - TOLERANCE_PX && middle(r.icon) <= r.meta.bottom + TOLERANCE_PX,
    titleUnder:
      r.meta.bottom <= r.title.top + TOLERANCE_PX && r.age.bottom <= r.title.top + TOLERANCE_PX,
    // The state icon is in the second icon slot; the link holds no chevron.
    iconInSecond: near(r.icon.left, r.inset + r.slot + r.gap),
    noLinkChevron: r.rowToggles === 0,
    // The change line is under the link, and the item is the two.
    changeUnder:
      r.change.top >= r.row.bottom - TOLERANCE_PX && r.change.top >= r.title.bottom - TOLERANCE_PX,
    itemIsBoth: near(r.item.height, r.row.height + r.change.height),
    // The chevron is on the change line, in the first icon slot, and the line in the title's column.
    chevronOnThird:
      within(r.chevron, r.change) &&
      within(r.toggle, r.change) &&
      r.chevron.top >= r.title.bottom - TOLERANCE_PX,
    chevronInFirst:
      near(r.toggle.left, r.changeInset) &&
      near(r.toggle.width, r.slot) &&
      near(r.changeInset, r.inset),
    lineInTitleColumn: near(r.changeLine.left, r.title.left),
  };
  return { ok: Object.values(parts).every(Boolean), parts };
}

async function main() {
  const bin = process.env.CHROME_BIN;
  const profiles = process.env.CHROME_PROFILES;
  if (!bin || !profiles) {
    throw new Error("CHROME_BIN and CHROME_PROFILES name Chrome and its profile's directory");
  }
  if (!KPRESS || !fs.existsSync(path.join(KPRESS, "css/style-tokens.css"))) {
    throw new Error("KPRESS_STATIC holds no css/style-tokens.css");
  }
  const server = await serve();
  const browser = await launchChrome(bin, { profiles });
  lap("Chrome started");
  const errors = [];
  browser.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    errors.push(exceptionDetails.exception?.description ?? exceptionDetails.text),
  );
  const measured = {};
  const frames = () =>
    browser.evaluate(
      `new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))`,
    );
  const shot = async (name, width) => {
    if (!process.env.SHOTS_DIR) {
      return;
    }
    // The pane's first rows, to look at.
    const { data } = await browser.send("Page.captureScreenshot", {
      format: "png",
      clip: { x: 0, y: 0, width: width + 16, height: 500, scale: 2 },
    });
    fs.mkdirSync(process.env.SHOTS_DIR, { recursive: true });
    fs.writeFileSync(path.join(process.env.SHOTS_DIR, `${name}.png`), Buffer.from(data, "base64"));
  };
  /** A real pointer: moved to, and pressed if *press*, at an element's point. */
  const pointAt = async (selector, press, at = "middle") => {
    const point = await browser.evaluate(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (el === null) return null;
      const r = el.getBoundingClientRect();
      return { x: ${at === "start" ? "r.left + 4" : "r.left + r.width / 2"}, y: r.top + r.height / 2 };
    })()`);
    if (point === null) {
      return false;
    }
    await browser.send("Input.dispatchMouseEvent", { type: "mouseMoved", ...point });
    if (press) {
      const button = { button: "left", buttons: 1, clickCount: 1 };
      await browser.send("Input.dispatchMouseEvent", { type: "mousePressed", ...point, ...button });
      await browser.send("Input.dispatchMouseEvent", {
        type: "mouseReleased",
        ...point,
        ...button,
        buttons: 0,
      });
    }
    await frames();
    return true;
  };
  const pause = (ms) => browser.evaluate(`new Promise((resolve) => setTimeout(resolve, ${ms}))`);
  const key = async (name, code, keyCode) => {
    for (const type of ["keyDown", "keyUp"]) {
      await browser.send("Input.dispatchKeyEvent", {
        type,
        key: name,
        code,
        windowsVirtualKeyCode: keyCode,
      });
    }
    await frames();
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
        // The theme's tokens, once its theme is the document's.
        const tokens = {
          hover: await browser.evaluate(`(${TOKEN})("--hover-bg")`),
          highlight: await browser.evaluate(`(${TOKEN})("--highlight-bg")`),
        };
        // Each row waits in its placeholder, past the quiet period, its read held. A build that
        // draws no third line draws no placeholder either, and fails here.
        const waits = await browser
          .waitFor(
            `${JSON.stringify([...SHOWN, ...NONE])}.every((number) => document.querySelector('.github-pulls-change[data-number="' + number + '"] .github-pulls-change-pending') !== null)`,
            5000,
          )
          .then(
            () => true,
            () => false,
          );
        check(
          `${at}: each row holds a placeholder on its third line while its line is read`,
          waits,
        );
        if (!waits) {
          await shot(`row-lines-${theme}-${width}`, width);
          lap(`${at}: no placeholder`);
          continue;
        }
        await browser.evaluate(`new Promise((resolve) => setTimeout(resolve, 120))`);
        const before = await browser.evaluate(READ);
        await shot(`row-lines-${theme}-${width}-waiting`, width);
        // One read names every row drawn; release it, and any that follows.
        await browser.waitFor(
          `(window.__release(), ${JSON.stringify(SHOWN)}.every((number) => document.querySelector('.github-pulls-change[data-number="' + number + '"] .change-line') !== null) && ${JSON.stringify(NONE)}.every((number) => document.querySelector('.github-pulls-change[data-number="' + number + '"] .github-pulls-change-line')?.childNodes.length === 0))`,
        );
        await frames();
        const after = await browser.evaluate(READ);
        const inks = await browser.evaluate(INKS);
        await shot(`row-lines-${theme}-${width}`, width);
        const asked = await browser.evaluate(`window.__asked`);
        check(
          `${at}: one read names every row drawn, the first four among them`,
          asked.length === 1 && [...SHOWN, ...NONE].every((number) => asked[0].includes(number)),
          JSON.stringify(asked),
        );
        measured[at] = {
          heights: Object.fromEntries(
            [...SHOWN, ...NONE].map((number) => [
              number,
              {
                waiting: before.rows[number]?.item?.height ?? null,
                shown: after.rows[number]?.item?.height ?? null,
                link: after.rows[number]?.row?.height ?? null,
                change: after.rows[number]?.change?.height ?? null,
              },
            ]),
          ),
          placeholder: before.rows[106]?.block?.width ?? null,
        };
        for (const number of [...SHOWN, ...NONE]) {
          const was = before.rows[number];
          const now = after.rows[number];
          check(
            `${at}: #${number} waits in a placeholder past the quiet period`,
            was?.pendingShown === true,
          );
          for (const [phase, r] of [
            ["waiting", was],
            ["answered", now],
          ]) {
            const lines = threeLines(r);
            check(
              `${at}: #${number}'s row is three lines, the chevron on the third (${phase})`,
              lines.ok,
              JSON.stringify(lines.parts ?? lines.why),
            );
          }
          for (const part of PARTS) {
            check(
              `${at}: #${number}'s ${part} does not move when its line arrives`,
              ["left", "top", "width", "height"].every((side) =>
                near(was?.[part]?.[side], now?.[part]?.[side]),
              ),
              `${JSON.stringify(was?.[part])} ${JSON.stringify(now?.[part])}`,
            );
          }
          // Where the placeholder is: on the third line, or wrapped out of view where a
          // typical line's floor has no room.
          const waitedInView =
            was.pending.top >= was.changeLine.top - TOLERANCE_PX &&
            was.pending.bottom <= was.changeLine.bottom + TOLERANCE_PX;
          check(
            `${at}: #${number}'s placeholder is on its third line or out of view`,
            waitedInView !== was.pending.top >= was.changeLine.bottom - TOLERANCE_PX,
            JSON.stringify({ pending: was.pending, line: was.changeLine }),
          );
          if (NONE.includes(number)) {
            check(
              `${at}: #${number} shows the chevron alone, no line and no placeholder`,
              now.nodes === 0 && now.pending === null && now.chevron !== null && now.text === "",
              JSON.stringify({ nodes: now.nodes, text: now.text }),
            );
            check(
              `${at}: #${number}'s change line is named for its files alone`,
              now.name === "Changed files",
              now.name,
            );
            continue;
          }
          const shown =
            now.line !== null &&
            now.line.top >= now.changeLine.top - TOLERANCE_PX &&
            now.line.bottom <= now.changeLine.bottom + TOLERANCE_PX;
          const dropped = now.line !== null && now.line.top >= now.changeLine.bottom - TOLERANCE_PX;
          check(
            `${at}: #${number}'s line is on its third line or out of view`,
            shown !== dropped,
            JSON.stringify({ line: now.line, changeLine: now.changeLine }),
          );
          measured[at][number] = shown ? (now.statusesCut ? "statuses cut" : "whole") : "dropped";
          if (shown) {
            if (waitedInView) {
              check(
                `${at}: #${number}'s line starts where its placeholder did`,
                near(now.line.left, was.pending.left),
                `${now.line.left} ${was.pending.left}`,
              );
            }
            check(
              `${at}: #${number}'s totals are whole and in the row`,
              now.statsWhole &&
                now.stats.right <= now.changeLine.right + TOLERANCE_PX &&
                now.changeLine.right <= now.change.right + TOLERANCE_PX,
              JSON.stringify({ stats: now.stats, line: now.changeLine }),
            );
          }
        }
        check(
          `${at}: nothing scrolls sideways`,
          before.scroll[0] <= before.scroll[1] && after.scroll[0] <= after.scroll[1],
          JSON.stringify([before.scroll, after.scroll]),
        );
        const now = after.rows[106];
        check(
          `${at}: #106's line says what its list sums to, as the SDK says it`,
          now.text === inks.text,
          `${JSON.stringify(now.text)} ${JSON.stringify(inks.text)}`,
        );
        check(
          `${at}: #106's change line is named in words`,
          now.name === `Changed files: ${inks.label}`,
          now.name,
        );
        if (measured[at][106] !== "dropped") {
          for (const [part, ink] of Object.entries(inks.reference)) {
            check(
              `${at}: ${part} is the component's ink and weight`,
              JSON.stringify(inks.row[part]) === JSON.stringify(ink),
              `${JSON.stringify(inks.row[part])} ${JSON.stringify(ink)}`,
            );
          }
        }
        // The open row's mark: its link and its change line, as one block.
        const mark = inks.highlight;
        check(
          `${at}: the open row's highlight carries onto its change line, its background and its bar`,
          mark.selected &&
            mark.row[0] === tokens.highlight &&
            JSON.stringify(mark.change) === JSON.stringify(mark.row) &&
            mark.other[0] !== tokens.highlight &&
            mark.other[1] !== mark.row[1],
          JSON.stringify({ mark, tokens }),
        );
        if (width === 299) {
          // The Pulls tab mounted again in the document: each line is in its first paint, from
          // the document's keep, with no read and no placeholder.
          await browser.evaluate(`(${MOUNT})(${width}, ${JSON.stringify(theme)}, false)`);
          await browser.waitFor(
            `document.querySelector('a.github-pulls-row[data-number="103"]') !== null`,
          );
          await frames();
          const again = await browser.evaluate(READ);
          check(
            `${at}: mounted again, its lines are drawn at once`,
            again.rows[106]?.text === now.text &&
              again.rows[106]?.pending === null &&
              again.rows[104]?.nodes === 0,
            JSON.stringify(again.rows[106]?.text),
          );
          measured[at].interaction = await interact(at, tokens);
        }
        lap(`${at}: #106 ${measured[at][106]}, #105 ${measured[at][105]}`);
      }
    }
    check(
      "the line shows whole at the widest pane",
      measured["420 px light"]?.[106] === "whole",
      JSON.stringify(measured["420 px light"]?.[106]),
    );
    measured.real = await browser.evaluate(`(${REAL})(${JSON.stringify(REAL_LINES)})`);
    check(
      "the real lines are measured in the change line's type",
      measured.real.font[0] === measured.real.font[1],
      JSON.stringify(measured.real.font),
    );
    check("no page error", errors.length === 0, errors.join("\n"));
  } finally {
    if (process.env.MEASURE_OUT) {
      fs.writeFileSync(process.env.MEASURE_OUT, `${JSON.stringify(measured, null, 1)}\n`);
    }
    await browser.close();
    server.close();
  }

  /**
   * Real pointer and keyboard input on the panel mounted at 299 px: hover, the focus ring, a
   * press on a title, and presses on the chevron and the line.
   */
  async function interact(at, tokens) {
    const result = {};
    const paint = (selector) =>
      browser.evaluate(
        `(() => { const el = document.querySelector(${JSON.stringify(selector)}); return el ? getComputedStyle(el).backgroundColor : null; })()`,
      );
    const ROW = 'a.github-pulls-row[data-number="103"]';
    const CHANGE = '.github-pulls-change[data-number="103"]';
    // Hover: the change line, then the title, each on its own.
    await pointAt(`${CHANGE} .github-pulls-change-line`, false, "start");
    result.hoverChange = [await paint(CHANGE), await paint(ROW)];
    await pointAt(`${ROW} .github-pulls-title`, false);
    result.hoverRow = [await paint(CHANGE), await paint(ROW)];
    await browser.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1200, y: 880 });
    await frames();
    check(
      `${at}: the change line hovers on its own`,
      result.hoverChange[0] === tokens.hover && result.hoverChange[1] !== tokens.hover,
      JSON.stringify({ ...result, tokens }),
    );
    check(
      `${at}: the row's link hovers without its change line`,
      result.hoverRow[1] === tokens.hover && result.hoverRow[0] !== tokens.hover,
      JSON.stringify({ ...result, tokens }),
    );
    // The focus ring: Tab to the list's stop, as a keyboard reader does, then focus moved to a
    // change line, as the panel moves it on Right; each element shows its own ring.
    for (let tab = 0; tab < 6; tab += 1) {
      await key("Tab", "Tab", 9);
      if (
        await browser.evaluate(`document.activeElement?.matches("a.github-pulls-row") === true`)
      ) {
        break;
      }
    }
    const ring = `(() => {
      const el = document.activeElement;
      const style = getComputedStyle(el);
      return { focus: el.matches(".github-pulls-change") ? "change " + el.dataset.number : el.matches("a.github-pulls-row") ? "row " + el.dataset.number : el.tagName, visible: el.matches(":focus-visible"), outline: [style.outlineStyle, style.outlineColor], background: style.backgroundColor };
    })()`;
    result.rowRing = await browser.evaluate(ring);
    await browser.evaluate(`document.querySelector(${JSON.stringify(CHANGE)})?.focus(), true`);
    await frames();
    result.changeRing = await browser.evaluate(ring);
    result.rowWhileChange = await browser.evaluate(
      `(() => { const style = getComputedStyle(document.querySelector(${JSON.stringify(ROW)})); return [style.outlineStyle, style.backgroundColor]; })()`,
    );
    const link = await browser.evaluate(`(${TOKEN})("--link")`);
    check(
      `${at}: the change line takes the focus ring on its own`,
      result.rowRing.focus.startsWith("row ") &&
        result.rowRing.visible &&
        result.changeRing.focus === "change 103" &&
        result.changeRing.visible &&
        result.changeRing.outline[0] === "solid" &&
        result.changeRing.outline[1] === link &&
        result.changeRing.background === tokens.hover &&
        result.rowWhileChange[0] === "none",
      JSON.stringify({ ...result, link }),
    );
    // A press on the title opens the pull request and expands nothing.
    const state = `(() => {
      const change = document.querySelector('.github-pulls-change[data-number="106"]');
      const item = change?.closest("li");
      const files = item?.querySelector(".github-pull-files");
      const box = (el) => el ? el.getBoundingClientRect().toJSON() : null;
      return {
        expanded: change?.getAttribute("aria-expanded") ?? null,
        turned: change?.querySelector(".toggle-chevron") ? getComputedStyle(change.querySelector(".toggle-chevron")).transform : null,
        files: files && files.isConnected && !files.hidden && files.getBoundingClientRect().height > 0 ? box(files) : null,
        change: box(change), opened: [...window.__opened],
      };
    })()`;
    await pointAt('a.github-pulls-row[data-number="106"] .github-pulls-title', true);
    result.title = await browser.evaluate(state);
    check(
      `${at}: a press on a row's title opens the pull request and expands nothing`,
      result.title.opened.includes(106) &&
        result.title.expanded === "false" &&
        result.title.files === null,
      JSON.stringify(result.title),
    );
    // A press on the chevron opens the files, under the change line, and opens no page.
    await pointAt('.github-pulls-change[data-number="106"] .github-pulls-toggle', true);
    // Past the chevron's turn, a --transition-fast.
    await pause(250);
    await browser
      .waitFor(
        `document.querySelector('.github-pulls-change[data-number="106"]')?.closest("li")?.querySelector(".github-pull-files-rows")?.firstElementChild != null`,
        5000,
      )
      .catch(() => false);
    result.chevron = await browser.evaluate(state);
    check(
      `${at}: a press on the chevron opens the files under the change line and opens no page`,
      result.chevron.expanded === "true" &&
        result.chevron.files !== null &&
        result.chevron.files.top >= result.chevron.change.bottom - TOLERANCE_PX &&
        result.chevron.turned !== result.title.turned &&
        result.chevron.opened.length === result.title.opened.length,
      JSON.stringify(result.chevron),
    );
    // The row pressed stays under the pointer: its files open below it, even above the row a
    // reveal placed, #105, the open one, whose place gives way to the reader's press.
    check(
      `${at}: a press on the chevron leaves its change line where it was`,
      result.chevron.change !== null &&
        result.title.change !== null &&
        Math.abs(result.chevron.change.top - result.title.change.top) <= TOLERANCE_PX,
      JSON.stringify({ before: result.title.change, after: result.chevron.change }),
    );
    // A press on the line closes them again.
    await pointAt('.github-pulls-change[data-number="106"] .change-line', true);
    await pause(250);
    result.line = await browser.evaluate(state);
    check(
      `${at}: a press on the change line closes the files and leaves it where it was`,
      result.line.change !== null &&
        Math.abs(result.line.change.top - result.title.change.top) <= TOLERANCE_PX,
      JSON.stringify({ before: result.title.change, after: result.line.change }),
    );
    check(
      `${at}: a press on the change line closes the files and opens no page`,
      result.line.expanded === "false" &&
        result.line.files === null &&
        result.line.turned === result.title.turned &&
        result.line.opened.length === result.title.opened.length,
      JSON.stringify(result.line),
    );
    return result;
  }

  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.stdout.write(`row lines in Chrome: ${failures.length} of ${checks} checks failed\n`);
    process.exit(1);
  }
  process.stdout.write(`row lines in Chrome: ${checks} checks passed\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack ?? error}\n`);
  process.exit(1);
});
