// The two trees of a change set's files, laid out by a real engine: a pull request's
// changed files under its Pulls row (builtin_plugins/github/pull-files-view.js) and a
// multi-file diff's Diff summary (builtin_plugins/diff/diff-summary.js), each mounted by its
// production module on one list of files, side by side in headless Chrome, under the shell's
// and both plugins' stylesheets.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/changed-file-rows-chrome.mjs
//
// tests/test_changed_file_rows_chrome.py owns the profile, runs this in a process group of
// its own, and judges the one JSON line it prints. What it measures is layout and paint,
// which no browserless DOM computes: for a folder's row and a file's at one depth in each
// tree, the row's height, where its content starts past the depth's indent, where the
// chevron or change letter and the name start, where the counts end, the gap, the type, the
// hover ground, and the focus ring; and a folder's tooltip. Both trees draw the shell's
// changed-file rows (static/styles.css, `.changed-file-row`; docs/design-system.md, "Diff
// Summary"), so each of those is one value in both. Rows and their parts are found by role
// and order, not by the shared classes, so the session reads a tree that does not use them.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const root = path.resolve(import.meta.dirname, "../..");
const DIRS = {
  "/static/": path.join(root, "src/metabrowser/static"),
  "/github/": path.join(root, "src/metabrowser/builtin_plugins/github"),
  "/diff/": path.join(root, "src/metabrowser/builtin_plugins/diff"),
};
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>changed file rows</title>
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/github/styles.css">
<link rel="stylesheet" href="/diff/styles.css">
<script src="/static/changed-files-tree.js"></script>
<style>body { display: flex; gap: 24px; margin: 0; } .host { width: 360px; }</style>
</head><body>
<div class="host github-pulls"><div class="tree-content" id="pulls-scroll"><ul><li id="pulls-item"><a id="pulls-owner" aria-level="1" href="#">#7</a></li></ul></div></div>
<div class="host metabrowser-diff-host" id="diff-host"></div>
</body></html>`;
const TYPES = { ".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml" };

function serve() {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    if (url.pathname === "/") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(PAGE);
      return;
    }
    const prefix = Object.keys(DIRS).find((each) => url.pathname.startsWith(each));
    const file = prefix ? path.join(DIRS[prefix], url.pathname.slice(prefix.length)) : null;
    if (!file?.startsWith(DIRS[prefix]) || !fs.existsSync(file)) {
      response.writeHead(404);
      response.end();
      return;
    }
    response.writeHead(200, { "content-type": TYPES[path.extname(file)] ?? "text/plain" });
    fs.createReadStream(file).pipe(response);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

// In the page: one list, a folder with a file and another holding a file whose line counts
// are unknown, as a binary file's are; both trees mounted on it, open.
const MOUNT = `(async () => {
  const tree = window.MetabrowserChangedFilesTree;
  const files = [
    { path: "docs/new.md", display: "docs/new.md", previous_path: null, previous_display: null, status: "added", additions: 12, deletions: 0 },
    { path: "src/app.txt", display: "src/app.txt", previous_path: null, previous_display: null, status: "modified", additions: 3, deletions: 1 },
    { path: "src/logo.png", display: "src/logo.png", previous_path: null, previous_display: null, status: "modified", additions: null, deletions: null },
  ];
  const formatCount = (count) => count.toLocaleString("en-US");
  const chevron = () => {
    const box = document.createElement("span");
    box.innerHTML = '<svg class="toggle-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="m9 18 6-6-6-6"/></svg>';
    return box.firstElementChild;
  };
  // The Pulls tab's tree, as pulls-panel.js mounts it under a pull request's row.
  const { mountFileTree } = await import("/github/pull-files-view.js");
  const listing = {
    state: "current", reason: null, number: 7, listed_from: "github",
    source: "https://github.com/octo/demo", generation: "0".repeat(32),
    fetched_at: "2026-11-15T00:00:00Z", reader: "gh:test", head: null, base: null,
    fresh_for_s: 60, refreshing: false, last_refresh: null, fetched: files.length, pages: 1,
    last_page: null, complete: true, capped: false, truncated: false, offset: 0, limit: 3000,
    rows: files,
  };
  const pulls = mountFileTree({
    number: 7, autoExpandFiles: 3000, current: null, shown: true,
    scrollRoot: document.getElementById("pulls-scroll"),
    chevron, href: (file) => "#" + file,
    request: async () => ({ status: 200, etag: null, body: listing }),
    formatTime: (value) => value,
    decorateExternalLink: (anchor) => anchor,
    page: () => null, open() {}, leave() {}, focusedIn() {},
    tree, formatCount,
  });
  pulls.attach(document.getElementById("pulls-item"), document.getElementById("pulls-owner"));
  pulls.controller.expand();
  // The Diff summary's tree, as diff-view.js mounts it under its header.
  const { mountSummaryTree } = await import("/diff/diff-summary.js");
  const summary = mountSummaryTree({ tree, files, id: "summary-tree", formatCount, chevron, jump() {} });
  document.getElementById("diff-host").append(summary.body);
  summary.setOpen(true);
  const frame = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  for (let at = 0; at < 100 && document.querySelectorAll('#pulls-item [role="treeitem"]').length < 5; at += 1) {
    await frame();
  }
  await frame();
  return document.querySelectorAll('[role="treeitem"]').length;
})()`;

const ROOTS = { pulls: "#pulls-item", summary: "#diff-host" };

// In the page: a row's geometry and type, its parts found by order (the lead, the name, the
// counts), and its depth's indent resolved where the row is.
const ROWS = `(() => {
  const round = (value) => Math.round(value * 100) / 100;
  // Each plugin's depth indent, the formula it gives its rows.
  const DEPTH = {
    pulls: "calc(var(--github-pulls-indent, 0px) + var(--github-pull-file-depth, 1) * var(--tree-indent))",
    summary: "calc(var(--diff-summary-depth, 0) * var(--tree-indent))",
  };
  const indentOf = (row, tree) => {
    const probe = document.createElement("span");
    probe.style.cssText = "position: absolute; visibility: hidden; width: " + DEPTH[tree];
    row.append(probe);
    const width = probe.getBoundingClientRect().width;
    probe.remove();
    return width;
  };
  const of = (row, tree) => {
    if (!row) return null;
    const box = row.getBoundingClientRect();
    const s = getComputedStyle(row);
    const content = box.left + parseFloat(s.borderLeftWidth) + parseFloat(s.paddingLeft);
    const [lead, name, stats] = row.children;
    return {
      height: round(box.height),
      level: row.getAttribute("aria-level"),
      contentFromRow: round(content - box.left),
      lead: round(lead.getBoundingClientRect().left - content),
      leadWidth: round(lead.getBoundingClientRect().width),
      name: round(name.getBoundingClientRect().left - content),
      statsEnd: stats ? round(box.right - stats.getBoundingClientRect().right) : null,
      gap: s.columnGap,
      size: s.fontSize,
      color: s.color,
      bar: s.borderLeftWidth,
      radius: s.borderTopLeftRadius,
      indent: round(indentOf(row, tree)),
    };
  };
  const out = {};
  for (const [tree, selector] of Object.entries(${JSON.stringify(ROOTS)})) {
    const rows = [...document.querySelectorAll(selector + ' [role="treeitem"]')];
    const pick = (id) => rows.find((row) => row.dataset.id === id) ?? null;
    out[tree] = {
      ids: rows.map((row) => row.dataset.id),
      folder: of(pick("docs/"), tree),
      file: of(pick("docs/new.md"), tree),
      // A folder whose sums leave a file out says what, and only that.
      tip: pick("src/")?.dataset.tipText ?? null,
      label: pick("src/")?.getAttribute("aria-label") ?? null,
    };
  }
  return out;
})()`;

const STATE = (selector) => `(() => {
  const row = document.querySelector(${JSON.stringify(selector)});
  const s = getComputedStyle(row);
  return { background: s.backgroundColor, outline: [s.outlineStyle, s.outlineWidth, s.outlineOffset].join(" "), focusVisible: row.matches(":focus-visible") };
})()`;

const profiles = process.env.CHROME_PROFILES;
if (!process.env.CHROME_BIN || !profiles) {
  throw new Error("CHROME_BIN and CHROME_PROFILES are required");
}
const server = await serve();
const result = {};
try {
  const browser = await launchChrome(process.env.CHROME_BIN, {
    profiles,
    width: 1000,
    height: 600,
  });
  try {
    const errors = [];
    browser.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
      errors.push(exceptionDetails.exception?.description ?? exceptionDetails.text),
    );
    await browser.send("Runtime.enable");
    await browser.send("Page.enable");
    await browser.send("Page.navigate", { url: `http://127.0.0.1:${server.address().port}/` });
    await browser.waitFor(
      `document.readyState === "complete" && window.MetabrowserChangedFilesTree !== undefined`,
    );
    result.drawn = await browser.evaluate(MOUNT);
    result.rows = await browser.evaluate(ROWS);
    // The hover, where the pointer rests on a row, and the ring, where focus lands after a
    // key: a key first, so Chrome draws focus as the keyboard's.
    const pointer = (x, y) =>
      browser.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
    await browser.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: "Shift",
      code: "ShiftLeft",
    });
    await browser.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: "Shift",
      code: "ShiftLeft",
    });
    result.states = {};
    for (const [tree, rootSelector] of Object.entries(ROOTS)) {
      result.states[tree] = {};
      for (const id of ["docs/", "docs/new.md"]) {
        const selector = `${rootSelector} [role="treeitem"][data-id="${id}"]`;
        await pointer(990, 590);
        const rest = await browser.evaluate(STATE(selector));
        const at = await browser.evaluate(
          `(() => { const r = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`,
        );
        await pointer(at.x, at.y);
        await browser.evaluate(
          "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))",
        );
        const hovered = await browser.evaluate(STATE(selector));
        await pointer(990, 590);
        await browser.evaluate(`document.querySelector(${JSON.stringify(selector)}).focus(), true`);
        const focused = await browser.evaluate(STATE(selector));
        result.states[tree][id] = { rest, hover: hovered.background, focus: focused };
      }
    }
    result.errors = errors;
  } finally {
    await browser.close();
  }
} finally {
  server.close();
}
process.stdout.write(`${JSON.stringify(result)}\n`);
