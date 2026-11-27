// Each stack's brief change line in the Pulls tab, on its Stack Overview row (mb-tvhs), laid out
// by headless Chrome: the production panel module and its stylesheets, mounted on recorded
// answers. "Heading" below is the row's one line, "Stack Overview" and then the change line;
// the stack's own row, its label, its size, and its age, is read beside it (`stack`).
//
//   CHROME_BIN=/path/to/chrome KPRESS_STATIC=/dir/with/css/and/fonts \
//     CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/github-pulls-stack-lines-chrome.mjs
//
// tests/test_github_pulls_stack_lines_chrome.py copies KPress's faces into KPRESS_STATIC and
// owns CHROME_PROFILES, as tests/test_github_pull_header_chrome.py does.
//
// The page mounts builtin_plugins/github/pulls-panel.js with the shell's own SDK, on the
// recorded All list, the recorded snapshot of two stacks, #286 and #290, and the stack
// changes tests/test_github_stack_change.py records: #286's line is summed, and #290's
// cannot be had. Each stack change's answer is held until the session lets it go, so the
// heading is laid out while its read is on its way, in the shell's pending placeholder, and
// again once its line has arrived. At every pane width from 420 px to the 180 px minimum, in
// the light theme and the dark, it holds that:
//
// - a heading waits only while its own stack's read is on its way: the list draws #290
//   first, and while its read is held #286's heading, queued behind it, holds no placeholder;
// - nothing moves when the line arrives but the row's chevron, which follows the line: the
//   row, its words, and the placeholder's start, which is the line's; nor anything of the stack's own row, its
//   chevron, its label, its count, and its age, which are whole from the first paint;
// - the heading stays one line: the row is one `--ui-row-height`, and the line, the stack's
//   line totals alone with no file statuses (mb-lqkb), is either whole on the heading's line
//   or out of view entirely, never cut through its totals or across the label;
// - the line's inks and weights are the component's, part for part, as the same line drawn
//   by the SDK outside the heading resolves them in that theme;
// - #290's heading shows no line and no placeholder once its answer says it has none, and
//   in a Pulls tab mounted again nothing is read and no heading waits: a stack whose answer
//   had no line does not pulse and go blank again (review of #484, A4).
//
// It then serves #286 a long line, exact and then estimated, at every width in the light
// theme: while "(estimated)" shows, the totals before it are whole and it follows them at the
// line's gap; it gives way whole first, then the line; and the estimated line goes from view
// where the exact one does (review A on #529, H2 and L1).
//
// It then serves #286 a change of no lines, in each theme at every width (mb-efum): the
// heading shows a muted "0 lines" at the line's weight, whole wherever the long line is.
//
// It also lays out the line totals of this repository's own stacks (`REAL_LINES`, measured
// 2026-11-16 with pull_stack_change.py's `comparison_sums`), to say how wide a typical line
// is, which the placeholder's width is set from.
import fs from "node:fs";
import http from "node:http";
import { createRequire } from "node:module";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

// The SDK's age builder over the ages a fake plays (sdk-ref-fixture.js), its source
// interpolated into a page script, so a page draws the labels the session chose.
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
const near = (a, b) =>
  typeof a === "number" && typeof b === "number" && Math.abs(a - b) <= TOLERANCE_PX;
const started = Date.now();
const lap = (what) => process.stderr.write(`${Date.now() - started} ms: ${what}\n`);

const lists = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/github-pulls-panel-responses.json"), "utf8"),
);
const rowsOf = (rows) =>
  Array.isArray(rows)
    ? rows.map((row) => JSON.parse(row))
    : [rows.same_as].flat().flatMap((holder) => rowsOf(lists[holder].body.rows));
