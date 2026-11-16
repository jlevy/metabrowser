// A commit's page with its Diff summary, laid out by a real engine: the commit summary the
// Git panel draws (`renderCommitSummary`) and the Diff summary the diff plugin draws in its
// place (`mountDiffSummary`), under the shell's and the diff plugin's stylesheets and
// KPress's faces, in headless Chrome.
//
//   CHROME_BIN=/path/to/chrome KPRESS_STATIC=/dir/with/css/and/fonts \
//     CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/git-commit-summary-chrome.mjs
//
// tests/test_git_commit_summary_chrome.py owns the profile, copies KPress's tokens and faces
// into KPRESS_STATIC, and runs this in a process group of its own.
//
// Which markup the summary has, and that the commit's diff is handed the place to draw its
// Diff summary in, are browserless (tests/dom/git-panel-behavior.js, and
// tests/dom/diff-view-behavior.js for the place). What only a browser can tell is where it
// lands: at the page's top, under the commit's identity and above its description, on the
// summary's content edge, its header one row at the widths it fits in; its tree opening
// under its header and above the description; the commit's totals in one line where no diff
// was drawn; and an empty place, for a commit with no count of files, taking no room
// (docs/design-system.md, "Git Commit Summary" and "Diff Summary").
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const DIFF = path.join(root, "src/metabrowser/builtin_plugins/diff");
const KPRESS = process.env.KPRESS_STATIC ? path.resolve(process.env.KPRESS_STATIC) : null;
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

// The shell's startup scripts the Git panel needs, in the shell's order, then the shared
// changed-files tree the Diff summary is drawn on.
const SCRIPTS = [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
  "inert-html.js",
  "plugin-sdk.js",
  "plugin-sdk-views.js",
  "keyboard-shortcuts.js",
  "overlay-layer.js",
  "git-graph.js",
  "git-history-window.js",
  "git-panel.js",
  "changed-files-tree.js",
];
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>commit summary</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/diff/styles.css">
<script>
  window.METABROWSER_SETTINGS = { SYNTAX_HIGHLIGHT_MAX_BYTES: 524288, SYNTAX_LANGUAGE_BY_BASENAME: {}, SYNTAX_LANGUAGE_BY_EXTENSION: {} };
  window.MetabrowserIcons = { copy: '<svg data-icon="copy"></svg>' };
