// Each stack heading's brief change line in the Pulls tab, laid out by headless Chrome: the
// production panel module and its stylesheets, mounted on recorded answers.
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
// - nothing moves when the line arrives: the row, its chevron, its icon, its label, and the
//   placeholder's start, which is the line's;
// - the heading stays one line: the row is one `--ui-row-height`, and the line is either
//   whole on the heading's line, its totals whole and its statuses cut short at most, or out
//   of view entirely, never cut through its totals or across the label;
// - the line's inks and weights are the component's, part for part, as the same line drawn
//   by the SDK outside the heading resolves them in that theme;
// - #290's heading shows no line and no placeholder once its answer says it has none, and
//   in a Pulls tab mounted again nothing is read and no heading waits: a stack whose answer
//   had no line does not pulse and go blank again (review of #484, A4).
//
// It also lays out the brief change lines of this repository's own stacks
// (`REAL_LINES`, measured 2026-11-16 with pull_stack_change.py's `comparison_sums`), to say
// how wide a typical line is, which the placeholder's width is set from.
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

const lists = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/github-pulls-panel-responses.json"), "utf8"),
);
const rowsOf = (rows) =>
  Array.isArray(rows)
    ? rows.map((row) => JSON.parse(row))
    : [rows.same_as].flat().flatMap((holder) => rowsOf(lists[holder].body.rows));