const stacks = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/github-stacks-responses.json"), "utf8"),
).shared.body;
// Both stacks need to fit the viewport for the geometry checks across pane widths.
const members = new Set(stacks.stacks.flatMap((stack) => stack.pulls));
const rows = [...rowsOf(lists.current.body.rows), ...rowsOf(lists.more_window.body.rows)].filter(
  (row) => members.has(row.number),
);
const open = rows.filter((row) => row.state === "open").length;
const ANSWERS = {
  list: {
    ...lists.current.body,
    rows,
    total: rows.length,
    repository_total: rows.length,
    catalog_fetched: rows.length,
    fetched: rows.length,
    filter_totals: { all: rows.length, open, closed: rows.length - open },
    next_after: null,
  },
  stacks,
  changes: JSON.parse(
    fs.readFileSync(path.join(root, "tests/fixtures/github-stack-change-responses.json"), "utf8"),
  ),
};
// This repository's stacks' lines, as `comparison_sums` summed them: the shortest, a median
// one, and the longest of 19.
const REAL_LINES = [
  { statuses: { modified: 37 }, additions: 366, deletions: 87 },
  { statuses: { added: 6, modified: 13 }, additions: 835, deletions: 57 },
  { statuses: { added: 22, modified: 43 }, additions: 13011, deletions: 456 },
  { statuses: { added: 28, modified: 98 }, additions: 20037, deletions: 761 },
  { statuses: { added: 58, modified: 205 }, additions: 49508, deletions: 4000 },
  {
    statuses: { added: 34, modified: 166, removed: 8, renamed: 10 },
    additions: 14943,
    deletions: 15476,
  },
  {
    statuses: { added: 299, modified: 292, removed: 2, renamed: 3 },
    additions: 136824,
    deletions: 5278,
  },
];

const SDK = [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
  "plugin-sdk.js",
  "plugin-sdk-views.js",
];
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>stack lines</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/github/styles.css">
<script>
  window.METABROWSER_SETTINGS = { SYNTAX_HIGHLIGHT_MAX_BYTES: 524288, SYNTAX_LANGUAGE_BY_BASENAME: {}, SYNTAX_LANGUAGE_BY_EXTENSION: {} };
  window.MetabrowserIcons = { copy: '<svg data-icon="copy"></svg>' };
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

