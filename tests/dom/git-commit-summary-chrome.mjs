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
import { STATUS_COUNTS } from "./status-count-paint.mjs";

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

// In the page: a change set five folders deep, and a function that opens the Diff summary
// drawn in a place and reads where its header and every row of its tree start, once its
// travel is over (docs/design-system.md, "Diff Summary": the tree's first level starts one
// --tree-indent in from the header, and each level one more).
const NESTED_SUMMARY = `(() => {
  const paths = ["top.py", "a/f.py", "a/b/f.py", "a/b/c/f.py", "a/b/c/d/f.py", "a/b/c/d/g.py"];
  const files = paths.map((path) => ({ kind: "modified", old: { path }, new: { path }, additions: 1, deletions: 0 }));
  return { manifest: { totals: { files: paths.length, additions: paths.length, deletions: 0, exact: true }, files } };
})()`;
const SUMMARY_INDENT = `async (place) => {
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const toggle = place.querySelector(".diff-summary-toggle");
  toggle.click();
  const deadline = performance.now() + 10000;
  const open = () => {
    const body = place.querySelector(".diff-summary-body");
    return body && !body.classList.contains("diff-summary-body-collapsed") && body.querySelector('[role="treeitem"]');
  };
  while (!open() && performance.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  // The box travels open in --transition-fast: wait for that travel itself, and for one that
  // replaced it, as a travel retargeted when the box's height changes is.
  const travels = () => place.querySelector(".diff-summary-body")?.getAnimations() ?? [];
  while (travels().length > 0 && performance.now() < deadline) {
    await Promise.allSettled(travels().map((travel) => travel.finished));
  }
  await frames();
  const left = (node) => Math.round(node.getBoundingClientRect().left * 100) / 100;
  return {
    step: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--tree-indent")),
    chevron: left(toggle.querySelector(".diff-summary-chevron")),
    // The header's words start at its change line: the file count is on the size line above.
    words: left(toggle.querySelector(".change-line")),
    rows: [...place.querySelectorAll('.diff-summary-body [role="treeitem"]')].map((row) => ({
      id: row.dataset.id,
      level: Number(row.getAttribute("aria-level")),
      lead: left(row.children[0]),
      name: left(row.children[1]),
    })),
  };
}`;
/** The rows of a measured tree that do not start one step per level in from its header. */
const offStep = (indent) =>
  indent === null
    ? ["not measured"]
    : indent.rows.filter(
        (row) =>
          Math.abs(row.lead - indent.chevron - indent.step * row.level) > 0.5 ||
          Math.abs(row.name - indent.words - indent.step * row.level) > 0.5,
      );

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
  // Each dot that sets a line's groups apart, and whether it starts a line of its own: the
  // part before it does not end on the line it is on.
  const dots = (line) =>
    [...line.querySelectorAll('.summary-punctuation[aria-hidden="true"]')].map((dot) => {
      const at = dot.getBoundingClientRect();
      const before = dot.previousElementSibling;
      const end = before ? [...before.getClientRects()].at(-1) : null;
      return {
        text: dot.textContent,
        top: round(at.top),
        startsLine: end === null || Math.abs(end.top - at.top) > 1 || end.right > at.left + 0.5,
      };
    });
  // How many lines a line's parts take: the distinct tops of their boxes, but for the text a
  // screen reader alone is told, which is on no line.
  const lines = (line) =>
    new Set(
      [...line.querySelectorAll("span:not(.visually-hidden)")].flatMap((node) =>
        [...node.getClientRects()].map((rect) => Math.round(rect.top)),
      ),
    ).size;
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
  // The change set the commit's diff reads: 35 files, 2 added, 3 deleted, 30 modified.
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
    const meta = stage.querySelector(".git-commit-ages");
    const body = stage.querySelector(".git-commit-body");
    const toggle = place.querySelector(".diff-summary");
    out.widths[width] = {
      subject: box(subject),
      meta: box(meta),
      place: box(place),
      toggle: toggle ? box(toggle) : null,
      body: box(body),
      rowHeight: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height")) || null,
      text: toggle?.textContent ?? null,
      dots: toggle ? dots(toggle) : null,
      lines: toggle ? lines(toggle) : null,
      hang: toggle ? parseFloat(getComputedStyle(toggle).marginLeft) : null,
      stats: stage.querySelectorAll(".git-commit-change-stats").length,
      inHeader: place.parentElement?.classList.contains("git-commit-header") ?? false,
    };
    handle.dispose();
  }
  // Every width from 60 to 400 px, 1 px apart: wherever the header wraps, it breaks after a
  // dot, never before one (A4 of review A on #479). The same sweep with each dot's group
  // dissolved, so that each dot is an item of its own again, is the control: a dot then
  // starts a line at some of these widths, so the check can fail (B2 of review B on #479).
  const sweepHeader = () => {
    const swept = [];
    for (let width = 60; width <= 400; width += 1) {
      const { place, handle } = draw(width, true);
      const toggle = place.querySelector(".diff-summary");
      swept.push({ width, lines: lines(toggle), starts: dots(toggle).filter((dot) => dot.startsLine).length });
      handle.dispose();
    }
    return swept;
  };
  out.sweep = sweepHeader();
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
  // Indented: a change set five folders deep, opened under the commit's identity.
  {
    const { place, handle } = draw(760, false);
    const nested = diff.mountDiffSummary(place, ${NESTED_SUMMARY}, window.metabrowser, {
      changedFiles: window.MetabrowserChangedFilesTree,
      openFile() {},
    });
    await frames();
    out.indent = await (${SUMMARY_INDENT})(place);
    nested.dispose();
    handle?.dispose();
  }
  // No diff drawn: the place says the commit's totals in one line, worded as a diff's line
  // is without its tree (A6 of review A on #470).
  {
    const { stage, place } = draw(760, false);
    await frames();
    const line = place.querySelector(".diff-summary");
    const sizeLine = stage.querySelector(".git-commit-size");
    out.totals = {
      display: getComputedStyle(place).display,
      text: line?.textContent ?? null,
      line: line ? box(line) : null,
      rowHeight: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height")) || null,
      place: box(place),
      meta: box(stage.querySelector(".git-commit-ages")),
      lines: line ? lines(line) : null,
      // The size line, the header's line above the Diff summary's place, says the file count.
      size: sizeLine ? { text: sizeLine.textContent, box: box(sizeLine) } : null,
    };
  }
  // A commit with no count of files: the place is empty and takes no room.
  {
    const { stage, place } = draw(760, false, { ...detail, stats: {} });
    await frames();
    out.empty = {
      display: getComputedStyle(place).display,
      height: box(place).height,
      meta: box(stage.querySelector(".git-commit-ages")),
      body: box(stage.querySelector(".git-commit-body")),
    };
  }
  // The hover summary says the commit's changes in the Diff summary's words and paint, in
  // each theme: the file count bold in the line's ink, each status count, number and letter,
  // bold in its status's ink, read with its contrast on the card's ground (mb-8iwn), and
  // each comma and dot muted (mb-khm6); narrowed, it wraps after a dot.
  {
    const tip = document.createElement("div");
    // Shown, as the SDK's tooltip shows one, so it is laid out.
    tip.className = "custom-tooltip visible";
    tip.style.display = "block";
    // With the commit's size, so its size line holds every kind of number it says.
    tip.innerHTML = internals.renderCommitSummary(detail, {
      compact: true,
      size: { base: null, head: detail.commit.id, state: "measured", reason: null, commits: 1, pushed_bytes: 58_270, diff_bytes: 198_540 },
    });
    pane.style.width = "980px";
    pane.replaceChildren(tip);
    const line = tip.querySelector(".git-commit-change-line");
    // The size line: its numbers bold in the line's own ink, its words regular, its dot muted,
    // never a status's color (docs/design-system.md, "Change Size Line").
    const sizeLine = tip.querySelector(".git-commit-size-line .change-size-line");
    const ink = (node) => getComputedStyle(node).color;
    const weight = (node) => getComputedStyle(node).fontWeight;
    const token = (name) => {
      const probe = document.createElement("span");
      probe.style.color = "var(" + name + ")";
      line.append(probe);
      const color = ink(probe);
      probe.remove();
      return color;
    };
    out.tooltip = {
      stats: tip.querySelectorAll(".git-commit-change-stats").length,
      place: tip.querySelectorAll(".git-commit-diff-summary").length,
      text: line?.textContent ?? null,
      hidden: line?.getAttribute("aria-hidden") ?? null,
      said: tip.querySelector(".git-commit-change-stats > .visually-hidden")?.textContent ?? null,
      paint: [],
    };
    for (const theme of ["light", "dark"]) {
      document.documentElement.dataset.theme = theme;
      await frames();
      // Once any cross-fade the theme started is over, so the card's ground is the theme's.
      await Promise.allSettled(
        document.getAnimations().filter((animation) => animation instanceof CSSTransition).map((animation) => animation.finished),
      );
      const tokens = {};
      for (const name of ["--text", "--muted", "--git-status-added", "--git-status-deleted", "--git-status-modified"]) {
        tokens[name] = token(name);
      }
      out.tooltip.paint.push({
        theme,
        tokens,
        line: { ink: ink(line), weight: weight(line) },
        words: ink(sizeLine),
        wordsWeight: weight(sizeLine),
        numbers: [...sizeLine.querySelectorAll(".summary-number")].map((node) => [node.textContent, ink(node), weight(node)]),
        sizeMarks: [...sizeLine.querySelectorAll(".summary-punctuation")].map((node) => [node.textContent, ink(node), weight(node)]),
        counts: (${STATUS_COUNTS})(line),
        marks: [...line.querySelectorAll(".summary-punctuation")].map((node) => [node.textContent, node.getAttribute("aria-hidden"), ink(node), weight(node)]),
      });
    }
    delete document.documentElement.dataset.theme;
    // Every width from 60 px to the card's own most, 360 px, 1 px apart: wherever it wraps, it
    // breaks after a dot; and with its groups dissolved, the control, a dot starts a line at
    // some of them (B2 of review B on #479).
    const sweepTip = () => {
      const swept = [];
      for (let width = 60; width <= 360; width += 1) {
        tip.style.width = width + "px";
        swept.push({ width, lines: lines(line), dots: dots(line).length, starts: dots(line).filter((dot) => dot.startsLine).length });
      }
      return swept;
    };
    out.tooltip.sweep = sweepTip();
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
          !at.text?.includes("files changed") &&
            at.text?.includes("2 A, 3 D, 30 M") &&
            at.text.includes("+1,234") &&
            at.text.includes("−3,423"),
          String(at.text),
        );
        // A header that wraps breaks after a dot: no dot starts a line (A4 of review A on
        // #479).
        check(
          `${where}: no line of the summary's header starts with its dot`,
          // One dot, between the statuses and the line totals: the file count is on the size
          // line above (docs/design-system.md, "Change Size Line").
          at.dots?.length === 1 && at.dots.every((dot) => !dot.startsLine),
          JSON.stringify(at.dots),
        );
        check(`${where}: the commit's stats block is gone`, at.stats === 0, String(at.stats));
        check(
          `${where}: the summary is in the commit's header`,
          at.inHeader === true,
          JSON.stringify(at),
        );
        check(
          `${where}: the summary is under the commit's metadata lines, its age the last`,
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
      // One row where the header fits on one line: at 420 px and wider, as the design system
      // says (B4 of review B on #479). Measured 2026-11-16 in Chrome, it fits from 373 px at the
      // body size, and from 354 px at the navigation rows' size it had before (mb-kisi).
      for (const width of WIDTHS.filter((each) => each >= 420)) {
        const at = measured.widths[width];
        check(
          `at ${width} px: the summary's header is one row`,
          at?.toggle !== null &&
            at.rowHeight !== null &&
            Math.abs(at.toggle.height - at.rowHeight) <= 0.5,
          JSON.stringify(at?.toggle),
        );
      }
      // At 320 px the header wraps, so its dots were read where a wrap can put them.
      check(
        "at 320 px: the summary's header wraps",
        (measured.widths[320]?.lines ?? 0) >= 2,
        JSON.stringify(measured.widths[320]),
      );
      const sweep = measured.sweep ?? [];
      check(
        "from 60 to 400 px, the summary's header never starts a line with its dot",
        sweep.length === 341 &&
          sweep.some((at) => at.lines >= 2) &&
          sweep.every((at) => at.starts === 0),
        JSON.stringify(sweep.filter((at) => at.starts > 0)),
      );
      // No control: its one dot follows the statuses, which the header cuts short rather than
      // wraps, so even with its group dissolved no wrap can put the dot first on a line. The
      // control had a dot after the file count, which is on the size line now.
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
      // Under the commit's identity, the tree's first level starts one step in from the
      // header and each level one more, at five depths (mb-hi4l).
      const indent = measured.indent ?? null;
      check(
        "opened under the commit's identity, the tree steps in from its header one level at a time",
        offStep(indent).length === 0 && new Set(indent.rows.map((row) => row.level)).size === 5,
        JSON.stringify(indent),
      );
      const totals = measured.totals;
      check(
        "with no diff drawn, the place says the commit's line totals in one line",
        totals?.display !== "none" &&
          totals?.text === "+1,234\u22123,423" &&
          totals.lines === 1 &&
          totals.line !== null &&
          totals.rowHeight !== null &&
          totals.line.height <= totals.rowHeight + 0.5 &&
          totals.place.top >= totals.meta.bottom - 0.5,
        JSON.stringify(totals),
      );
      // The file count is on the size line, the header's line above the Diff summary's
      // place, one row (docs/design-system.md, "Change Size Line").
      check(
        "the size line above the Diff summary's place says the file count in one row",
        totals?.size?.text === "35 files changed" &&
          totals.rowHeight !== null &&
          totals.size.box.height <= totals.rowHeight + 0.5 &&
          totals.size.box.bottom <= totals.place.top + 0.5 &&
          totals.size.box.top >= totals.meta.bottom - 0.5,
        JSON.stringify(totals?.size),
      );
      const empty = measured.empty;
      check(
        "with no count of files, the empty place takes no room",
        empty?.display === "none" && empty.height === 0,
        JSON.stringify(empty),
      );
      const tooltip = measured.tooltip;
      check(
        "the hover summary has its change line and no Diff summary",
        tooltip?.stats === 1 && tooltip.place === 0,
        JSON.stringify(tooltip),
      );
      check(
        "the hover summary reads as the Diff summary's header, in words for a screen reader",
        tooltip?.text === "2 A, 3 D, 30 M·+1,234−3,423" &&
          tooltip.hidden === "true" &&
          tooltip.said === "2 added, 3 deleted, 30 modified; 1,234 lines added, 3,423 deleted",
        JSON.stringify(tooltip),
      );
      const STATUS_INK = {
        added: "--git-status-added",
        deleted: "--git-status-deleted",
        modified: "--git-status-modified",
      };
      for (const paint of tooltip?.paint ?? []) {
        const where = `the hover summary, ${paint.theme}`;
        const inks = Object.values(paint.tokens);
        check(
          `${where}: the tokens are distinct`,
          new Set(inks).size === inks.length,
          JSON.stringify(paint.tokens),
        );
        check(
          `${where}: its file count is bold, in the line's ink`,
          JSON.stringify(paint.numbers.map(([text]) => text)) ===
            JSON.stringify(["35", "56.9 KB", "193.9 KB"]) &&
            paint.numbers.every(
              ([, color, weight]) => color === paint.tokens["--text"] && weight === "700",
            ),
          JSON.stringify(paint.numbers),
        );
        // Its words are regular: nothing sets a weight on the card or its change line, so a
        // rule that bolded either would show here.
        check(
          `${where}: its words are in the line's ink, at its regular weight`,
          paint.words === paint.tokens["--text"] &&
            paint.line.ink === paint.tokens["--text"] &&
            paint.line.weight === "400" &&
            paint.wordsWeight === "400",
          JSON.stringify({ words: paint.words, wordsWeight: paint.wordsWeight, line: paint.line }),
        );
        // A status count, "2 A", is one span that is the status primitive: its number and its
        // letter bold, in its status's ink, at a text's 4.5:1 on the card (mb-8iwn). Before,
        // the number was in the line's ink and the letter at the line's weight.
        check(
          `${where}: each status count, number and letter, is bold in its status's ink, 2 A, 3 D, 30 M`,
          JSON.stringify(paint.counts.map((count) => [count.text, count.status])) ===
            JSON.stringify([
              ["2 A", "added"],
              ["3 D", "deleted"],
              ["30 M", "modified"],
            ]) &&
            paint.counts.every(
              (count) =>
                count.statusPrimitive &&
                count.number !== null &&
                count.number[1] === paint.tokens[STATUS_INK[count.status]] &&
                count.letter[1] === paint.tokens[STATUS_INK[count.status]] &&
                count.number[2] === "700" &&
                count.letter[2] === "700",
            ),
          JSON.stringify(paint.counts),
        );
        check(
          `${where}: each status count reads at a text's 4.5:1 on the card's ground`,
          paint.counts.length === 3 && paint.counts.every((count) => count.contrast >= 4.5),
          JSON.stringify(
            paint.counts.map(({ text, size, ground, ink, contrast }) => ({
              text,
              size,
              ground,
              ink,
              contrast,
            })),
          ),
        );
        check(
          `${where}: its commas and dots are muted at the line's weight, the dots hidden`,
          JSON.stringify(paint.marks.map(([text, hidden]) => [text, hidden])) ===
            JSON.stringify([
              [",", null],
              [",", null],
              ["·", "true"],
            ]) &&
            paint.marks.every(
              ([, , color, markWeight]) =>
                color === paint.tokens["--muted"] && markWeight === paint.line.weight,
            ),
          JSON.stringify(paint.marks),
        );
        check(
          `${where}: the size line's dot is muted at the line's weight`,
          JSON.stringify(paint.sizeMarks.map(([text]) => text)) === JSON.stringify(["·"]) &&
            paint.sizeMarks.every(
              ([, color, markWeight]) => color === paint.tokens["--muted"] && markWeight === "400",
            ),
          JSON.stringify(paint.sizeMarks),
        );
      }
      check(
        "the two themes ink the hover summary's status counts apart",
        JSON.stringify(tooltip?.paint?.[0]?.counts) !== JSON.stringify(tooltip?.paint?.[1]?.counts),
        JSON.stringify(tooltip?.paint),
      );
      const tipSweep = tooltip?.sweep ?? [];
      check(
        "from 60 to 360 px, the hover summary wraps and never starts a line with its dot",
        tipSweep.length === 301 &&
          tipSweep.some((at) => at.lines >= 3) &&
          tipSweep.every((at) => at.dots === 1 && at.starts === 0),
        JSON.stringify(tipSweep.filter((at) => at.dots !== 1 || at.starts > 0)),
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
