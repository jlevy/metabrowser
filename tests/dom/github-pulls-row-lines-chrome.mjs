// Each Pulls row's run and last line (mb-d0a3, mb-85op, mb-lqkb, mb-zuy0, mb-pw8t, mb-rb3n),
// laid out by headless Chrome: the production panel module, the shell's SDK, icon registry, and
// stylesheets, mounted on recorded answers.
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
// and #105 the open pull request. Its rows' lines are the summary route's recorded answer
// `summed` (tests/fixtures/github-pull-files-summary-responses.json): #106's and #105's lists
// are summed, #104's is not cached, and #103's is filling; a row the recording does not name
// answers as its not-cached row does. The summary's answer is held until the session lets it
// go, so each row is laid out while it waits, in the shell's pending placeholder past the
// quiet period, and again once its lines have arrived. At every pane width from 420 px to the
// 180 px minimum, in the light theme and the dark, it holds that:
//
// - each pull request's row is its link: its run, one flow of the state icon, the title, the
//   number, and the author, a muted dot before each part after the title, every line of it
//   starting in the text column, past the icon, which is centered on its first line, as tall
//   as its lines and never cut short, so it ends with the author, whose name is on the run's
//   baseline (mb-rb3n); then its last line, one line tall: the toggle, the lines and the
//   chevron after them, starting in the text column, and the age at the row's end, past the
//   chevron (docs/design-system.md, "Ages End the Row");
// - GitHub's longest login is cut short only where it is wider than a line, and the longest
//   age is whole at the row's end;
// - a closed row is `ROW_ESTIMATE_PX` tall with a run of `ESTIMATE_LINES`, a typical row's at
//   the default pane, and a line shorter or taller for each line fewer or more;
// - nothing moves when the lines arrive: the item, the link, the run, the title, the state
//   icon, the number, the author, the age, and the last line; the chevron keeps its line and
//   follows the lines, which start where the placeholder did;
// - the lines and the chevron are one line, the lines whole and in the row wherever the last
//   line has their room beside the readiness's column and the age (mb-3n21), and given way
//   whole to an ellipsis only where it has not, at the narrowest panes; the chevron ends
//   before the readiness's column;
//   the line counts no files by status; nothing scrolls sideways;
// - the lines' inks and weights are the component's, part for part, as the same line drawn by
//   the SDK outside the row resolves them in that theme, and its item's name says it in words;
// - #104 and #103, whose lists cannot be had, have the chevron alone on their last line, and
//   show no lines and no placeholder, once answered;
// - the open row's highlight is its item's: one ground under its run and its last line, and
//   its left bar down the link's edge.
//
// #106's and #104's authors have an avatar's address, which the page's policy keeps from
// loading, so their box holds the person glyph, as an avatar that fails does; #105's and
// #103's have none, and no box.
//
// At 299 px, the default pane, in each theme, with real pointer and keyboard input, it holds
// that a pull request is one item (mb-1z7j): the pointer anywhere on it hovers the item's one
// ground, and on its toggle, the lines or the chevron, the chevron's plate too, the inner
// target's own hover, which no other part shows; Tab's stop is the row's link, whose ring is
// drawn round the whole item, and the toggle is no stop. A press on a row's title, its number,
// its author, or its last line past the chevron opens the pull request and expands nothing; a
// press on the chevron or on the lines opens or closes the files under the row, and opens no
// page (docs/design-system.md, "A Click on the Toggle's Line Toggles"). The keys need the
// shell's registry, which this page has not: tests/dom/github-pulls-stacks-chrome.mjs holds
// them in the running app; here the handle's `expand` and `collapse`, which Right and Left
// call, act on the focused item. With SHOTS_DIR set, it saves the item's hover and the inner
// target's, at 299 px in each theme.
//
// It then mounts the rows again, in each theme at every width, with #106's change of no lines
// and #105's of additions alone (mb-efum): a zero total is left out, "+3", and no lines are a
// muted "0 lines" at the line's weight, whole and in the row.
//
// It also lays out the lines changed of this repository's own pull requests (`REAL_LINES`), to
// say how wide a typical row's lines are, which the placeholder's width is judged against, and
// their titles (`REAL_TITLES`) in a closed row at every width, their author's name and avatar
// box beside them, to say how many lines a typical row's run takes and how tall the row is,
// which `ROW_ESTIMATE_PX` is held to.
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
/** Whether *inner*'s box is within *outer*'s, top to bottom. */
const within = (inner, outer) =>
  inner != null &&
  outer != null &&
  inner.top >= outer.top - TOLERANCE_PX &&
  inner.bottom <= outer.bottom + TOLERANCE_PX;
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
// Titles of three lengths among the rows checked: #106's and #104's are short, #105's runs
// past two lines at every width, and #103's is one unbroken word longer than the row.
const TITLES = {
  105: "feat(pulls): one run for a row, its title, its place, its number, its author, and its age, wrapping in the text column past the state icon at every width",
  103: `docs:${"x".repeat(160)}`,
};
// An avatar's address for #106's and #104's authors, as GitHub gives one: the page's policy
// (`PAGE`) keeps it from loading, so the box holds the person glyph, and the box is what the
// run lays out. #105's and #103's authors have none, and no box.
const AVATAR = "https://avatars.githubusercontent.com/u/1?s=40";
const AVATARS = new Set([106, 104]);
const ANSWERS = {
  list: {
    ...lists.current.body,
    rows: rowsOf(lists.current.body.rows).map((row) => ({
      ...row,
      ...(row.number in TITLES ? { title: TITLES[row.number] } : {}),
      ...(AVATARS.has(row.number) ? { author_avatar_url: AVATAR } : {}),
    })),
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
// Images only from the page's own server: an avatar's address asks nothing of the network.
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>row lines</title>
<meta http-equiv="Content-Security-Policy" content="img-src 'self' data:">
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
    ...(${agesFrom})(document, () => ({ label: "1m", className: "age-min" })),
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

// In the page: each checked row's geometry, its run's lines, and what its toggle shows.
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
    const heading = row.querySelector(".github-pulls-heading");
    const title = row.querySelector(".github-pulls-title");
    const place = row.querySelector(".github-pulls-place");
    const shown = row.querySelector(".github-pulls-number");
    const tail = row.querySelector(":scope > .github-pulls-tail");
    // The age, at the end of the last line (docs/design-system.md, "Ages End the Row").
    const age = tail?.querySelector(":scope > .github-pulls-age") ?? null;
    const change = tail?.querySelector(".github-pulls-change") ?? null;
    const line = change?.querySelector(".github-pulls-change-line") ?? null;
    const pending = line?.querySelector(".github-pulls-change-pending") ?? null;
    const said = line?.querySelector(".change-line") ?? null;
    const stats = said?.querySelector(".change-line-stats") ?? null;
    const toggle = change?.querySelector(":scope > .github-pulls-toggle") ?? null;
    const chevron = toggle?.querySelector("svg") ?? null;
    const style = getComputedStyle(row);
    const runStyle = heading ? getComputedStyle(heading) : null;
    const lh = runStyle ? parseFloat(runStyle.lineHeight) : null;
    const run = heading?.getBoundingClientRect() ?? null;
    const top = run ? run.top + parseFloat(runStyle.paddingTop) : 0;
    // The line of the run a box is on, by its middle.
    const lineOf = (rect) => Math.floor((rect.top + rect.height / 2 - top) / lh);
    // The run's lines, from its parts' fragments: a line's start and end are its fragments'
    // outermost. The dots are left out: a line never starts with one, and a dot's trailing
    // space hangs past the end of a line it ends.
    const lines = [];
    for (const piece of [title]) {
      for (const rect of piece?.getClientRects() ?? []) {
        if (rect.width === 0) continue;
        const at = lineOf(rect);
        const seen = lines[at];
        lines[at] = seen
          ? { left: Math.min(seen.left, rect.left), right: Math.max(seen.right, rect.right) }
          : { left: rect.left, right: rect.right };
      }
    }
    // A text's own box, its glyphs' line box, whatever box holds it.
    const glyphs = (el) => {
      const text = el ? [...el.childNodes].find((node) => node.nodeType === Node.TEXT_NODE) : null;
      if (!text) return null;
      const range = document.createRange();
      range.selectNodeContents(text);
      return box(range);
    };
    rows[number] = {
      item: box(item), row: box(row), heading: box(heading), title: box(title), lh,
      runLines: Array.from(lines, (each) => each ?? null),
      // Past its box, a run cut short.
      clamped: heading !== null && heading.scrollHeight > heading.clientHeight + 1,
      column: heading?.querySelector(".github-pull-row-copy").getBoundingClientRect().left ?? null,
      icon: box(row.querySelector(".github-pull-state-icon")),
      noPlace: place.hidden,
      headingHasNumber: heading.contains(shown),
      headingHasAuthor: heading.querySelector(".actor-avatar") !== null,
      rowToggles: row.querySelectorAll(".github-pulls-toggle").length,
      inset: inset(row),
      slot: parseFloat(style.getPropertyValue("--tree-icon-slot")), gap: runStyle ? parseFloat(runStyle.columnGap) : null,
      number: box(shown),
      age: box(age), ageText: glyphs(age),
      tail: box(tail), tailHeight: tail ? parseFloat(getComputedStyle(tail).height) : null,
      // The end of the last line's content, which the age ends at.
      tailEnd: tail ? tail.getBoundingClientRect().right - parseFloat(getComputedStyle(tail).paddingInlineEnd) : null,
      lastStart: tail ? tail.getBoundingClientRect().left + parseFloat(getComputedStyle(tail).paddingInlineStart) : null,
      change: box(change), toggle: box(toggle), chevron: box(chevron),
      changeLine: box(line), pending: box(pending), block: box(pending?.querySelector(".tally-pending")),
      pendingShown: pending !== null && getComputedStyle(pending).visibility === "visible",
      line: box(said), stats: box(stats), said: said?.textContent ?? null,
      statsWhole: stats === null || stats.scrollWidth <= stats.clientWidth + 0.5,
      // The lines' own width, whole or not, and the readiness's column after the toggle
      // (mb-3n21), which the toggle never runs into.
      statsNatural: stats?.scrollWidth ?? null,
      readiness: box(tail?.querySelector(".github-pulls-readiness") ?? null),
      tailGap: tail ? parseFloat(getComputedStyle(tail).columnGap) : null,
      changeRoom: tail && age && shown ? tail.getBoundingClientRect().right - shown.closest(".github-pull-row-end").getBoundingClientRect().width - age.getBoundingClientRect().width - 2 * parseFloat(getComputedStyle(tail).columnGap) - change.getBoundingClientRect().left : null,
      toggleRoom: toggle ? toggle.getBoundingClientRect().width + parseFloat(getComputedStyle(toggle).marginInlineStart) : null,
      // The line counts no files by status (mb-lqkb).
      statuses: said?.querySelectorAll(".change-line-statuses, .change-line-group, .file-change-status").length ?? 0,
      text: line?.textContent ?? null, nodes: line?.childNodes.length ?? null,
      // The toggle is the pointer's alone, hidden from assistive technology; its words, hidden
      // too, describe the row, which alone says whether its files are open.
      hidden: change?.getAttribute("aria-hidden") ?? null,
      words: document.getElementById(row.getAttribute("aria-describedby") ?? "")?.textContent ?? null,
      expanded: row.getAttribute("aria-expanded"),
      files: box(item.querySelector(".github-pull-files")),
    };
  }
  return { rows, scroll: [pane.scrollWidth, pane.clientWidth] };
})()`;

// In the page: the inks and weights of the lines' parts in #106's row, and of the same line
// drawn by the SDK in a plain block of the page, the component outside any host; the name the
// SDK gives it; and the open row's highlight: its item's ground, and the bar on its link.
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
  const other = document.querySelector('a.github-pulls-row[data-number="104"]');
  const ground = (el) => el ? getComputedStyle(el).backgroundColor : null;
  const bar = (el) => el ? [getComputedStyle(el).borderLeftColor, getComputedStyle(el).borderLeftWidth] : null;
  return {
    row: read(host), reference: read(reference), text: reference.textContent, label: said.label,
    highlight: {
      selected: open?.classList.contains("selected") ?? false,
      item: ground(open?.parentElement), row: [ground(open), ...bar(open)],
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
// a copy of #104's row, drawn and gone at once, and how many lines its run takes. The copy's
// author is this repository's pull requests' own, `REAL_AUTHOR`, with #104's avatar box, and
// its age the page's "1m", as wide as most. Its last line is one line tall whatever it holds.
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
  const byLines = {};
  for (const row of rows) byLines[row.lines] = (byLines[row.lines] ?? 0) + 1;
  return {
    n: rows.length,
    lh: parseFloat(getComputedStyle(item.querySelector(".github-pulls-heading")).lineHeight),
    mean: round(heights.reduce((sum, height) => sum + height, 0) / rows.length),
    min: Math.min(...heights),
    max: Math.max(...heights),
    // How many of the rows' runs take one line, two, three, and so on.
    byLines,
  };
})`;