const ANSWERS = {
  list: { ...lists.current.body, rows: rowsOf(lists.current.body.rows) },
  stacks: JSON.parse(
    fs.readFileSync(path.join(root, "tests/fixtures/github-stacks-responses.json"), "utf8"),
  ).shared.body,
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
      const found = Object.values(answers.changes).find((answer) => answer.body.number === number) ?? answers.changes.not_stacked;
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
    formatAge: () => ({ label: "1m", className: "age-min" }),
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

// In the page: each stack heading's geometry and what it shows, read from its row's top.
const READ = `(() => {
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height };
  };
  const rowHeight = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height"));
  return Object.fromEntries([...document.querySelectorAll(".github-pulls-stack-row")].map((row) => {
    const heading = row.querySelector(".github-pulls-stack-heading");
    const label = row.querySelector(".github-pull-stack-label");
    const change = row.querySelector(".github-pulls-stack-change");
    const pending = change.querySelector(".github-pulls-stack-change-pending");
    const line = change.querySelector(".change-line");
    const stats = change.querySelector(".change-line-stats");
    const statuses = change.querySelector(".change-line-statuses");
    return [row.dataset.stack, {
      row: box(row), toggle: box(row.querySelector(".github-pulls-toggle")),
      icon: box(row.querySelector(".github-pull-stack-icon")), heading: box(heading),
      label: box(label), labelCut: label.scrollWidth > label.clientWidth + 0.5,
      change: box(change), pending: box(pending), pendingShown: pending !== null && getComputedStyle(pending).visibility === "visible",
      line: box(line), stats: box(stats),
      statsWhole: stats === null || stats.scrollWidth <= stats.clientWidth + 0.5,
      statusesCut: statuses !== null && statuses.scrollWidth > statuses.clientWidth + 0.5,
      text: change.textContent, name: row.getAttribute("aria-label"), rowHeight,
      headingLines: heading.scrollHeight,
    }];
  }));
})()`;

// In the page: the inks and weights of the line's parts in the heading, and of the same line
// drawn by the SDK in a plain block of the page, the component outside any host.
const INKS = `(() => {
  const parts = [".summary-number", ".file-change-status", ".change-line-statuses > .summary-punctuation", ".change-line-group > .summary-punctuation", ".diff-stat-add", ".diff-stat-del"];
  const read = (host) => Object.fromEntries(parts.map((selector) => {
    const el = host?.querySelector(selector);
    const style = el ? getComputedStyle(el) : null;
    return [selector, style ? [style.color, style.fontWeight] : null];
  }));
  const heading = document.querySelector('.github-pulls-stack-row[data-stack="286"] .github-pulls-stack-change');
  const reference = document.getElementById("reference");
  const answers = window.__answers.changes.current.body;
  const tree = window.MetabrowserChangedFilesTree;
  const said = window.metabrowser.changeLine({
    statuses: tree.statusBreakdown(answers.statuses.flatMap((entry) => Array.from({ length: entry.count }, () => entry.status))),
    additions: answers.additions, deletions: answers.deletions,
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

// In the page: how wide each real stack's line is, the separator's dot with it, in the
// heading's type.
const REAL = `((lines) => {
  const tree = window.MetabrowserChangedFilesTree;
  const host = document.createElement("span");
  host.className = "github-pulls-stack-change";
  // Outside any row, at its own widest: the heading's type, the nav's.
  host.style.cssText = "position:absolute;visibility:hidden;width:max-content";
  document.getElementById("reference").append(host);
  const widths = lines.map((line) => {
    const said = window.metabrowser.changeLine({
      statuses: tree.statusBreakdown(Object.entries(line.statuses).flatMap(([status, count]) => Array.from({ length: count }, () => status))),
      additions: line.additions, deletions: line.deletions,
    });
    host.replaceChildren(...window.metabrowser.countPartsNodes([{ separator: "·" }]), ...window.metabrowser.changeLineNodes(said));
    const em = parseFloat(getComputedStyle(host).fontSize);
    const width = host.getBoundingClientRect().width;
    const stats = host.querySelector(".change-line-stats").getBoundingClientRect();
    // The floor: the dot, the gaps, and the totals, which the line keeps whole.
    const dot = host.querySelector(":scope > .summary-punctuation").getBoundingClientRect().width;
    const floor = dot + 12 + stats.width;
    const round = (value) => Math.round(value * 100) / 100;
    return { text: said.text, px: round(width), em: round(width / em), floorEm: round(floor / em) };
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
          `document.querySelector('.github-pulls-stack-row[data-stack="${stack}"] .github-pulls-stack-change-pending')`;
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
          `(window.__release(), document.querySelector('.github-pulls-stack-row[data-stack="286"] .change-line') !== null && document.querySelector('.github-pulls-stack-row[data-stack="290"] .github-pulls-stack-change').childNodes.length === 0)`,
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
        for (const part of ["row", "toggle", "icon", "label"]) {
          check(
            `${at}: #286's ${part} does not move when its line arrives`,
            ["left", "top", "width", "height"].every((side) =>
              near(was?.[part]?.[side], now?.[part]?.[side]),
            ),
            `${JSON.stringify(was?.[part])} ${JSON.stringify(now?.[part])}`,
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
        const shown =
          now.line !== null &&
          now.line.top >= now.heading.top - TOLERANCE_PX &&
          now.line.bottom <= now.heading.bottom + TOLERANCE_PX;
        const dropped = now.change.top >= now.heading.bottom - TOLERANCE_PX;
        check(
          `${at}: #286's line is on its heading's line or out of view`,
          shown !== dropped,
          JSON.stringify({ line: now.line, change: now.change, heading: now.heading }),
        );
        if (shown) {
          if (waitedInView) {
            check(
              `${at}: the line starts where its placeholder did`,
              near(now.change.left, was.change.left),
              `${now.change.left} ${was.change.left}`,
            );
          }
          check(
            `${at}: the line starts after the label`,
            now.change.left >= now.label.right - TOLERANCE_PX,
          );
          check(
            `${at}: its totals are whole and in the row`,
            now.statsWhole && now.stats.right <= now.heading.right + TOLERANCE_PX,
            JSON.stringify(now.stats),
          );
          check(
            `${at}: the name says the line in words`,
            now.name.startsWith("Stack #286: 1 added, 1 modified; 5 lines added, 0 deleted; "),
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
        measured[at].shown = shown ? (now.statusesCut ? "statuses cut" : "whole") : "dropped";
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
