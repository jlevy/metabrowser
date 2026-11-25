// Each Pulls row's lines (mb-d0a3, mb-85op, mb-lqkb, mb-zuy0), laid out by headless Chrome: the
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
// - each pull request's row is its link, its title's lines, one flow of the state icon on the
//   first line's start and the title, which wraps under the icon and is cut short at the second
//   line's end, one line tall for a title that fits it and two for any longer (mb-zuy0); then
//   its change line, which holds
//   the chevron in the icon slot under the state icon, the number's line in the title's column,
//   the number, the author, and the lines changed, and the age at the row's end; the link holds
//   no chevron;
// - nothing moves when the lines arrive: the item, the link, the title's two lines, the change
//   line, the chevron, the state icon, the number, the age, and the placeholder's start, which is
//   the lines';
// - the change line stays one line: the number whole, and the lines whole or out of view, never
//   cut short, and out of view only where the number leaves them no room; the author gives way
//   before them; the line counts no files by status; nothing scrolls sideways;
// - the lines' inks and weights are the component's, part for part, as the same line drawn by
//   the SDK outside the row resolves them in that theme, and its item's name says it in words;
// - #104 and #103, whose lists cannot be had, show the chevron, the number, and the author, and no
//   lines and no placeholder, once answered;
// - the open row's highlight is its item's: one ground under its three lines, and its left bar
//   down the link's and the change line's edge.
//
// At 299 px, the default pane, in each theme, with real pointer and keyboard input, it holds
// that a pull request's lines are one item (mb-1z7j): the pointer on any of them hovers
// the item's one ground, and on the change line, the line with the toggle, the chevron's plate
// too, the inner target's own hover, which the link's lines never show; Tab's stop is the
// row's link, whose ring is drawn round the whole item, and the change line is no stop. A
// press on a row's title opens the pull request and expands nothing; a press on the number, on
// the author, on the chevron, and on the lines, each on the change line, opens or closes the
// files under it, and opens no page (docs/design-system.md, "A Click on the Toggle's Line
// Toggles"). The keys
// need the shell's registry, which this page has not: tests/dom/github-pulls-stacks-chrome.mjs
// holds them in the running app; here the handle's `expand` and `collapse`, which Right and
// Left call, act on the focused item. With SHOTS_DIR set, it saves the item's hover and the
// inner target's, at 299 px in each theme.
//
// It then mounts the rows again, in each theme at every width, with #106's change of no lines
// and #105's of additions alone (mb-efum): a zero total is left out, "+3", and no lines are a
// muted "0 lines" at the line's weight, whole wherever #106's recorded line is shown.
//
// It also lays out the lines changed of this repository's own pull requests (`REAL_LINES`), to
// say how wide a typical row's lines are, which the placeholder's width is judged against, and
// their titles (`REAL_TITLES`) in a closed row at every width, to say how tall a typical row
// is, which `ROW_ESTIMATE_PX` is held to.
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
// Titles of three lengths among the rows checked: #106's and #104's are one line, #105's runs
// past two lines at every width, and #103's is one unbroken word longer than the row.
const TITLES = {
  105: "feat(pulls): keep a stack member's place before its title, and let a long title run to a second line under the state icon before it is cut short at that line's end",
  103: "docs:" + "x".repeat(160),
};
const ANSWERS = {
  list: {
    ...lists.current.body,
    rows: rowsOf(lists.current.body.rows).map((row) =>
      row.number in TITLES ? { ...row, title: TITLES[row.number] } : row,
    ),
  },
  stacks: fixture("github-stacks-responses.json").empty.body,
  summed: fixture("github-pull-files-summary-responses.json").summed.body,
  // A row's list of changed files, once its chevron opens it: the recorded two-file list.
  files: { ...twoFiles, rows: twoFiles.rows.map((row) => JSON.parse(row)) },
};
// The rows the checks read: two with a line, one whose list is not cached, one filling.
const SHOWN = [106, 105];
const NONE = [104, 103];
const OPEN = 105;