// In the page: mount the panel at *width* in *theme* on the recorded answers, each stack
// change held until `window.__release()`, and return a reader of the headings' geometry.
const MOUNT = `async (width, theme, fresh = true) => {
  window.__panel?.dispose();
  // A fresh document: no stack line or comparison kept from an earlier mount.
  if (fresh) {
    // On a build with no stack lines there is nothing to clear, and the heading waits for none.
    (await import("/github/stack-lines.js").catch(() => null))?.documentStackLines.clear();
    (await import("/github/comparison-prefetch.js")).documentComparisons.clear();
  }
  document.documentElement.dataset.theme = theme;
  const answers = window.__answers ??= await (await fetch("/answers.json")).json();
  const panel = window.__module ??= await import("/github/pulls-panel.js");
  const held = [];
  const asked = window.__asked = [];
  window.__release = () => held.splice(0).forEach((release) => release());
  const respond = (body, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  window.fetch = async (route) => {
    const url = new URL(route, location.href);
    if (url.pathname === "/api/plugin/github/stack-change") {
      const number = Number(url.searchParams.get("number"));
      asked.push(number);
      await new Promise((resolve) => held.push(resolve));
      // A sweep may set #286's answer for itself: a long line, exact or estimated.
      const found = (number === 286 && window.__line286) || Object.values(answers.changes).find((answer) => answer.body.number === number) || answers.changes.not_stacked;
      return respond(found.body, found.status);
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
    ...(${agesFrom})(document, () => ({ label: "1m", className: "age-min" })),
    formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
    loadChangedFilesTree: () => Promise.resolve(window.MetabrowserChangedFilesTree),
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

// In the page: each stack's Stack Overview row's geometry and what it shows, read from its
// row's top, and the geometry and text of the stack's own row (`stack`).
const READ = `(() => {
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height };
  };
  const rowHeight = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height"));
  return Object.fromEntries([...document.querySelectorAll(".github-pulls-whole-row")].map((row) => {
    const heading = row.querySelector(".github-pulls-whole-line");
    const label = row.querySelector(".github-pulls-whole-title");
    const change = row.querySelector(".github-pulls-stack-change");
    const stackRow = document.querySelector('.github-pulls-stack-row[data-stack="' + row.dataset.stack + '"]');
    const stackLabel = stackRow.querySelector(".github-pull-stack-label");
    const pending = change.querySelector(".github-pulls-stack-change-pending");
    const line = change.querySelector(".change-line");
    const stats = change.querySelector(".change-line-stats");
    return [row.dataset.stack, {
      row: box(row), toggle: box(row.querySelector(".github-pulls-toggle")),
      heading: box(heading),
      stack: {
        row: box(stackRow), toggle: box(stackRow.querySelector(".github-pulls-toggle")),
        label: box(stackLabel), count: box(stackRow.querySelector(".github-pulls-stack-count")),
        age: box(stackRow.querySelector(".github-pulls-age")),
        labelCut: stackLabel.scrollWidth > stackLabel.clientWidth + 0.5,
        text: stackRow.textContent,
      },
      label: box(label), labelCut: label.scrollWidth > label.clientWidth + 0.5,
      change: box(change), pending: box(pending), pendingShown: pending !== null && getComputedStyle(pending).visibility === "visible",
      line: box(line), stats: box(stats), note: box(change.querySelector(".github-pulls-stack-change-note")),
      statsWhole: stats === null || stats.scrollWidth <= stats.clientWidth + 0.5,
      // The line counts no files by status (mb-lqkb).
      statuses: change.querySelectorAll(".change-line-statuses, .change-line-group, .file-change-status").length,
      text: change.textContent, name: row.getAttribute("aria-label"), rowHeight,
      headingLines: heading.scrollHeight,
    }];
  }));
})()`;

// In the page: the inks and weights of the line's parts in the heading, and of the same line
// drawn by the SDK in a plain block of the page, the component outside any host.
const INKS = `(() => {
  const parts = [".diff-stat-add", ".diff-stat-del"];
  const read = (host) => Object.fromEntries(parts.map((selector) => {
    const el = host?.querySelector(selector);
    const style = el ? getComputedStyle(el) : null;
    return [selector, style ? [style.color, style.fontWeight] : null];
  }));
  const heading = document.querySelector('.github-pulls-whole-row[data-stack="286"] .github-pulls-stack-change');
  const reference = document.getElementById("reference");
  const answers = window.__answers.changes.current.body;
  // The line totals alone, a zero one left out, as the heading draws them (mb-lqkb, mb-efum).
  const said = window.metabrowser.changeLine({
    statuses: [], additions: answers.additions, deletions: answers.deletions,
  });
  reference.replaceChildren(...window.metabrowser.changeLineNodes(said));
  const dot = heading?.querySelector(":scope > .summary-punctuation");
  const probe = document.createElement("span");
  probe.style.color = "var(--muted)";
  document.body.append(probe);
  const muted = getComputedStyle(probe).color;
  probe.remove();
  return { heading: read(heading), reference: read(reference), dot: dot ? getComputedStyle(dot).color : null, muted, text: heading?.textContent ?? null, said: said.text };
})()`;

// In the page: how wide each real stack's line totals are in the heading's type, the room
// the placeholder holds after the dot's.
const REAL = `((lines) => {
  const host = document.createElement("span");
  host.className = "github-pulls-stack-change";
  // Outside any row, at its own widest: the heading's type, the nav's.
  host.style.cssText = "position:absolute;visibility:hidden;width:max-content";
  document.getElementById("reference").append(host);
  const widths = lines.map((line) => {
    const said = window.metabrowser.changeLine({
      statuses: [], additions: line.additions, deletions: line.deletions,
    });
    host.replaceChildren(...window.metabrowser.countPartsNodes([{ separator: "·" }]), ...window.metabrowser.changeLineNodes(said));
    const em = parseFloat(getComputedStyle(host).fontSize);
    const width = host.querySelector(".change-line").getBoundingClientRect().width;
    const round = (value) => Math.round(value * 100) / 100;
    return { text: said.text, px: round(width), em: round(width / em) };
  });
  const pending = document.querySelector(".github-pulls-stack-change-pending > .tally-pending");
  host.remove();
  return { widths, placeholder: pending ? pending.getBoundingClientRect().width : null };
})`;

const WIDTHS = [420, 380, 340, 299, 260, 220, 200, 180];
const THEMES = ["light", "dark"];

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
  try {
    await browser.send("Runtime.enable");
    await browser.send("Page.enable");
    await browser.send("Page.navigate", { url: `http://127.0.0.1:${server.address().port}/` });
    await browser.waitFor(
      `document.readyState === "complete" && Boolean(window.metabrowser?.changeLine)`,
    );
    await browser.evaluate(
      `Promise.all([...document.fonts].map((face) => face.load().catch(() => null))).then(() => document.fonts.ready).then(() => true)`,
    );
    lap("the page loaded");
    for (const theme of THEMES) {
      for (const width of WIDTHS) {
        const at = `${width} px ${theme}`;
        await browser.evaluate(`(${MOUNT})(${width}, ${JSON.stringify(theme)})`);
        const pending = (stack) =>
          `document.querySelector('.github-pulls-whole-row[data-stack="${stack}"] .github-pulls-stack-change-pending')`;
        const waited = (condition) =>
          browser.waitFor(condition, 5000).then(
            () => true,
            () => false,
          );
        // The list draws #290 first, so its read is sent first, and its heading waits; #286's,
        // queued behind it, does not. A build that draws no line draws no placeholder either,
        // and fails here.
        const first = await waited(`${pending(290)} !== null`);
        check(`${at}: #290's heading holds a placeholder while its read is on its way`, first);
        if (!first) {
          lap(`${at}: no placeholder`);
          continue;
        }
        const queued = await browser.evaluate(
          `({ pending: ${pending(286)} === null, asked: window.__asked.join(",") })`,
        );
        check(
          `${at}: #286's heading, its read queued behind #290's, holds no placeholder`,
          queued.pending && queued.asked === "290",
          JSON.stringify(queued),
        );
        await browser.evaluate(`window.__release(), true`);
        // #290's answer has no line; #286's read is sent, and its heading waits in its turn.
        const waits = await waited(`${pending(286)} !== null && ${pending(290)} === null`);
        check(`${at}: #286's heading holds a placeholder while its read is on its way`, waits);
        if (!waits) {
          lap(`${at}: no placeholder for #286`);
          continue;
        }
        await browser.evaluate(`new Promise((resolve) => setTimeout(resolve, 120))`);
        const before = await browser.evaluate(READ);
        await browser.evaluate(`window.__release(), true`);
        // The lane reads one stack at a time, so release each read as it is asked for.
        await browser.waitFor(
          `(window.__release(), document.querySelector('.github-pulls-whole-row[data-stack="286"] .change-line') !== null && document.querySelector('.github-pulls-whole-row[data-stack="290"] .github-pulls-stack-change').childNodes.length === 0)`,
        );
        await browser.evaluate(
          `new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))`,
        );
        const after = await browser.evaluate(READ);
        const inks = await browser.evaluate(INKS);
        if (process.env.SHOTS_DIR) {
          // The pane's first rows, to look at: the heading as it arrived.
          const shot = await browser.send("Page.captureScreenshot", {
            format: "png",
            clip: { x: 0, y: 0, width: width + 16, height: 360, scale: 2 },
          });
          fs.writeFileSync(
            path.join(process.env.SHOTS_DIR, `stack-lines-${theme}-${width}.png`),
            Buffer.from(shot.data, "base64"),
          );
        }
        measured[at] = { before: before["286"], after: after["286"], inks };
        const [was, now] = [before["286"], after["286"]];
        check(
          `${at}: #286 waits in a placeholder past the quiet period`,
          was?.pendingShown === true,
        );
        // Where the placeholder is: on the heading's line, or wrapped out of view where a
        // typical line's floor has no room, never across the label.
        const waitedInView =
          was.pending.top >= was.heading.top - TOLERANCE_PX &&
          was.pending.bottom <= was.heading.bottom + TOLERANCE_PX;
        check(
          `${at}: the placeholder is on the heading's line or out of view`,
          waitedInView !== was.change.top >= was.heading.bottom - TOLERANCE_PX,
          JSON.stringify({ pending: was.pending, heading: was.heading }),
        );
        if (waitedInView) {
          check(
            `${at}: the placeholder starts after the label`,
            was.pending.left >= was.label.right - TOLERANCE_PX,
          );
        }
        // The row and its words stay; its chevron follows the line, as a pull request's
        // row's does, so it alone moves (mb-odt4).
        for (const part of ["row", "label"]) {
          check(
            `${at}: #286's ${part} does not move when its line arrives`,
            ["left", "top", "width", "height"].every((side) =>
              near(was?.[part]?.[side], now?.[part]?.[side]),
            ),
            `${JSON.stringify(was?.[part])} ${JSON.stringify(now?.[part])}`,
          );
        }
        // The stack's own row is whole from its first paint, its count and its age with it,
        // and a line's arrival moves and changes nothing of it (mb-tvhs).
        for (const stack of ["286", "290"]) {
          for (const part of ["row", "toggle", "label", "count", "age"]) {
            check(
              `${at}: Stack #${stack}'s own ${part} does not move when a line arrives`,
              ["left", "top", "width", "height"].every((side) =>
                near(before[stack]?.stack?.[part]?.[side], after[stack]?.stack?.[part]?.[side]),
              ),
              `${JSON.stringify(before[stack]?.stack?.[part])} ${JSON.stringify(after[stack]?.stack?.[part])}`,
            );
          }
          check(
            `${at}: Stack #${stack}'s own row says the same before and after`,
            before[stack]?.stack?.text === after[stack]?.stack?.text &&
              /^Stack #\d+· \d+ pulls?/.test(after[stack]?.stack?.text ?? ""),
            JSON.stringify([before[stack]?.stack?.text, after[stack]?.stack?.text]),
          );
          check(
            `${at}: Stack #${stack}'s own row is one row tall, its label whole and its age after the pull count`,
            near(after[stack].stack.row.height, after[stack].rowHeight) &&
              !after[stack].stack.labelCut &&
              after[stack].stack.age.right <= after[stack].stack.row.right + TOLERANCE_PX &&
              (after[stack].stack.age.top > after[stack].stack.count.top + TOLERANCE_PX ||
                near(after[stack].stack.age.left - after[stack].stack.count.right, 6)),
            JSON.stringify(after[stack].stack),
          );
        }
        for (const stack of ["286", "290"]) {
          const each = after[stack];
          check(
            `${at}: #${stack}'s row is one row tall`,
            near(each.row.height, each.rowHeight),
            `${each.row.height}`,
          );
          check(`${at}: #${stack}'s label is whole`, !each.labelCut);
        }
        check(
          `${at}: #290 shows no line and no placeholder`,
          after["290"].text === "" && after["290"].pending === null,
        );
        // The line never wraps (the owner's word of 2026-11-26): it is on the heading's line,
        // whole or, where the row has no room, cut short at its box's edge with an ellipsis,
        // as a pull request's lines are, and the chevron right after that edge.
        const shown =
          now.line !== null &&
          now.line.top >= now.heading.top - TOLERANCE_PX &&
          now.line.bottom <= now.heading.bottom + TOLERANCE_PX &&
          now.change.top >= now.heading.top - TOLERANCE_PX &&
          now.change.bottom <= now.heading.bottom + TOLERANCE_PX;
        const whole = shown && now.line.right <= now.change.right + TOLERANCE_PX;
        check(
          `${at}: #286's line is on its heading's line`,
          shown,
          JSON.stringify({ line: now.line, change: now.change, heading: now.heading }),
        );
        check(
          `${at}: the chevron is right after the line's box, on the heading's line`,
          shown &&
            Math.abs(now.toggle.left - now.change.right - 3.25) <= 1.5 &&
            now.toggle.top >= now.heading.top - TOLERANCE_PX &&
            now.toggle.bottom <= now.heading.bottom + TOLERANCE_PX &&
            now.toggle.right <= now.heading.right + TOLERANCE_PX,
          JSON.stringify({ toggle: now.toggle, change: now.change, heading: now.heading }),
        );
        if (whole) {
          if (waitedInView) {
            check(
              `${at}: the line starts where its placeholder did, after the dot's room`,
              near(now.change.left, was.change.left) && near(now.line.left, was.pending.left),
              `${now.line.left} ${was.pending.left}`,
            );
          }
          check(
            `${at}: the line starts after the label`,
            now.change.left >= now.label.right - TOLERANCE_PX,
          );
          check(
            `${at}: its totals are whole and in the row, and start the line`,
            now.statsWhole &&
              now.stats.right <= now.heading.right + TOLERANCE_PX &&
              near(now.stats.left, now.line.left),
            JSON.stringify({ stats: now.stats, line: now.line }),
          );
          check(
            `${at}: the name says the line's totals in words`,
            now.name === "Stack Overview, Stack #286: 5 lines added",
            now.name,
          );
          for (const [part, ink] of Object.entries(inks.reference)) {
            check(
              `${at}: ${part} is the component's ink and weight`,
              JSON.stringify(inks.heading[part]) === JSON.stringify(ink),
              `${JSON.stringify(inks.heading[part])} ${JSON.stringify(ink)}`,
            );
          }
          check(
            `${at}: the dot before the line is muted`,
            inks.dot === inks.muted,
            `${inks.dot} ${inks.muted}`,
          );
        }
        measured[at].shown = whole ? "whole" : "cut";
        check(
          `${at}: the line counts no files by status`,
          now.statuses === 0 && after["290"].statuses === 0,
          JSON.stringify({ text: now.text }),
        );
        measured[at].waited = waitedInView ? "in view" : "out of view";
        if (width === 299) {
          // The Pulls tab mounted again in the document: the line is in its first paint, from
          // the document's keep, with no read and no placeholder.
          await browser.evaluate(`(${MOUNT})(${width}, ${JSON.stringify(theme)}, false)`);
          await browser.waitFor(
            `document.querySelectorAll(".github-pulls-stack-row").length === 2`,
          );
          const again = await browser.evaluate(READ);
          check(
            `${at}: mounted again, its line is drawn at once`,
            again["286"].text === now.text && again["286"].pending === null,
            again["286"].text,
          );
          // Past the browser's idle time: neither stack is read again, and #290's heading,
          // whose answer had no line, does not wait again.
          await browser.evaluate(`new Promise((resolve) => setTimeout(resolve, 400))`);
          const later = await browser.evaluate(READ);
          const reread = await browser.evaluate(`window.__asked.join(",")`);
          check(
            `${at}: mounted again, nothing is read and no heading waits`,
            reread === "" && later["290"].pending === null && later["290"].text === "",
            JSON.stringify({ reread, pending: later["290"].pending }),
          );
        }
        lap(`${at}: waited ${measured[at].waited}, line ${measured[at].shown}`);
      }
    }
    check(
      "the line shows whole at the widest pane",
      measured["420 px light"]?.shown === "whole",
      JSON.stringify(measured["420 px light"]?.shown),
    );
    // A long line, exact and then estimated (review A on #529, H2 and L1): while
    // "(estimated)" shows, the totals before it are whole and it follows them at the line's
    // gap; it gives way whole before the line does, leaving no blank run; and the estimated
    // line goes from view at the widths where the exact one does.
    const long = (exact) => ({
      status: 200,
      body: {
        ...ANSWERS.changes.inexact.body,
        files: 43,
        additions: 1234,
        deletions: 567,
        exact,
        statuses: [
          { status: "added", count: 21 },
          { status: "removed", count: 7 },
          { status: "modified", count: 15 },
        ],
      },
    });
    const states = { exact: {}, estimated: {} };
    for (const [kind, exact] of [
      ["exact", true],
      ["estimated", false],
    ]) {
      await browser.evaluate(`(window.__line286 = ${JSON.stringify(long(exact))}, true)`);
      for (const width of WIDTHS) {
        const at = `${width} px ${kind} long line`;
        await browser.evaluate(`(${MOUNT})(${width}, "light")`);
        await browser.waitFor(
          `(window.__release(), document.querySelector('.github-pulls-whole-row[data-stack="286"] .change-line') !== null)`,
        );
        await browser.evaluate(
          `new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))`,
        );
        const now = (await browser.evaluate(READ))["286"];
        const inView = (part) =>
          part !== null &&
          part.top >= now.heading.top - TOLERANCE_PX &&
          part.bottom <= now.heading.bottom + TOLERANCE_PX &&
          part.right <= now.change.right + TOLERANCE_PX;
        const shown = inView(now.line);
        const noteShown = inView(now.note);
        check(
          `${at}: the note is there exactly when the line is estimated`,
          (now.note !== null) === !exact,
        );
        const state = !shown ? "cut" : noteShown ? "whole, noted" : "whole";
        states[kind][width] = state;
        if (noteShown) {
          check(
            `${at}: the totals before "(estimated)" are whole`,
            shown && now.statsWhole && near(now.stats.left, now.line.left),
            JSON.stringify({ stats: now.stats, line: now.line }),
          );
          check(
            `${at}: "(estimated)" follows the totals at the line's gap, no blank run`,
            Math.abs(now.note.left - now.stats.right - 6) <= 1,
            JSON.stringify({ stats: now.stats, note: now.note }),
          );
        }
        if (shown) {
          check(
            `${at}: its totals start the line, and count no files by status`,
            near(now.stats.left, now.line.left) && now.statuses === 0,
            JSON.stringify({ stats: now.stats, line: now.line, text: now.text }),
          );
        }
        lap(`${at}: ${state}`);
      }
    }
    // A change of no lines (mb-efum): a muted "0 lines" at the line's weight, said "no lines
    // changed", and whole wherever the long exact line, which is wider, shows.
    await browser.evaluate(
      `(window.__line286 = ${JSON.stringify({ status: 200, body: { ...ANSWERS.changes.current.body, additions: 0, deletions: 0 } })}, true)`,
    );
    const noLines = {};
    for (const theme of THEMES) {
      for (const width of WIDTHS) {
        const at = `${width} px ${theme} no lines`;
        await browser.evaluate(`(${MOUNT})(${width}, ${JSON.stringify(theme)})`);
        await browser.waitFor(
          `(window.__release(), document.querySelector('.github-pulls-whole-row[data-stack="286"] .change-line') !== null)`,
        );
        await browser.evaluate(
          `new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))`,
        );
        const now = (await browser.evaluate(READ))["286"];
        const ink = await browser.evaluate(`(() => {
          const line = document.querySelector('.github-pulls-whole-row[data-stack="286"] .change-line');
          const none = line?.querySelector(".change-line-stats > .change-line-none") ?? null;
          const probe = document.createElement("span");
          probe.style.color = "var(--muted)";
          document.body.append(probe);
          const muted = getComputedStyle(probe).color;
          probe.remove();
          return {
            none: none ? [getComputedStyle(none).color, getComputedStyle(none).fontWeight] : null,
            line: line ? getComputedStyle(line).fontWeight : null,
            muted,
          };
        })()`);
        if (process.env.SHOTS_DIR && width === 299) {
          const shot = await browser.send("Page.captureScreenshot", {
            format: "png",
            clip: { x: 0, y: 0, width: width + 16, height: 360, scale: 2 },
          });
          fs.writeFileSync(
            path.join(process.env.SHOTS_DIR, `stack-lines-${theme}-${width}-no-lines.png`),
            Buffer.from(shot.data, "base64"),
          );
        }
        const shown =
          now.line !== null &&
          now.line.top >= now.heading.top - TOLERANCE_PX &&
          now.line.bottom <= now.heading.bottom + TOLERANCE_PX &&
          now.line.right <= now.change.right + TOLERANCE_PX;
        check(
          `${at}: the heading says "0 lines", and its name "no lines changed"`,
          now.text === "·0 lines" && now.name === "Stack Overview, Stack #286: no lines changed",
          JSON.stringify({ text: now.text, name: now.name }),
        );
        check(
          `${at}: "0 lines" is muted, at the line's weight`,
          ink.none !== null && ink.none[0] === ink.muted && ink.none[1] === ink.line,
          JSON.stringify(ink),
        );
        check(
          `${at}: "0 lines" is whole where it shows`,
          !shown || now.statsWhole,
          JSON.stringify({ stats: now.stats, line: now.line }),
        );
        check(
          `${at}: "0 lines" shows wherever the long exact line does`,
          states.exact[width] === "cut" || shown,
          JSON.stringify({ long: states.exact[width], shown }),
        );
        noLines[at] = shown ? "whole" : "cut";
        lap(`${at}: ${noLines[at]}`);
      }
    }
    await browser.evaluate(`(window.__line286 = null, true)`);
    measured.long = states;
    measured.noLines = noLines;
    const order = ["whole, noted", "whole", "cut"];
    const ranks = WIDTHS.map((width) => order.indexOf(states.estimated[width]));
    check(
      "the estimated line shows its note at the widest pane",
      states.estimated[420] === "whole, noted",
      JSON.stringify(states.estimated),
    );
    check(
      "the estimated line gives way note first, then the line, as the pane narrows",
      ranks.every((rank, index) => index === 0 || rank >= ranks[index - 1]),
      JSON.stringify(states.estimated),
    );
    check(
      "the estimated line goes from view at the widths where the exact one does",
      WIDTHS.every(
        (width) => (states.exact[width] === "cut") === (states.estimated[width] === "cut"),
      ),
      JSON.stringify(states),
    );
    measured.real = await browser.evaluate(`(${REAL})(${JSON.stringify(REAL_LINES)})`);
    check("no page error", errors.length === 0, errors.join("\n"));
  } finally {
    delete measured.inks;
    if (process.env.MEASURE_OUT) {
      fs.writeFileSync(process.env.MEASURE_OUT, `${JSON.stringify(measured, null, 1)}\n`);
    }
    await browser.close();
    server.close();
  }
  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.stdout.write(`stack lines in Chrome: ${failures.length} of ${checks} checks failed\n`);
    process.exit(1);
  }
  process.stdout.write(`stack lines in Chrome: ${checks} checks passed\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack ?? error}\n`);
  process.exit(1);
});