</script>
${SCRIPTS.map((name) => `<script src="/static/${name}"></script>`).join("\n")}
</head><body><div id="preview-pane" class="preview-pane"></div></body></html>`;

const TYPES = {
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
};
function serve() {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://localhost");
    let file = null;
    if (url.pathname === "/") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(PAGE);
      return;
    }
    if (url.pathname.startsWith("/static/")) {
      file = path.join(STATIC, url.pathname.slice(8));
    } else if (url.pathname.startsWith("/diff/")) {
      file = path.join(DIFF, url.pathname.slice(6));
    } else if (KPRESS && url.pathname.startsWith("/kpress/")) {
      file = path.join(KPRESS, url.pathname.slice(8));
    }
    const within = [root, KPRESS].filter(Boolean).some((dir) => file?.startsWith(dir + path.sep));
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

// The pane widths the page is read at: a wide pane, the default, and a narrow one.
const WIDTHS = [980, 760, 560, 420, 320];

// In the page: draw a commit's page at each width, its Diff summary in its place, and read
// where the summary's parts are; then open the summary; then draw the page with no diff.
const MEASURE = `async (widths) => {
  const internals = window.MetabrowserGitPanel._internals;
  const diff = await import("/diff/diff-view.js");
  const pane = document.getElementById("preview-pane");
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const until = async (test, what) => {
    const deadline = performance.now() + 10000;
    while (performance.now() < deadline) {
      if (test()) return;
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    throw new Error("timed out waiting for " + what);
  };
  const round = (value) => Math.round(value * 100) / 100;
  const box = (node) => {
    const rect = node.getBoundingClientRect();
    return { top: round(rect.top), bottom: round(rect.bottom), left: round(rect.left), height: round(rect.height) };
  };
  const now = Date.now() / 1000 - 3600;
  const detail = {
    commit: {
      id: "c".repeat(40), short_id: "ccccccc", parent_ids: ["d".repeat(40)],
      author: { name: "Author", email: "a@example.invalid" },
      authored_at: now, committed_at: now, subject: "Consolidate the diff summaries", refs: [],
    },
    stats: { files_changed: 35, files_added: 2, files_deleted: 3, files_modified: 30, additions: 1234, deletions: 3423 },
    body: "Its counts are the Diff summary's header.\\nAnd its tree is the commit's files.",
    files: [],
  };
  // The change set the commit's diff reads: 35 files, 2 added, 3 removed, 30 modified.
  const kinds = [...Array(2).fill("added"), ...Array(3).fill("deleted"), ...Array(30).fill("modified")];
  const files = kinds.map((kind, at) => ({
    kind,
    ...(kind === "added" ? {} : { old: { path: "src/f" + at + ".py" } }),
    ...(kind === "deleted" ? {} : { new: { path: "src/f" + at + ".py" } }),
    additions: 30,
    deletions: 90,
  }));
  const document_ = { manifest: { totals: { files: 35, additions: 1234, deletions: 3423, exact: true }, files } };
  const draw = (width, withDiff, shown = detail) => {
    pane.style.width = width + "px";
    const stage = document.createElement("div");
    stage.className = "git-commit-stage";
    stage.innerHTML = '<div class="git-commit-view">' + internals.renderCommitSummary(shown) + "</div>";
    pane.replaceChildren(stage);
    const place = stage.querySelector(".git-commit-diff-summary");
    const handle = withDiff
      ? diff.mountDiffSummary(place, document_, window.metabrowser, {
          changedFiles: window.MetabrowserChangedFilesTree,
          openFile() {},
        })
      : null;
    return { stage, place, handle };
  };
  await document.fonts.ready;
  const out = { widths: {}, opened: null, totals: null, empty: null };
  for (const width of widths) {
    const { stage, place, handle } = draw(width, true);
    await frames();
    const subject = stage.querySelector(".git-commit-subject");
    const meta = stage.querySelector(".git-commit-meta");
    const body = stage.querySelector(".git-commit-body");
    const toggle = place.querySelector(".diff-summary");
    out.widths[width] = {
      subject: box(subject),
      meta: box(meta),
      place: box(place),
      toggle: toggle ? box(toggle) : null,
      body: box(body),
      rowHeight: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height")) || null,
      text: toggle?.querySelector(".diff-summary-files")?.parentElement?.textContent ?? null,
      hang: toggle ? parseFloat(getComputedStyle(toggle).marginLeft) : null,
      stats: stage.querySelectorAll(".git-commit-change-stats").length,
      inHeader: place.parentElement?.classList.contains("git-commit-header") ?? false,
    };
    handle.dispose();
  }
  // Opened: the tree under its header, above the description.
  {
    const { stage, place, handle } = draw(760, true);
    await frames();
    const toggle = place.querySelector(".diff-summary-toggle");
    toggle.click();
    await until(() => {
      const body = place.querySelector(".diff-summary-body");
      return body && !body.classList.contains("diff-summary-body-collapsed") && body.querySelector('[role="treeitem"]');
    }, "the summary's tree");
    await frames();
    const tree = place.querySelector(".diff-summary-body");
    out.opened = {
      toggle: box(toggle),
      tree: box(tree),
      description: box(stage.querySelector(".git-commit-body")),
      inPlace: place.contains(tree),
      treeRows: tree.querySelectorAll('[role="treeitem"]').length,
    };
    handle.dispose();
  }
  // No diff drawn: the place says the commit's totals in one line, worded as a diff's line
  // is without its tree (A6 of review A on #470).
  {
    const { stage, place } = draw(760, false);
    await frames();
    const line = place.querySelector(".diff-summary");
    out.totals = {
      display: getComputedStyle(place).display,
      text: line?.textContent ?? null,
      line: line ? box(line) : null,
      rowHeight: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height")) || null,
      place: box(place),
      meta: box(stage.querySelector(".git-commit-meta")),
    };
  }
  // A commit with no count of files: the place is empty and takes no room.
  {
    const { stage, place } = draw(760, false, { ...detail, stats: {} });
    await frames();
    out.empty = {
      display: getComputedStyle(place).display,
      height: box(place).height,
      meta: box(stage.querySelector(".git-commit-meta")),
      body: box(stage.querySelector(".git-commit-body")),
    };
  }
  // The hover summary keeps its two rows of counts.
  {
    const tip = document.createElement("div");
    tip.className = "custom-tooltip";
    tip.innerHTML = internals.renderCommitTooltip(detail);
    pane.replaceChildren(tip);
    out.tooltip = {
      stats: tip.querySelectorAll(".git-commit-change-stats").length,
      place: tip.querySelectorAll(".git-commit-diff-summary").length,
    };
  }
  pane.replaceChildren();
  return out;
}`;

async function main() {
  const bin = process.env.CHROME_BIN;
  if (!bin) {
    throw new Error("CHROME_BIN names no Chrome");
  }
  if (!KPRESS || !fs.existsSync(path.join(KPRESS, "css/style-tokens.css"))) {
    throw new Error("KPRESS_STATIC holds no css/style-tokens.css");
  }
  const profiles = process.env.CHROME_PROFILES;
  if (!profiles) {
    throw new Error("CHROME_PROFILES names no directory for Chrome's profile");
  }
  const began = performance.now();
  const lap = (step) =>
    process.stderr.write(`${step} at ${Math.round(performance.now() - began)} ms\n`);
  const server = await serve();
  try {
    const browser = await launchChrome(bin, { profiles });
    lap("Chrome started");
    try {
      await browser.send("Page.enable");
      await browser.send("Page.navigate", { url: `http://127.0.0.1:${server.address().port}/` });
      await browser.waitFor(
        `document.readyState === "complete" && Boolean(window.MetabrowserGitPanel) && Boolean(window.MetabrowserChangedFilesTree) && Boolean(window.metabrowser)`,
      );
      lap("the page loaded");
      const measured = await browser.evaluate(`(${MEASURE})(${JSON.stringify(WIDTHS)})`);
      lap("every width drawn");
      for (const width of WIDTHS) {
        const at = measured.widths[width];
        const where = `at ${width} px`;
        check(`${where}: the page draws its Diff summary`, at?.toggle !== null, JSON.stringify(at));
        if (!at?.toggle) {
          continue;
        }
        check(
          `${where}: the Diff summary's header says the commit's counts`,
          at.text?.includes("35 changed files") &&
            at.text.includes("2 added, 3 removed, 30 modified") &&
            at.text.includes("+1,234") &&
            at.text.includes("−3,423"),
          String(at.text),
        );
        check(`${where}: the commit's stats block is gone`, at.stats === 0, String(at.stats));
        check(
          `${where}: the summary is in the commit's header`,
          at.inHeader === true,
          JSON.stringify(at),
        );
        check(
          `${where}: the summary is under the commit's identity`,
          at.place.top >= at.meta.bottom - 0.5,
          JSON.stringify({ meta: at.meta, place: at.place }),
        );
        check(
          `${where}: the summary is above the commit's description`,
          at.place.bottom <= at.body.top + 0.5,
          JSON.stringify({ place: at.place, body: at.body }),
        );
        // The place starts where the subject does; the header in it hangs by the toggle's own
        // margin, as every Diff summary's does, and by nothing of the commit page's.
        check(
          `${where}: the summary starts on the subject's edge`,
          Math.abs(at.place.left - at.subject.left) <= 0.5 &&
            at.hang !== null &&
            Math.abs(at.toggle.left - (at.place.left + at.hang)) <= 0.5,
          JSON.stringify({
            subject: at.subject,
            place: at.place,
            toggle: at.toggle,
            hang: at.hang,
          }),
        );
      }
      // One row where the header fits on one line: at the default pane and wider.
      for (const width of WIDTHS.filter((each) => each >= 560)) {
        const at = measured.widths[width];
        check(
          `at ${width} px: the summary's header is one row`,
          at?.toggle !== null &&
            at.rowHeight !== null &&
            Math.abs(at.toggle.height - at.rowHeight) <= 0.5,
          JSON.stringify(at?.toggle),
        );
      }
      const opened = measured.opened;
      check(
        "opened, the summary's tree is in its place, under its header",
        opened?.inPlace === true && opened.tree.top >= opened.toggle.bottom - 0.5,
        JSON.stringify(opened),
      );
      check(
        "opened, the summary's tree is above the commit's description",
        opened !== null && opened.tree.bottom <= opened.description.top + 0.5,
        JSON.stringify(opened),
      );
      check("opened, the tree draws rows", (opened?.treeRows ?? 0) > 0, JSON.stringify(opened));
      const totals = measured.totals;
      check(
        "with no diff drawn, the place says the commit's totals in one line",
        totals?.display !== "none" &&
          totals?.text === "35 changed files +1,234 \u22123,423" &&
          totals.line !== null &&
          totals.rowHeight !== null &&
          totals.line.height <= totals.rowHeight + 0.5 &&
          totals.place.top >= totals.meta.bottom - 0.5,
        JSON.stringify(totals),
      );
      const empty = measured.empty;
      check(
        "with no count of files, the empty place takes no room",
        empty?.display === "none" && empty.height === 0,
        JSON.stringify(empty),
      );
      check(
        "the hover summary keeps its two rows of counts and has no Diff summary",
        measured.tooltip?.stats === 1 && measured.tooltip.place === 0,
        JSON.stringify(measured.tooltip),
      );
      if (process.env.MEASURE_OUT) {
        fs.writeFileSync(process.env.MEASURE_OUT, JSON.stringify(measured, null, 2));
      }
    } finally {
      await browser.close();
      lap("Chrome stopped");
    }
  } finally {
    server.close();
  }
  if (failures.length) {
    console.error(failures.join("\n"));
    process.exitCode = 1;
    return;
  }
  console.log(`commit summary in Chrome: ${checks} checks passed`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