const REAL_TITLES = [
  [440, "plan: documentation from first principles"],
  [
    441,
    "docs(perf): the next campaigns' plan, every hypothesis current, and a committed paced-series driver",
  ],
  [
    442,
    "perf(transitions): recorder revision 6, the readings the next stage needs and the three open recorder bugs",
  ],
  [
    444,
    "Menus: one group pattern at the row inset, and filter menus that fit their rows and the window (mb-s6vu, mb-1wfn)",
  ],
  [445, "Files: Group by as the filter row's one control, with age and type sections (mb-sogv)"],
  [447, "fix(diff): a rendered Markdown fold expands in place with no box (mb-m5dd)"],
  [448, "feat(diff): a Diff summary of changed files, on the Pulls tree's shared model (mb-epw2)"],
  [449, "perf(diff): answer a commit comparison with two git processes, not four (H116)"],
  [450, "feat(github): group the Pulls tab by native stack, in one stack design (mb-cm61)"],
  [451, "Conversation: commits read like comments, joined by a timeline line (mb-g3ao)"],
  [452, "docs: rebuild the documentation from first principles"],
  [453, "plan: one object data model with several views"],
  [
    455,
    "perf(server): encode stamped assets once, and send uncompressed to the app's own loopback client (H115), with U2's server-time instrument",
  ],
  [456, "fix(styles): h2 upright wherever the prose face is sans (mb-l4vm)"],
  [
    457,
    "feat(keys): Control-N and Control-P walk a stack, and P opens the Pulls tab (mb-lnqj, mb-6rfu)",
  ],
  [458, "fix(nav): navigation toolbars wrap when the pane is narrow (mb-nm4z)"],
  [
    459,
    "feat(files): Group by reads By age and By file type, takes A, T, and N, and opens with focus (mb-4mir, mb-ibo4, mb-spqw)",
  ],
  [460, "fix(tooltips): a tooltip only adds information; the Pulls column has none (mb-8mpo)"],
  [461, "fix(github): one Conversation rhythm, and headings that read alike (mb-w7rt, mb-novh)"],
  [462, "feat(titles): a conventional-commit prefix is regular and the rest bold (mb-z57p)"],
  [
    463,
    "fix: make the Files tab, stack menu, changed-file rows and GitHub tokens follow the design system (mb-xlla)",
  ],
  [464, "feat(nav): navigating to an item reveals it in the nav pane by every route (mb-6y0g)"],
  [465, "feat(github): color label chips as github.com does (mb-9qob)"],
  [
    466,
    "perf(files): Group by reads every group in one pass and shows a choice while it waits (mb-navs, mb-75l5)",
  ],
  [467, "docs: bring the docs and CHANGELOG to the consistency pass's final state (mb-vg55)"],
  [468, "chore(policy): grant github-stacked-prs and github-workflows"],
  [
    469,
    "feat(github): a Pulls row reads its number's line first and its whole title second (mb-lkkt)",
  ],
  [470, "feat(diff): one Diff summary at the top of the commit and pull request pages (mb-pb35)"],
  [
    471,
    "feat(github): cache each repository's label set so every chip is colored on first paint (mb-varu)",
  ],
  [
    472,
    "fix(diff): the Diff summary opens in the page's flow, one step in from its header (mb-hi4l)",
  ],
  [
    473,
    "fix: a group heading's tally sits beside it, and a stack heading has none (mb-mcjd, mb-yk0i)",
  ],
  [
    474,
    "fix(diff): no rule under the layout chooser, and every count summary's numbers are bold (mb-a073, mb-roa9)",
  ],
  [475, "fix(fonts): keep one monospace face across the shell and KPress documents"],
  [
    476,
    "fix(github): the pull request header's freshness line is a metadata line, and its Diff summary row holds the pending placeholder (mb-2u08, mb-onr2)",
  ],
  [477, "feat(nav): the folder name goes home, with every tab reset; 0 does the same (mb-5lzl)"],
  [
    478,
    "perf(github): a pull request's comparison is cached and prefetched, so a revisit never waits (mb-neg9)",
  ],
  [
    479,
    'feat(diff): the Diff summary reads "N files changed" with colored status letters (mb-vb51)',
  ],
  [480, "fix(markdown): keep sanitizer diagnostics out of the reader's disclosure"],
  [
    481,
    "fix(files): repaints elsewhere leave the pending tooltip, so a tree row's tooltip shows under load (mb-alff)",
  ],
  [482, "build(deps): raise kpress to 0.3.6"],
  [
    484,
    "feat(github): each stack heading in the Pulls column shows its brief change line (mb-9ekj)",
  ],
  [485, "plan: publishing setup for the macOS app (signing, notarization, DMG, install checks)"],
  [486, "fix: the whole-stack review's follow-ups for stack #446 (B1 to B11 of review B on #478)"],
  [487, "feat(ui): one page header for the commit and pull request pages"],
  [488, "test(faces): read each probe's text in the pane, not in the shell's stage (mb-nvo0)"],
];

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
  // A sweep may set a row's totals for itself (\`window.__rowTotals\`, by number).
  const summed = new Map(answers.summed.rows.map((row) => [row.number, { ...row, ...window.__rowTotals?.[row.number] }]));
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
    const heading = row.querySelector(".github-pulls-heading");
    const title = row.querySelector(".github-pulls-title");
    const meta = change?.querySelector(".github-pulls-meta") ?? null;
    const flow = meta?.querySelector(".github-pulls-line") ?? null;
    const line = flow?.querySelector(".github-pulls-change-line") ?? null;
    const by = flow?.querySelector(".github-pulls-by") ?? null;
    const pending = line?.querySelector(".github-pulls-change-pending") ?? null;
    const said = line?.querySelector(".change-line") ?? null;
    const stats = said?.querySelector(".change-line-stats") ?? null;
    const toggle = change?.querySelector(".github-pulls-toggle") ?? null;
    const style = getComputedStyle(row);
    // The title's lines, from its fragments' rects, a line's at one top: those whose top is
    // inside the heading's box are the lines drawn, and the rest are past the clamp.
    const tops = new Map();
    for (const rect of title?.getClientRects() ?? []) {
      if (rect.width === 0) continue;
      const top = Math.round(rect.top * 2) / 2;
      const seen = tops.get(top);
      tops.set(top, seen ? { left: Math.min(seen.left, rect.left), top, right: Math.max(seen.right, rect.right) } : { left: rect.left, top, right: rect.right });
    }
    const lines = [...tops.values()].sort((a, b) => a.top - b.top);
    rows[number] = {
      item: box(item), row: box(row), heading: box(heading), title: box(title),
      lh: heading ? parseFloat(getComputedStyle(heading).lineHeight) : null,
      padTop: parseFloat(style.paddingTop), padBottom: parseFloat(style.paddingBottom),
      // The link's floor, the shell's row height, which a title of one line sits inside.
      minHeight: parseFloat(style.minHeight) || 0,
      titleLines: lines, clamped: heading !== null && heading.scrollHeight > heading.clientHeight + 1,
      icon: box(row.querySelector(".github-pull-state-icon")),
      place: box(row.querySelector(".github-pulls-place")),
      rowToggles: row.querySelectorAll(".github-pulls-toggle").length,
      inset: inset(row), changeInset: inset(change),
      slot: parseFloat(style.getPropertyValue("--tree-icon-slot")), gap: parseFloat(style.columnGap),
      change: box(change), toggle: box(toggle), chevron: box(toggle?.querySelector("svg")),
      meta: box(meta), number: box(meta?.querySelector(".github-pulls-number") ?? null),
      flow: box(flow), by: box(by), age: box(change?.querySelector(".github-pulls-age") ?? null),
      changeLine: box(line), pending: box(pending), block: box(pending?.querySelector(".tally-pending")),
      pendingShown: pending !== null && getComputedStyle(pending).visibility === "visible",
      line: box(said), stats: box(stats), said: said?.textContent ?? null,
      statsWhole: stats === null || stats.scrollWidth <= stats.clientWidth + 0.5,
      // The line counts no files by status (mb-lqkb).
      statuses: said?.querySelectorAll(".change-line-statuses, .change-line-group, .file-change-status").length ?? 0,
      text: line?.textContent ?? null, nodes: line?.childNodes.length ?? null,
      // The change line is the pointer's alone, hidden from assistive technology; its words,
      // hidden too, describe the row, which alone says whether its files are open.
      hidden: change?.getAttribute("aria-hidden") ?? null,
      words: document.getElementById(row.getAttribute("aria-describedby") ?? "")?.textContent ?? null,
      expanded: row.getAttribute("aria-expanded"),
      files: box(item.querySelector(".github-pull-files")),
    };
  }
  return { rows, scroll: [pane.scrollWidth, pane.clientWidth] };
})()`;

// In the page: the inks and weights of the line's parts in #106's row, and of the same line
// drawn by the SDK in a plain block of the page, the component outside any host; the name the
// SDK gives it; and the open row's highlight: its item's ground, and the bar on its link and
// its change line.
const INKS = `(() => {
  const parts = [".diff-stat-add", ".diff-stat-del"];
  const read = (host) => Object.fromEntries(parts.map((selector) => {
    const el = host?.querySelector(selector);
    const style = el ? getComputedStyle(el) : null;
    return [selector, style ? [style.color, style.fontWeight] : null];
  }));
  const host = document.querySelector('.github-pulls-change[data-number="106"] .github-pulls-change-line');
  const reference = document.getElementById("reference");
  const summary = window.__answers.summed.rows.find((row) => row.number === 106);
  // The line totals alone, a zero one left out, as the row draws them (mb-lqkb, mb-efum).
  const said = window.metabrowser.changeLine({
    statuses: [], additions: summary.additions, deletions: summary.deletions,
  });
  reference.replaceChildren(...window.metabrowser.changeLineNodes(said));
  const open = document.querySelector('a.github-pulls-row[data-number="${OPEN}"]');
  const openChange = document.querySelector('.github-pulls-change[data-number="${OPEN}"]');
  const other = document.querySelector('.github-pulls-change[data-number="104"]');
  const ground = (el) => el ? getComputedStyle(el).backgroundColor : null;
  const bar = (el) => el ? [getComputedStyle(el).borderLeftColor, getComputedStyle(el).borderLeftWidth] : null;
  return {
    row: read(host), reference: read(reference), text: reference.textContent, label: said.label,
    highlight: {
      selected: open?.classList.contains("selected") ?? false,
      item: ground(open?.parentElement), row: [ground(open), ...bar(open)], change: [ground(openChange), ...bar(openChange)],
      other: [ground(other?.parentElement), ...bar(other)],
    },
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

// In the page: how tall each real pull request's closed row is at the pane's width, its title in
// a copy of #104's row, drawn and gone at once, and how many of its titles take one line.
const REAL_ROWS = `((titles) => {
  const item = document.querySelector('li.github-pulls-item[data-number="104"]');
  const round = (value) => Math.round(value * 100) / 100;
  const rows = titles.map(([number, title]) => {
    const copy = item.cloneNode(true);
    copy.removeAttribute("data-number");
    copy.querySelector(".github-pulls-title").textContent = title;
    item.parentElement.append(copy);
    const heading = copy.querySelector(".github-pulls-heading");
    const lh = parseFloat(getComputedStyle(heading).lineHeight);
    const row = { number, height: round(copy.getBoundingClientRect().height), lines: Math.round(heading.getBoundingClientRect().height / lh) };
    copy.remove();
    return row;
  });
  const heights = rows.map((row) => row.height);
  return {
    n: rows.length,
    lh: parseFloat(getComputedStyle(item.querySelector(".github-pulls-heading")).lineHeight),
    mean: round(heights.reduce((sum, height) => sum + height, 0) / rows.length),
    min: Math.min(...heights),
    max: Math.max(...heights),
    oneLine: rows.filter((row) => row.lines === 1).length,
    twoLines: rows.filter((row) => row.lines === 2).length,
  };
})`;

// In the page: how wide each real pull request's lines changed are in the change line's type,
// whole, as the row draws them, its totals alone.
const REAL = `((lines) => {
  const container = document.querySelector(".github-pulls-meta");
  const host = document.createElement("span");
  // Beside the rows, at its own widest: the change line's type, the nav's.
  host.style.cssText = "position:absolute;visibility:hidden;width:max-content;white-space:nowrap;font-size:var(--nav-font-size)";
  document.getElementById("pane").append(host);
  const em = parseFloat(getComputedStyle(host).fontSize);
  const round = (value) => Math.round(value * 100) / 100;
  const widths = lines.map(([number, _added, _modified, _removed, _renamed, additions, deletions]) => {
    const said = window.metabrowser.changeLine({ statuses: [], additions, deletions });
    host.replaceChildren(...window.metabrowser.changeLineNodes(said));
    const width = host.querySelector(".change-line").getBoundingClientRect().width;
    return { number, text: said.text, px: round(width), em: round(width / em) };
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
    em, font, n: widths.length, em_: summary("em"),
    shortest: byWidth[0], median: byWidth[Math.floor(byWidth.length / 2)], longest: byWidth[byWidth.length - 1],
    widths,
  };
})`;

const WIDTHS = [420, 380, 340, 299, 260, 220, 200, 180];
// The default pane's width, where the hover and the focus are held.
const DEFAULT_PANE = 299;
const THEMES = ["light", "dark"];
const PARTS = [
  "item",
  "row",
  "heading",
  "title",
  "icon",
  "change",
  "toggle",
  "chevron",
  "meta",
  "number",
  "age",
  "flow",
];

/** Whether *r*'s parts are its lines: the link's one or two of title, and the change line. */
function threeLines(r) {
  if (!r?.change || !r.toggle || !r.chevron || !r.heading || !r.meta || !r.number || !r.age) {
    return { ok: false, why: "a part is missing" };
  }
  const within = (inner, outer) =>
    inner.top >= outer.top - TOLERANCE_PX && inner.bottom <= outer.bottom + TOLERANCE_PX;
  const first = r.titleLines[0];
  // The lines the title takes, one for a title that fits the first line, and two for any
  // longer, cut short at the second (mb-zuy0).
  const shown = Math.min(2, r.titleLines.length);
  const parts = {
    // The link is the title's lines, as tall as they are (mb-85op, mb-zuy0), and no shorter
    // than the shell's row, which a title of one line sits inside.
    titleLines:
      shown > 0 &&
      near(r.heading.height, shown * r.lh) &&
      near(r.row.height, Math.max(r.minHeight, r.padTop + shown * r.lh + r.padBottom)),
    // The state icon leads the first line, on the row's inset in the one icon slot (mb-3vil),
    // centered on the first line's box; the title starts one column gap after it.
    iconOnFirst: near(r.icon.top, r.heading.top) && near(r.icon.height, r.lh),
    iconOnInset: near(r.icon.left, r.inset) && near(r.icon.width, r.slot),
    titleAfterIcon:
      first !== undefined &&
      near(first.top, r.heading.top) &&
      near(first.left, r.icon.right + r.gap),
    // No stack in this list: no place, and no bullet.
    noPlace: r.place !== null && r.place.width === 0,
    noLinkChevron: r.rowToggles === 0,
    // The change line is under the link, and the item is the two.
    changeUnder: r.change.top >= r.row.bottom - TOLERANCE_PX,
    itemIsBoth: near(r.item.height, r.row.height + r.change.height),
    // The chevron is on the change line, in the row's one slot under the state icon, and the
    // number's line in the text column, one column gap after the chevron's slot (mb-3vil).
    chevronOnThird: within(r.chevron, r.change) && within(r.toggle, r.change),
    chevronUnderIcon:
      near(r.toggle.left, r.changeInset) &&
      near(r.toggle.width, r.slot) &&
      near(r.changeInset, r.inset) &&
      near(r.toggle.left, r.icon.left),
    numberInTextColumn:
      near(r.meta.left, r.toggle.right + r.gap) && near(r.number.left, r.meta.left),
    // The number, the age, and what shows of the author and the lines are on the third line.
    oneLine:
      within(r.meta, r.change) &&
      within(r.number, r.change) &&
      within(r.age, r.change) &&
      r.number.right <= r.meta.right + TOLERANCE_PX &&
      r.age.left >= r.meta.right - TOLERANCE_PX &&
      r.age.right <= r.change.right + TOLERANCE_PX,
  };
  return { ok: Object.values(parts).every(Boolean), parts };
}

/** Whether *part* of the number's line, its box *b*, is on the line in view or past it. */
function onLine(r, b) {
  if (b === null) {
    return "none";
  }
  if (b.top >= r.flow.top - TOLERANCE_PX && b.bottom <= r.flow.bottom + TOLERANCE_PX) {
    return b.right <= r.flow.right + TOLERANCE_PX ? "shown" : "cut";
  }
  return b.top >= r.flow.bottom - TOLERANCE_PX ? "dropped" : "cut";
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
  /** An element's node in Chrome's accessibility tree, as assistive technology reads it. */
  const axOf = async (selector) => {
    const { result: handle } = await browser.send("Runtime.evaluate", {
      expression: `document.querySelector(${JSON.stringify(selector)})`,
    });
    if (!handle?.objectId) {
      return null;
    }
    const { nodes } = await browser.send("Accessibility.getPartialAXTree", {
      objectId: handle.objectId,
      fetchRelatives: false,
    });
    const node = nodes?.[0];
    return node === undefined
      ? null
      : {
          role: node.role?.value ?? null,
          name: node.name?.value ?? null,
          description: node.description?.value ?? null,
          ignored: node.ignored === true,
          reasons: node.ignoredReasons?.map((reason) => reason.name) ?? [],
        };
  };
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
          plate: await browser.evaluate(`(${TOKEN})("--border")`),
          text: await browser.evaluate(`(${TOKEN})("--text")`),
          // A box that paints no ground of its own.
          none: "rgba(0, 0, 0, 0)",
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
        // A closed row is its title's lines and its change line, waiting or shown: a title of
        // two lines makes the height the panel places an unmeasured row at
        // (`ROW_ESTIMATE_PX`), and one of a line a row shorter by what its link gives up, down
        // to the shell's row height its link keeps (mb-zuy0).
        const estimate = await browser.evaluate(`window.__module.ROW_ESTIMATE_PX`);
        const titleLines = (number) => Math.min(2, after.rows[number]?.titleLines.length ?? 0);
        const sample = after.rows[SHOWN[0]];
        const lineHeight = sample?.lh ?? 0;
        const link = (lines) =>
          Math.max(
            sample?.minHeight ?? 0,
            (sample?.padTop ?? 0) + lines * lineHeight + (sample?.padBottom ?? 0),
          );
        const expected = (number) => estimate - link(2) + link(titleLines(number));
        check(
          `${at}: a closed row is ROW_ESTIMATE_PX tall with a title of two lines, and shorter by what its link gives up with one, waiting and shown`,
          Object.entries(measured[at].heights).every(
            ([number, height]) =>
              near(height.waiting, expected(Number(number))) &&
              near(height.shown, expected(Number(number))),
          ),
          JSON.stringify({
            estimate,
            lineHeight,
            oneLine: link(1),
            twoLines: link(2),
            heights: measured[at].heights,
          }),
        );
        if (theme === THEMES[0]) {
          measured[at].realTitles = await browser.evaluate(
            `(${REAL_ROWS})(${JSON.stringify(REAL_TITLES)})`,
          );
        }
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
              `${at}: #${number}'s row is its title's lines and its change line, the chevron on the last (${phase})`,
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
          // typical row's lines have no room.
          const waited = onLine(was, was.pending);
          const waitedInView = waited === "shown";
          check(
            `${at}: #${number}'s placeholder is on its third line or out of view`,
            waited === "shown" || waited === "dropped",
            JSON.stringify({ pending: was.pending, flow: was.flow }),
          );
          // The title's two lines: one of a short title, two of a long one, the rest past its
          // clamp, and the second under the state icon (mb-85op).
          const drawn = now.titleLines.filter(
            (line) => line.top < now.heading.bottom - TOLERANCE_PX,
          );
          if (number === 105 || number === 103) {
            check(
              `${at}: #${number}'s long title is cut short at its second line, which starts under the state icon`,
              drawn.length === 2 &&
                now.clamped &&
                near(drawn[1].left, now.icon.left) &&
                drawn.every((line) => line.right <= now.heading.right + TOLERANCE_PX),
              JSON.stringify({ drawn, heading: now.heading, icon: now.icon, clamped: now.clamped }),
            );
          } else {
            check(
              `${at}: #${number}'s short title is one line, in a box of one line (mb-zuy0)`,
              drawn.length === 1 && !now.clamped && near(now.heading.height, now.lh),
              JSON.stringify({ drawn, heading: now.heading }),
            );
          }
          if (NONE.includes(number)) {
            check(
              `${at}: #${number} shows the chevron, the number, and the author, and no lines and no placeholder`,
              now.nodes === 0 &&
                now.pending === null &&
                now.chevron !== null &&
                now.text === "" &&
                onLine(now, now.number) === "shown",
              JSON.stringify({ nodes: now.nodes, text: now.text }),
            );
            check(
              `${at}: #${number}'s change line is hidden, and its words describe its row for its files alone`,
              now.hidden === "true" && now.words === "Changed files",
              JSON.stringify({ hidden: now.hidden, words: now.words }),
            );
            continue;
          }
          const lines = onLine(now, now.changeLine);
          const author = onLine(now, now.by);
          check(
            `${at}: #${number}'s lines are whole on its third line or out of view, never cut short`,
            (lines === "shown" && now.statsWhole) || lines === "dropped",
            JSON.stringify({ lines, changeLine: now.changeLine, flow: now.flow }),
          );
          check(
            `${at}: #${number}'s line counts no files by status`,
            now.statuses === 0 && !/[ADMR],|\b\d+ [ADMR]\b/.test(now.text ?? ""),
            JSON.stringify({ text: now.text }),
          );
          // The lines leave the line only where the number leaves them no room, and the author
          // gives way before them: no author on the line without its lines.
          check(
            `${at}: #${number}'s lines are out of view only where they have no room beside the number`,
            lines === "shown" ||
              now.number.right + now.changeLine.width > now.flow.right + TOLERANCE_PX,
            JSON.stringify({ number: now.number, changeLine: now.changeLine, flow: now.flow }),
          );
          check(
            `${at}: #${number}'s author is on the line only with its lines, and before them`,
            author !== "cut" &&
              (author !== "shown" ||
                (lines === "shown" && now.by.right <= now.changeLine.left + TOLERANCE_PX)),
            JSON.stringify({ author, lines, by: now.by, changeLine: now.changeLine }),
          );
          measured[at][number] = { lines, author };
          // Lines no wider than the placeholder arrive in its room: where it was, on the line or
          // off it, and the author as it was.
          if (now.line.width <= was.block.width + TOLERANCE_PX) {
            check(
              `${at}: #${number}'s lines, no wider than its placeholder, leave the author as it was`,
              onLine(was, was.by) === author &&
                ["left", "width"].every((side) => near(was.by?.[side], now.by?.[side])) &&
                waited === lines,
              JSON.stringify({ was: was.by, now: now.by, waited, lines }),
            );
          }
          if (lines === "shown") {
            if (waitedInView) {
              check(
                `${at}: #${number}'s lines start where its placeholder did`,
                near(now.line.left, was.pending.left),
                `${now.line.left} ${was.pending.left}`,
              );
            }
            check(
              `${at}: #${number}'s totals are whole and in the row`,
              now.statsWhole && now.stats.right <= now.flow.right + TOLERANCE_PX,
              JSON.stringify({ stats: now.stats, flow: now.flow }),
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
          `${at}: #106's lines say what its list sums to, as the SDK says it, after the author's separator`,
          now.said === inks.text && now.text === ` · ${inks.text}`,
          `${JSON.stringify(now.text)} ${JSON.stringify(inks.text)}`,
        );
        check(
          `${at}: #106's row is described by its change line's words`,
          now.hidden === "true" && now.words === `Changed files: ${inks.label}`,
          JSON.stringify({ hidden: now.hidden, words: now.words }),
        );
        if (measured[at][106].lines === "shown") {
          for (const [part, ink] of Object.entries(inks.reference)) {
            check(
              `${at}: ${part} is the component's ink and weight`,
              JSON.stringify(inks.row[part]) === JSON.stringify(ink),
              `${JSON.stringify(inks.row[part])} ${JSON.stringify(ink)}`,
            );
          }
        }
        // The open row's mark is its item's: one ground under its three lines, which neither
        // the link nor the change line paints over, and the bar down both boxes' edge.
        const mark = inks.highlight;
        check(
          `${at}: the open row's highlight is its item's, one ground and one bar down its three lines`,
          mark.selected &&
            mark.item === tokens.highlight &&
            mark.row[0] === tokens.none &&
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
          // As Chrome computes it for assistive technology: the row is described by its line's
          // words, hidden as they are, and the line itself is no node of the tree, whose items'
          // children are only rows and groups.
          await browser.send("Accessibility.enable");
          const row106 = await axOf('a.github-pulls-row[data-number="106"]');
          const line106 = await axOf('.github-pulls-change[data-number="106"]');
          await browser.send("Accessibility.disable");
          check(
            `${at}: #106's row is described by its line's words, and the line is hidden from the tree`,
            row106?.role === "treeitem" &&
              row106.description === `Changed files: ${inks.label}` &&
              line106?.ignored === true &&
              (line106.reasons ?? []).some((reason) => reason.startsWith("ariaHidden")),
            JSON.stringify({ row106, line106 }),
          );
          measured[at].interaction = await interact(at, tokens);
          measured[at].inView = await walkInView(at);
        }
        lap(
          `${at}: #106 ${JSON.stringify(measured[at][106])}, #105 ${JSON.stringify(measured[at][105])}`,
        );
      }
    }
    const seen = Object.values(measured).map((at) => at?.[106] ?? {});
    check(
      "the number, the author, and the lines show whole at the widest pane",
      measured["420 px light"]?.[106]?.lines === "shown" &&
        measured["420 px light"]?.[106]?.author === "shown",
      JSON.stringify(measured["420 px light"]?.[106]),
    );
    check(
      "a narrower pane drops the author first, its lines whole, and the narrowest the lines too",
      seen.some((at) => at.author === "dropped" && at.lines === "shown") &&
        measured["180 px light"]?.[106]?.lines === "dropped",
      JSON.stringify(Object.fromEntries(Object.entries(measured).map(([k, v]) => [k, v?.[106]]))),
    );
    // A change of no lines and one of additions alone (mb-efum): a zero total is left out,
    // and "0 lines" is muted, at the line's weight, and whole wherever the recorded line,
    // "+1,093 −493", which is wider, shows.
    await browser.evaluate(
      `(window.__rowTotals = { 106: { additions: 0, deletions: 0 }, 105: { additions: 3, deletions: 0 } }, true)`,
    );
    measured.zeroTotals = {};
    for (const theme of THEMES) {
      for (const width of WIDTHS) {
        const at = `${width} px ${theme}`;
        await browser.evaluate(`(${MOUNT})(${width}, ${JSON.stringify(theme)})`);
        await browser.waitFor(
          `(window.__release(), ${JSON.stringify(SHOWN)}.every((number) => document.querySelector('.github-pulls-change[data-number="' + number + '"] .change-line') !== null))`,
        );
        await frames();
        const muted = await browser.evaluate(`(${TOKEN})("--muted")`);
        const { rows } = await browser.evaluate(READ);
        const ink = await browser.evaluate(`(() => {
          const line = document.querySelector('.github-pulls-change[data-number="106"] .change-line');
          const none = line?.querySelector(".change-line-stats > .change-line-none") ?? null;
          const added = document.querySelector('.github-pulls-change[data-number="105"] .change-line');
          return {
            none: none ? [getComputedStyle(none).color, getComputedStyle(none).fontWeight] : null,
            line: line ? getComputedStyle(line).fontWeight : null,
            added: added ? [...added.querySelectorAll(".change-line-stats > *")].map((part) => part.className) : null,
          };
        })()`);
        if (width === 299) {
          await shot(`row-lines-${theme}-${width}-zero-totals`, width);
        }
        const none = rows[106];
        const lines = onLine(none, none.changeLine);
        check(
          `${at} zero totals: #106 says "0 lines", in words "no lines changed"`,
          none.said === "0 lines" &&
            none.text === " · 0 lines" &&
            none.words === "Changed files: no lines changed",
          JSON.stringify({ said: none.said, text: none.text, words: none.words }),
        );
        check(
          `${at} zero totals: #105 shows its additions alone, "+3"`,
          rows[105].said === "+3" &&
            JSON.stringify(ink.added) === JSON.stringify(["diff-stat-add"]),
          JSON.stringify({ said: rows[105].said, parts: ink.added }),
        );
        check(
          `${at} zero totals: "0 lines" is muted, at the line's weight`,
          ink.none !== null && ink.none[0] === muted && ink.none[1] === ink.line,
          JSON.stringify({ ink, muted }),
        );
        check(
          `${at} zero totals: "0 lines" is whole on the third line or out of view, never cut`,
          (lines === "shown" &&
            none.statsWhole &&
            none.stats.right <= none.flow.right + TOLERANCE_PX) ||
            lines === "dropped",
          JSON.stringify({ lines, stats: none.stats, flow: none.flow }),
        );
        check(
          `${at} zero totals: "0 lines" shows wherever the recorded line does`,
          measured[at]?.[106]?.lines !== "shown" || lines === "shown",
          JSON.stringify({ recorded: measured[at]?.[106]?.lines, lines }),
        );
        measured.zeroTotals[at] = {
          lines,
          author: onLine(none, none.by),
          width: none.line?.width ?? null,
        };
        lap(`${at} zero totals: #106 ${JSON.stringify(measured.zeroTotals[at])}`);
      }
    }
    await browser.evaluate(`(window.__rowTotals = null, true)`);
    measured.real = await browser.evaluate(`(${REAL})(${JSON.stringify(REAL_LINES)})`);
    // The height an unmeasured row is placed at is a typical row's at the default pane: this
    // repository's titles, in a closed row at 299 px, whose mean it is within half a line of.
    const real = measured[`${DEFAULT_PANE} px ${THEMES[0]}`]?.realTitles;
    const estimate = await browser.evaluate(`window.__module.ROW_ESTIMATE_PX`);
    check(
      "ROW_ESTIMATE_PX is within half a line of this repository's rows at the default pane",
      real !== undefined &&
        real.n === REAL_TITLES.length &&
        Math.abs(real.mean - estimate) <= real.lh / 2,
      JSON.stringify({ estimate, real }),
    );
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
   * Real pointer and keyboard input on the panel mounted at 299 px: the item's hover and the
   * inner target's, the item's focus ring, presses on the title and the number's line, and
   * presses on the chevron and the line.
   */
  async function interact(at, tokens) {
    const result = {};
    const ROW = 'a.github-pulls-row[data-number="103"]';
    const CHANGE = '.github-pulls-change[data-number="103"]';
    const look = () =>
      browser.evaluate(`(() => {
        const row = document.querySelector(${JSON.stringify(ROW)});
        const change = document.querySelector(${JSON.stringify(CHANGE)});
        const plate = change?.querySelector(":scope > .github-pulls-toggle") ?? null;
        const ground = (el) => el ? getComputedStyle(el).backgroundColor : null;
        const chevron = plate?.querySelector(".toggle-chevron") ?? null;
        return {
          item: ground(row?.parentElement), row: ground(row), change: ground(change), plate: ground(plate),
          chevron: chevron ? getComputedStyle(chevron).color : null,
        };
      })()`);
    const name = (what) => `${at.replace(/\s+/g, "-")}-${what}`;
    // Hover: the title, then on the change line the number, the age, and the chevron. Every
    // line hovers the item's one ground; only the change line, the toggle's line, also lights
    // its chevron.
    // The title's two lines, at their middle: #103's title runs past its clamp, so its own box
    // reaches under the link.
    await pointAt(`${ROW} .github-pulls-heading`, false);
    result.hoverTitle = await look();
    await shot(name("hover-item"), 299);
    await pointAt(`${CHANGE} .github-pulls-number`, false);
    result.hoverMeta = await look();
    await pointAt(`${CHANGE} .github-pulls-age`, false);
    result.hoverLine = await look();
    await shot(name("hover-inner"), 299);
    await pointAt(`${CHANGE} > .github-pulls-toggle`, false);
    result.hoverChevron = await look();
    await browser.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1200, y: 880 });
    await frames();
    result.away = await look();
    const outer = (seen) =>
      seen.item === tokens.hover && seen.row === tokens.none && seen.change === tokens.none;
    check(
      `${at}: the pointer on any of a pull request's lines hovers its one item`,
      [result.hoverTitle, result.hoverMeta, result.hoverLine, result.hoverChevron].every(outer) &&
        result.away.item !== tokens.hover,
      JSON.stringify({ ...result, tokens }),
    );
    check(
      `${at}: the change line, the toggle's line, adds the inner target's hover, the chevron's plate`,
      [result.hoverMeta, result.hoverLine, result.hoverChevron].every(
        (seen) => seen.plate === tokens.plate && seen.chevron === tokens.text,
      ) &&
        [result.hoverTitle, result.away].every(
          (seen) => seen.plate === tokens.none && seen.chevron !== tokens.text,
        ),
      JSON.stringify({ ...result, tokens }),
    );
    // The focus ring: Tab to the list's stop, as a keyboard reader does. The stop is the row's
    // link, and the ring is drawn round its item, its three lines; the change line is no stop.
    for (let tab = 0; tab < 6; tab += 1) {
      await key("Tab", "Tab", 9);
      if (
        await browser.evaluate(`document.activeElement?.matches("a.github-pulls-row") === true`)
      ) {
        break;
      }
    }
    result.ring = await browser.evaluate(`(() => {
      const el = document.activeElement;
      const item = el.parentElement;
      const change = item?.querySelector(":scope > .github-pulls-change") ?? null;
      const own = getComputedStyle(el);
      const style = item ? getComputedStyle(item) : null;
      return {
        focus: el.matches("a.github-pulls-row") ? "row " + el.dataset.number : el.tagName,
        selected: el.classList.contains("selected"),
        visible: el.matches(":focus-visible"), own: own.outlineStyle,
        item: style ? [style.outlineStyle, style.outlineColor, style.outlineOffset, style.backgroundColor] : null,
        changeStop: change === null ? null : change.tabIndex >= 0 || change.hasAttribute("tabindex"),
      };
    })()`);
    const link = await browser.evaluate(`(${TOKEN})("--link")`);
    check(
      `${at}: Tab's stop is a row's link, its item takes the ring, and its change line is no stop`,
      result.ring.focus.startsWith("row ") &&
        result.ring.visible &&
        result.ring.own === "none" &&
        result.ring.item?.[0] === "solid" &&
        result.ring.item[1] === link &&
        result.ring.item[2] === "-2px" &&
        // The current item keeps its mark under the ring, as a Files row does.
        result.ring.item[3] === (result.ring.selected ? tokens.highlight : tokens.hover) &&
        result.ring.changeStop === false,
      JSON.stringify({ ring: result.ring, link }),
    );
    // A press on the title opens the pull request and expands nothing.
    const state = `(() => {
      const change = document.querySelector('.github-pulls-change[data-number="106"]');
      const item = change?.closest("li");
      const files = item?.querySelector(".github-pull-files");
      const box = (el) => el ? el.getBoundingClientRect().toJSON() : null;
      return {
        expanded: item?.querySelector("a.github-pulls-row")?.getAttribute("aria-expanded") ?? null,
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
    // A press on the number, on the third line, the toggle's line since mb-lqkb, opens the
    // files and no page; one on the author, on the same line, closes them.
    await pointAt('.github-pulls-change[data-number="106"] .github-pulls-number', true);
    await pause(250);
    await browser
      .waitFor(
        `document.querySelector('.github-pulls-change[data-number="106"]')?.closest("li")?.querySelector(".github-pull-files-rows")?.firstElementChild != null`,
        5000,
      )
      .catch(() => false);
    result.number = await browser.evaluate(state);
    check(
      `${at}: a press on a row's number opens its files under the change line and opens no page`,
      result.number.opened.length === result.title.opened.length &&
        result.number.expanded === "true" &&
        result.number.files !== null &&
        result.number.files.top >= result.number.change.bottom - TOLERANCE_PX &&
        Math.abs(result.number.change.top - result.title.change.top) <= TOLERANCE_PX,
      JSON.stringify(result.number),
    );
    result.authorShown = await browser.evaluate(
      `(() => { const by = document.querySelector('.github-pulls-change[data-number="106"] .github-pulls-by'); const line = by?.parentElement; return by !== null && by.getBoundingClientRect().bottom <= line.getBoundingClientRect().bottom + 0.5; })()`,
    );
    await pointAt('.github-pulls-change[data-number="106"] .github-pulls-author', true);
    await pause(250);
    result.meta = await browser.evaluate(state);
    check(
      `${at}: a press on a row's author, in view, closes its files and opens no page`,
      result.authorShown &&
        result.meta.opened.length === result.title.opened.length &&
        result.meta.expanded === "false" &&
        result.meta.files === null &&
        Math.abs(result.meta.change.top - result.title.change.top) <= TOLERANCE_PX,
      JSON.stringify({ shown: result.authorShown, meta: result.meta }),
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
        result.chevron.opened.length === result.meta.opened.length,
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
        result.line.opened.length === result.meta.opened.length,
      JSON.stringify(result.line),
    );
    // Right and Left on the item, its handle's `expand` and `collapse`, keep its change line
    // where it is too, over #105, the open row, placed again by a reveal before each.
    const CHANGE106 = `document.querySelector('.github-pulls-change[data-number="106"]')`;
    const ROW106 = `document.querySelector('a.github-pulls-row[data-number="106"]')`;
    for (const [handler, key, want] of [
      ["expand", "Right", "true"],
      ["collapse", "Left", "false"],
    ]) {
      await browser.evaluate(`window.__panel.setCurrent(105, null, { again: true }), true`);
      await frames();
      // The reveal made #105 the list's Tab stop, and the press on #106 left focus on its row:
      // the key acts on #106, the item with focus, not on the Tab stop.
      await browser.evaluate(`${ROW106}.focus(), true`);
      const before = await browser.evaluate(`${CHANGE106}.getBoundingClientRect().top`);
      await browser.evaluate(`window.__panel.${handler}(), true`);
      await pause(250);
      if (want === "true") {
        await browser
          .waitFor(
            `${CHANGE106}.closest("li").querySelector(".github-pull-files-rows")?.firstElementChild != null`,
            5000,
          )
          .catch(() => false);
        await frames();
      }
      const moved = {
        before,
        after: await browser.evaluate(`${CHANGE106}.getBoundingClientRect().top`),
        expanded: await browser.evaluate(`${ROW106}.getAttribute("aria-expanded")`),
        focused: await browser.evaluate(`document.activeElement === ${ROW106}`),
      };
      result[key] = moved;
      check(
        `${at}: ${key} on the item ${want === "true" ? "opens" : "closes"} the files and leaves it where it was, over a revealed row`,
        moved.expanded === want &&
          moved.focused &&
          Math.abs(moved.after - moved.before) <= TOLERANCE_PX,
        JSON.stringify(moved),
      );
    }
    return result;
  }

  /**
   * A walk and a reveal bring a pull request's whole item into view: its three lines and the
   * focus ring round them, not only its link's two lines (`itemElement` in pulls-panel.js).
   */
  async function walkInView(at) {
    const result = {};
    // In the page: the pane's view under its sticky filters, the item just below its fold and
    // the row before it, and where each is.
    const place = (numbers) =>
      browser.evaluate(`(() => {
        const pane = document.getElementById("pane");
        const box = pane.getBoundingClientRect();
        const filters = pane.querySelector(".github-pulls-filters");
        const view = {
          top: filters ? Math.max(box.top, filters.getBoundingClientRect().bottom) : box.top,
          bottom: box.top + pane.clientHeight,
        };
        const rows = [...pane.querySelectorAll('.github-pulls-list [role="treeitem"]')];
        const zoneOf = (row) => row.matches("a.github-pulls-row") ? row.parentElement : row;
        const numbers = ${JSON.stringify(numbers)} ?? (() => {
          const below = rows.findIndex((row) => zoneOf(row).getBoundingClientRect().bottom > view.bottom);
          return below > 0 && rows[below].matches("a.github-pulls-row[data-number]")
            ? [rows[below - 1].dataset.number ?? rows[below - 1].dataset.stack, rows[below].dataset.number]
            : null;
        })();
        if (numbers === null) return { view, numbers: null };
        const [above, below] = numbers.map((number) =>
          pane.querySelector('a.github-pulls-row[data-number="' + number + '"]') ??
          pane.querySelector('.github-pulls-stack-row[data-stack="' + number + '"]'));
        const zone = below.parentElement;
        const where = (el) => el ? { top: el.getBoundingClientRect().top, bottom: el.getBoundingClientRect().bottom } : null;
        return {
          view, numbers, above: where(zoneOf(above)), zone: where(zone),
          change: where(zone.querySelector(":scope > .github-pulls-change")),
          link: where(below), focused: document.activeElement === below,
        };
      })()`);
    const whole = (seen) =>
      seen.zone !== null &&
      seen.change !== null &&
      seen.zone.top >= seen.view.top - TOLERANCE_PX &&
      seen.zone.bottom <= seen.view.bottom + TOLERANCE_PX &&
      seen.change.bottom <= seen.view.bottom + TOLERANCE_PX;
    await browser.evaluate(`document.getElementById("pane").scrollTop = 0, true`);
    await frames();
    result.before = await place(null);
    check(
      `${at}: an item lies just below the pane's fold, its change line out of view`,
      result.before.numbers !== null &&
        result.before.above.bottom <= result.before.view.bottom + TOLERANCE_PX &&
        result.before.change.bottom > result.before.view.bottom + TOLERANCE_PX,
      JSON.stringify(result.before),
    );
    if (result.before.numbers === null) {
      return result;
    }
    const [above, below] = result.before.numbers;
    // Down from the row above the fold, as a reader walks: the handle's `move`, which the
    // shell's key routes to.
    await browser.evaluate(
      `(document.querySelector('a.github-pulls-row[data-number="${above}"]') ?? document.querySelector('.github-pulls-stack-row[data-stack="${above}"]')).focus(), window.__panel.move(1), true`,
    );
    await frames();
    result.down = await place(result.before.numbers);
    check(
      `${at}: Down onto the item just below the fold brings all of it into view, its change line too`,
      result.down.focused && whole(result.down),
      JSON.stringify({ below, down: result.down }),
    );
    // A reveal of that item, the pane's page arriving at it, brings it whole too.
    await browser.evaluate(`document.getElementById("pane").scrollTop = 0, true`);
    await frames();
    await browser.evaluate(`window.__panel.setCurrent(${below}, null, { again: true }), true`);
    await frames();
    result.reveal = await place(result.before.numbers);
    check(
      `${at}: a reveal of the item just below the fold brings all of it into view`,
      whole(result.reveal),
      JSON.stringify({ below, reveal: result.reveal }),
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