// The longest compact age takes only its own width, even at the minimum pane width.
const LONG_AGE = `(() => {
  const item = document.querySelector('li.github-pulls-item[data-number="104"]');
  const copy = item.cloneNode(true);
  copy.removeAttribute("data-number");
  const age = copy.querySelector(".github-pulls-age");
  age.textContent = "12mo";
  item.parentElement.append(copy);
  const change = copy.querySelector(".github-pulls-change").getBoundingClientRect();
  const end = copy.querySelector(".github-pull-row-end").getBoundingClientRect();
  const ageBox = age.getBoundingClientRect();
  const gap = parseFloat(getComputedStyle(age.closest(".github-pulls-tail")).gap);
  const read = { ageWhole: age.scrollWidth <= age.clientWidth + 0.5, gap, beforeEnd: ageBox.right < end.left, measuredGap: ageBox.left - change.right };
  copy.remove();
  return read;
})()`;

// In the page: how wide each real pull request's lines changed are in the run's type, whole,
// as the row draws them, its totals alone.
const REAL = `((lines) => {
  const container = document.querySelector(".github-pulls-change");
  const host = document.createElement("span");
  // Beside the rows, at its own widest: the run's type, the nav's.
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

// The author of this repository's pull requests 440 to 488 (`REAL_TITLES`).
const WIDTHS = [420, 380, 340, 299, 260, 220, 200, 180];
// The default pane's width, where the hover and the focus are held.
const DEFAULT_PANE = 299;
const THEMES = ["light", "dark"];
// The parts that do not move when the lines arrive, whatever their width, since the lines are
// on the row's last line, under the run, with the age in its own column at the line's end
// (mb-rb3n).
const PARTS = ["item", "row", "heading", "title", "icon", "number", "tail"];
// How many lines a typical row's run takes at the default pane, which a closed row placed at
// `ROW_ESTIMATE_PX` has.
const ESTIMATE_LINES = 3;

/** Whether *r* is its run, which ends with the author, and its last line, the toggle and the
 * age (mb-rb3n). */
function rowShape(r) {
  if (
    !r?.heading ||
    !r.icon ||
    !r.number ||
    !r.age ||
    !r.tail ||
    !r.chevron ||
    r.runLines.length === 0
  ) {
    return { ok: false, why: "a part is missing" };
  }
  const lines = r.runLines;
  const n = lines.length;
  const parts = {
    // The run is as tall as its lines, and never cut short (mb-pw8t).
    runIsItsLines:
      lines.every((line) => line !== null) && near(r.heading.height, n * r.lh) && !r.clamped,
    // Every line of it starts in the text column, past the state icon, as a tree's title wraps,
    // and ends inside the row: no line's start rests on a first line's indent (mb-ma3f).
    linesInTextColumn: lines.every(
      (line) =>
        line !== null &&
        line.left >= r.column - TOLERANCE_PX &&
        line.right <= r.heading.right + TOLERANCE_PX,
    ),
    // The state icon is the run's start, on the row's inset in the one icon slot (mb-3vil),
    // centered on the first line's box, and the text column is one column gap past it.
    iconOnFirst: near(r.icon.top, r.heading.top) && near(r.icon.height, r.lh),
    iconOnInset:
      near(r.icon.left, r.inset) &&
      near(r.icon.width, r.slot) &&
      near(r.column, r.icon.right + r.gap),
    titleOnly: r.noPlace && !r.headingHasNumber && !r.headingHasAuthor,
    lastLine:
      near(r.tail.top, r.heading.bottom) &&
      near(r.tail.bottom, r.row.bottom) &&
      near(r.tail.height, r.tailHeight) &&
      r.rowToggles === 1 &&
      near(r.lastStart, r.column) &&
      near(r.change.left, r.column) &&
      within(r.chevron, r.tail) &&
      (r.changeLine === null || r.chevron.left >= r.changeLine.right - TOLERANCE_PX),
    summaryFields:
      within(r.age, r.tail) &&
      within(r.number, r.tail) &&
      near(r.number.right, r.tailEnd) &&
      near(r.age.left, r.change.right + r.tailGap) &&
      r.age.right < r.number.left &&
      r.ageText !== null &&
      near(r.ageText.right, r.age.right),
    // A closed row's item is its link.
    itemIsRow: near(r.item.height, r.row.height),
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
  /**
   * A real pointer: moved to, and pressed if *press*, at an element's point: its box's middle,
   * 4 px in from its start, or the middle of its first fragment, the first line of a title
   * that wraps.
   */
  const pointAt = async (selector, press, at = "middle") => {
    const point = await browser.evaluate(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (el === null) return null;
      const r = ${at === "first" ? "el.getClientRects()[0] ?? el.getBoundingClientRect()" : "el.getBoundingClientRect()"};
      return { x: ${at === "start" ? "r.left + 4" : at === "end" ? "r.right - 4" : "r.left + r.width / 2"}, y: r.top + r.height / 2 };
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
          bar: await browser.evaluate(`(${TOKEN})("--highlight-bar")`),
          // A box that paints no ground of its own.
          none: "rgba(0, 0, 0, 0)",
        };
        // Each row waits in its placeholder, past the quiet period, its read held. A build that
        // draws no placeholder fails here.
        const waits = await browser
          .waitFor(
            `${JSON.stringify([...SHOWN, ...NONE])}.every((number) => document.querySelector('.github-pulls-change[data-number="' + number + '"] .github-pulls-change-pending') !== null)`,
            5000,
          )
          .then(
            () => true,
            () => false,
          );
        check(`${at}: each row holds a placeholder in its run while its lines are read`, waits);
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
                runLines: after.rows[number]?.runLines.length ?? null,
              },
            ]),
          ),
          placeholder: before.rows[106]?.block?.width ?? null,
        };
        // A closed row is its run and its last line: a run of `ESTIMATE_LINES` makes the height
        // the panel places an unmeasured row at (`ROW_ESTIMATE_PX`), and each line fewer or more
        // a row a line shorter or taller.
        const estimate = await browser.evaluate(`window.__module.ROW_ESTIMATE_PX`);
        const expected = (r) => (r ? estimate + (r.runLines.length - ESTIMATE_LINES) * r.lh : null);
        check(
          `${at}: a closed row is ROW_ESTIMATE_PX tall with a run of ${ESTIMATE_LINES} lines, and a line shorter or taller for each line fewer or more, waiting and shown`,
          [...SHOWN, ...NONE].every(
            (number) =>
              near(before.rows[number]?.item?.height, expected(before.rows[number])) &&
              near(after.rows[number]?.item?.height, expected(after.rows[number])),
          ),
          JSON.stringify({ estimate, lh: after.rows[SHOWN[0]]?.lh, heights: measured[at].heights }),
        );
        const long = await browser.evaluate(LONG_AGE);
        check(
          `${at}: the longest age fits beside the change summary`,
          long.ageWhole && long.beforeEnd && near(long.measuredGap, long.gap),
          JSON.stringify(long),
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
            const shape = rowShape(r);
            check(
              `${at}: #${number}'s row is its title and its summary line (${phase})`,
              shape.ok,
              JSON.stringify({
                ...(shape.parts ?? { why: shape.why }),
                lines: r?.runLines,
                column: r?.column,
                run: r?.heading,
                age: r?.age,
              }),
            );
          }
          // Lines of any width, and no line, arrive on the last line, alone: nothing moves but
          // the chevron, which keeps its line and follows them.
          for (const part of PARTS) {
            check(
              `${at}: #${number}'s ${part} does not move when its lines arrive`,
              ["left", "top", "width", "height"].every((side) =>
                near(was?.[part]?.[side], now?.[part]?.[side]),
              ),
              `${JSON.stringify(was?.[part])} ${JSON.stringify(now?.[part])}`,
            );
          }
          check(
            `${at}: #${number}'s chevron keeps its line when its lines arrive`,
            near(was?.chevron?.top, now?.chevron?.top) &&
              near(was?.chevron?.height, now?.chevron?.height),
            `${JSON.stringify(was?.chevron)} ${JSON.stringify(now?.chevron)}`,
          );
          // The title is never cut short: #105's and #103's take the run past two lines, and
          // #103's one word breaks inside the row (rowShape holds every line in the row).
          if (number === 105 || number === 103) {
            check(
              `${at}: #${number}'s long title runs past two lines, never cut short`,
              now.runLines.length >= 3 && !now.clamped,
              JSON.stringify({ lines: now.runLines, heading: now.heading, clamped: now.clamped }),
            );
          }
          if (NONE.includes(number)) {
            check(
              `${at}: #${number}'s last line is the chevron alone, with no lines and no placeholder`,
              now.nodes === 0 &&
                now.pending === null &&
                now.chevron !== null &&
                now.text === "" &&
                now.chevron.left <= now.column + now.slot,
              JSON.stringify({
                nodes: now.nodes,
                text: now.text,
                column: now.column,
                chevron: now.chevron,
              }),
            );
            check(
              `${at}: #${number}'s toggle is hidden, and its words describe its row for its files alone`,
              now.hidden === "true" && now.words === "Changed files",
              JSON.stringify({ hidden: now.hidden, words: now.words }),
            );
            measured[at][number] = { runLines: now.runLines.length };
            continue;
          }
          // The lines are whole, before the chevron, wherever the last line has their room
          // beside the readiness's column and the age; at the narrowest panes, where it has
          // not, they give way whole to an ellipsis, and the chevron, the column, and the age
          // stay (docs/design-system.md, "The Pulls Tab"). Either way the toggle ends before
          // the readiness's column.
          const room = now.changeRoom;
          const needs = (now.statsNatural ?? 0) + (now.toggleRoom ?? 0);
          // Whole: the line's box holds the lines, and they end before the chevron.
          const whole =
            now.statsWhole &&
            now.stats !== null &&
            now.changeLine !== null &&
            now.stats.right <= now.changeLine.right + TOLERANCE_PX &&
            now.stats.right <= now.chevron.left + TOLERANCE_PX;
          check(
            `${at}: #${number}'s lines are whole, before the chevron on the last line, and in the row, where the line has their room beside the readiness column, and give way only where it has not`,
            now.line !== null &&
              room !== null &&
              whole === room >= needs - TOLERANCE_PX &&
              within(now.line, now.tail) &&
              now.chevron.right <= now.age.left - now.tailGap + TOLERANCE_PX &&
              now.chevron.right <= now.tail.right + TOLERANCE_PX,
            JSON.stringify({
              line: now.line,
              stats: now.stats,
              chevron: now.chevron,
              changeLine: now.changeLine,
              readiness: now.readiness,
              room,
              needs,
              tail: now.tail,
            }),
          );
          check(
            `${at}: #${number}'s line counts no files by status`,
            now.statuses === 0 && !/[ADMR],|\b\d+ [ADMR]\b/.test(now.text ?? ""),
            JSON.stringify({ text: now.text }),
          );
          check(
            `${at}: #${number}'s lines start where its placeholder did`,
            near(now.line.left, was.pending.left),
            `${now.line.left} ${was.pending.left}`,
          );
          measured[at][number] = { runLines: now.runLines.length, lines: now.line?.width ?? null };
        }
        check(
          `${at}: nothing scrolls sideways`,
          before.scroll[0] <= before.scroll[1] && after.scroll[0] <= after.scroll[1],
          JSON.stringify([before.scroll, after.scroll]),
        );
        const now = after.rows[106];
        check(
          `${at}: #106's lines say what its list sums to, as the SDK says it`,
          now.said === inks.text && now.text === inks.text,
          `${JSON.stringify(now.text)} ${JSON.stringify(inks.text)}`,
        );
        check(
          `${at}: #106's row is described by its toggle's words`,
          now.hidden === "true" && now.words === `Changed files: ${inks.label}`,
          JSON.stringify({ hidden: now.hidden, words: now.words }),
        );
        for (const [part, ink] of Object.entries(inks.reference)) {
          check(
            `${at}: ${part} is the component's ink and weight`,
            JSON.stringify(inks.row[part]) === JSON.stringify(ink),
            `${JSON.stringify(inks.row[part])} ${JSON.stringify(ink)}`,
          );
        }
        // The open row's mark is its item's: one ground under its run and its last line, which
        // the link does not paint over, and the bar down the link's edge.
        const mark = inks.highlight;
        check(
          `${at}: the open row's highlight is its item's, one ground under it and one bar down its edge`,
          mark.selected &&
            mark.item === tokens.highlight &&
            mark.row[0] === tokens.none &&
            mark.row[1] === tokens.bar &&
            mark.row[2] === "2px" &&
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
          // As Chrome computes it for assistive technology: the row is described by its lines'
          // words, hidden as they are, and the toggle itself is no node of the tree, whose items'
          // children are only rows and groups.
          await browser.send("Accessibility.enable");
          const row106 = await axOf('a.github-pulls-row[data-number="106"]');
          const line106 = await axOf('.github-pulls-change[data-number="106"]');
          await browser.send("Accessibility.disable");
          check(
            `${at}: #106's row is described by its lines' words, and the toggle is hidden from the tree`,
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
    // A change of no lines and one of additions alone (mb-efum): a zero total is left out,
    // and "0 lines" is muted, at the line's weight, and whole in the run.
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
        check(
          `${at} zero totals: #106 says "0 lines", in words "no lines changed"`,
          none.said === "0 lines" &&
            none.text === "0 lines" &&
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
          `${at} zero totals: "0 lines" is whole on the last line, before the chevron`,
          none.statsWhole &&
            within(none.line, none.tail) &&
            none.stats.right <= none.chevron.left + TOLERANCE_PX &&
            none.chevron.right <= none.tail.right + TOLERANCE_PX,
          JSON.stringify({ stats: none.stats, chevron: none.chevron, tail: none.tail }),
        );
        const shape = rowShape(none);
        check(
          `${at} zero totals: #106's row is its run, ending with the author, and its last line, the toggle and the age`,
          shape.ok,
          JSON.stringify(shape.parts ?? shape.why),
        );
        measured.zeroTotals[at] = {
          runLines: none.runLines.length,
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
      "the real lines are measured in the run's type",
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
   * inner target's, the item's focus ring, presses on the title, the number, the author,
   * and the last line past the chevron, and presses on the chevron and the lines.
   */
  async function interact(at, tokens) {
    const result = {};
    const ROW = 'a.github-pulls-row[data-number="106"]';
    const CHANGE = '.github-pulls-change[data-number="106"]';
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
    // Hover: the title, the number, and the age, then the lines and the chevron. Every part
    // hovers the item's one ground; only the toggle, the lines and the chevron, also lights its
    // chevron.
    await pointAt(`${ROW} .github-pulls-title`, false, "first");
    result.hoverTitle = await look();
    await shot(name("hover-item"), 299);
    await pointAt(`${ROW} .github-pulls-number`, false);
    result.hoverNumber = await look();
    await pointAt(`${ROW} .github-pulls-age`, false);
    result.hoverAge = await look();
    await pointAt(`${CHANGE} .change-line`, false);
    result.hoverLines = await look();
    await shot(name("hover-inner"), 299);
    await pointAt(`${CHANGE} > .github-pulls-toggle`, false);
    result.hoverChevron = await look();
    await browser.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1200, y: 880 });
    await frames();
    result.away = await look();
    const outer = (seen) =>
      seen.item === tokens.hover && seen.row === tokens.none && seen.change === tokens.none;
    const hovers = [
      result.hoverTitle,
      result.hoverNumber,
      result.hoverAge,
      result.hoverLines,
      result.hoverChevron,
    ];
    check(
      `${at}: the pointer anywhere on a pull request hovers its one item`,
      hovers.every(outer) && result.away.item !== tokens.hover,
      JSON.stringify({ ...result, tokens }),
    );
    check(
      `${at}: the toggle, the lines and the chevron, adds the inner target's hover, the chevron's plate, and no other part does`,
      [result.hoverLines, result.hoverChevron].every(
        (seen) => seen.plate === tokens.plate && seen.chevron === tokens.text,
      ) &&
        [result.hoverTitle, result.hoverNumber, result.hoverAge, result.away].every(
          (seen) => seen.plate === tokens.none && seen.chevron !== tokens.text,
        ),
      JSON.stringify({ ...result, tokens }),
    );
    // The focus ring: Tab to the list's stop, as a keyboard reader does. The stop is the row's
    // link, and the ring is drawn round its item; the toggle is no stop.
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
      const change = item?.querySelector(".github-pulls-change") ?? null;
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
      `${at}: Tab's stop is a row's link, its item takes the ring, and its toggle is no stop`,
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
    // A press on the title, the number, or the author opens the pull request and expands
    // nothing (mb-pw8t).
    const state = `(() => {
      const row = document.querySelector(${JSON.stringify(ROW)});
      const change = document.querySelector(${JSON.stringify(CHANGE)});
      const item = row?.closest("li");
      const files = item?.querySelector(".github-pull-files");
      const box = (el) => el ? el.getBoundingClientRect().toJSON() : null;
      return {
        expanded: row?.getAttribute("aria-expanded") ?? null,
        turned: change?.querySelector(".toggle-chevron") ? getComputedStyle(change.querySelector(".toggle-chevron")).transform : null,
        files: files && files.isConnected && !files.hidden && files.getBoundingClientRect().height > 0 ? box(files) : null,
        row: box(row), opened: [...window.__opened],
      };
    })()`;
    const opens = (seen, was) =>
      seen.opened.length === was.length + 1 &&
      seen.opened.at(-1) === 106 &&
      seen.expanded === "false" &&
      seen.files === null;
    const opened = await browser.evaluate(`[...window.__opened]`);
    await pointAt(`${ROW} .github-pulls-title`, true, "first");
    result.title = await browser.evaluate(state);
    check(
      `${at}: a press on a row's title opens the pull request and expands nothing`,
      opens(result.title, opened),
      JSON.stringify(result.title),
    );
    await pointAt(`${ROW} .github-pulls-number`, true);
    await pause(250);
    result.number = await browser.evaluate(state);
    check(
      `${at}: a press on a row's number opens the pull request and expands nothing`,
      opens(result.number, result.title.opened) &&
        Math.abs(result.number.row.top - result.title.row.top) <= TOLERANCE_PX,
      JSON.stringify(result.number),
    );
    // A press on the last line past the chevron, the item's link's, opens the pull request too
    // (mb-rb3n).
    result.lastPastChevron = await browser.evaluate(
      `(() => { const tail = document.querySelector(${JSON.stringify(`${ROW} > .github-pulls-tail`)}); const chevron = tail?.querySelector(".github-pulls-toggle"); return tail !== null && chevron !== null && tail.getBoundingClientRect().right - 4 > chevron.getBoundingClientRect().right; })()`,
    );
    await pointAt(`${ROW} > .github-pulls-tail`, true, "end");
    await pause(250);
    result.last = await browser.evaluate(state);
    check(
      `${at}: a press on a row's last line past the chevron opens the pull request and expands nothing`,
      result.lastPastChevron &&
        opens(result.last, result.number.opened) &&
        Math.abs(result.last.row.top - result.title.row.top) <= TOLERANCE_PX,
      JSON.stringify({ past: result.lastPastChevron, last: result.last }),
    );
    // A press on the chevron opens the files, under the row, and opens no page.
    await pointAt(`${CHANGE} > .github-pulls-toggle`, true);
    // Past the chevron's turn, a --transition-fast.
    await pause(250);
    await browser
      .waitFor(
        `document.querySelector(${JSON.stringify(ROW)})?.closest("li")?.querySelector(".github-pull-files-rows")?.firstElementChild != null`,
        5000,
      )
      .catch(() => false);
    result.chevron = await browser.evaluate(state);
    check(
      `${at}: a press on the chevron opens the files under the row and opens no page`,
      result.chevron.expanded === "true" &&
        result.chevron.files !== null &&
        result.chevron.files.top >= result.chevron.row.bottom - TOLERANCE_PX &&
        result.chevron.turned !== result.title.turned &&
        result.chevron.opened.length === result.last.opened.length,
      JSON.stringify(result.chevron),
    );
    // The row pressed stays under the pointer: its files open below it, even above the row a
    // reveal placed, #105, the open one, whose place gives way to the reader's press.
    check(
      `${at}: a press on the chevron leaves its row where it was`,
      result.chevron.row !== null &&
        result.title.row !== null &&
        Math.abs(result.chevron.row.top - result.title.row.top) <= TOLERANCE_PX,
      JSON.stringify({ before: result.title.row, after: result.chevron.row }),
    );
    // A press on the lines closes them again.
    await pointAt(`${CHANGE} .change-line`, true);
    await pause(250);
    result.line = await browser.evaluate(state);
    check(
      `${at}: a press on the lines closes the files, opens no page, and leaves the row where it was`,
      result.line.expanded === "false" &&
        result.line.files === null &&
        result.line.turned === result.title.turned &&
        result.line.opened.length === result.last.opened.length &&
        result.line.row !== null &&
        Math.abs(result.line.row.top - result.title.row.top) <= TOLERANCE_PX,
      JSON.stringify(result.line),
    );
    // Right and Left on the item, its handle's `expand` and `collapse`, keep its row where it
    // is too, over #105, the open row, placed again by a reveal before each.
    const ROW106 = `document.querySelector(${JSON.stringify(ROW)})`;
    for (const [handler, key, want] of [
      ["expand", "Right", "true"],
      ["collapse", "Left", "false"],
    ]) {
      await browser.evaluate(`window.__panel.setCurrent(105, null, { again: true }), true`);
      await frames();
      // The reveal made #105 the list's Tab stop, and the press on #106 left focus on its row:
      // the key acts on #106, the item with focus, not on the Tab stop.
      await browser.evaluate(`${ROW106}.focus(), true`);
      const before = await browser.evaluate(`${ROW106}.getBoundingClientRect().top`);
      await browser.evaluate(`window.__panel.${handler}(), true`);
      await pause(250);
      if (want === "true") {
        await browser
          .waitFor(
            `${ROW106}.closest("li").querySelector(".github-pull-files-rows")?.firstElementChild != null`,
            5000,
          )
          .catch(() => false);
        await frames();
      }
      const moved = {
        before,
        after: await browser.evaluate(`${ROW106}.getBoundingClientRect().top`),
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
   * A walk and a reveal bring a pull request's whole item into view: its run and its last
   * line, and the focus ring round them (`itemElement` in pulls-panel.js).
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
          const below = rows.findIndex((row) => zoneOf(row).getBoundingClientRect().bottom > view.bottom + 1);
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
          last: where(zone.querySelector(".github-pulls-tail")),
          link: where(below), focused: document.activeElement === below,
        };
      })()`);
    const whole = (seen) =>
      seen.zone !== null &&
      seen.last !== null &&
      seen.zone.top >= seen.view.top - TOLERANCE_PX &&
      seen.zone.bottom <= seen.view.bottom + TOLERANCE_PX &&
      seen.last.bottom <= seen.view.bottom + TOLERANCE_PX;
    await browser.evaluate(`document.getElementById("pane").scrollTop = 0, true`);
    await frames();
    result.before = await place(null);
    check(
      `${at}: an item lies just below the pane's fold, its last line out of view`,
      result.before.numbers !== null &&
        result.before.above.bottom <= result.before.view.bottom + TOLERANCE_PX &&
        result.before.last.bottom > result.before.view.bottom + TOLERANCE_PX,
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
      `${at}: Down onto the item just below the fold brings all of it into view, its last line too`,
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
