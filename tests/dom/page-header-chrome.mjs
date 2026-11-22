// A commit's page and a pull request's page have one header, laid out by a real engine: the
// commit summary the Git panel draws (`renderCommitSummary`) and the pull request page the
// GitHub plugin mounts (`mountPullPage`), each with the Diff summary the diff plugin draws in
// its place, under the shell's, the GitHub plugin's, and the diff plugin's stylesheets and
// KPress's faces, in headless Chrome.
//
//   CHROME_BIN=/path/to/chrome KPRESS_STATIC=/dir/with/css/and/fonts \
//     CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/page-header-chrome.mjs
//
// tests/test_page_header_chrome.py owns the profile, copies KPress's tokens and faces into
// KPRESS_STATIC, and runs this in a process group of its own. With MEASURE_OUT set, it also
// writes what it read there.
//
// The owner asked that the lines under the two titles share one design (mb-26zj): every line
// at the regular body size, the Diff summary's included, which was a step smaller on both
// pages (mb-kisi); the author drawn the same on both, an avatar's box and then the bold name
// (mb-nunw); and a profile icon for a commit's author (mb-s3g8). Which classes each page
// writes is browserless (tests/test_design_vocabulary.py,
// `test_page_headers_set_every_line_under_the_title_at_the_body_size`); what only a browser
// can tell is the computed type of every line and of each run of text in it, where the two
// authors' names start, and that an avatar arriving in the box moves nothing
// (docs/design-system.md, "Page Headers" and "Actor Identity").
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const GITHUB = path.join(root, "src/metabrowser/builtin_plugins/github");
const DIFF = path.join(root, "src/metabrowser/builtin_plugins/diff");
const FIXTURES = path.join(root, "tests/fixtures/github-pull-page-responses.json");
const KPRESS = process.env.KPRESS_STATIC ? path.resolve(process.env.KPRESS_STATIC) : null;
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

// The shell's startup scripts both pages need, in the shell's order, the icon registry first
// (the revision's copy button is its glyph, as in the app), then the shared changed-files
// tree the Diff summary is drawn on.
const SCRIPTS = [
  "icons.js",
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
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>page headers</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/github/styles.css">
<link rel="stylesheet" href="/diff/styles.css">
<script>
  window.METABROWSER_SETTINGS = { SYNTAX_HIGHLIGHT_MAX_BYTES: 524288, SYNTAX_LANGUAGE_BY_BASENAME: {}, SYNTAX_LANGUAGE_BY_EXTENSION: {} };
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
    if (url.pathname === "/" || url.pathname.startsWith("/pull/")) {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(PAGE);
      return;
    }
    if (url.pathname === "/fixtures.json") {
      file = FIXTURES;
    } else if (url.pathname.startsWith("/static/")) {
      file = path.join(STATIC, url.pathname.slice(8));
    } else if (url.pathname.startsWith("/github/")) {
      file = path.join(GITHUB, url.pathname.slice(8));
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

// The pane widths the headers are read at: a wide pane, the default, and a narrow one.
const WIDTHS = [980, 560, 360];

// In the page: draw one page's header at a width, its Diff summary drawn in its place, and read
// its title and every line under it: each line's computed type, and each run of text in it
// with the type it computes to, by what the run is. Then put an avatar in the author's box,
// in the glyph's place, and read where the name starts and every line's height again.
const MEASURE = `async (which, width) => {
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const round = (value) => Math.round(value * 100) / 100;
  const diff = (window.__diff ??= await import("/diff/diff-view.js"));
  const pane = document.getElementById("preview-pane");
  pane.style.width = width + "px";
  // The change set both pages' Diff summaries say: 35 files, 2 added, 3 deleted, 30 modified.
  const kinds = [...Array(2).fill("added"), ...Array(3).fill("deleted"), ...Array(30).fill("modified")];
  const files = kinds.map((kind, at) => ({
    kind,
    ...(kind === "added" ? {} : { old: { path: "src/f" + at + ".py" } }),
    ...(kind === "deleted" ? {} : { new: { path: "src/f" + at + ".py" } }),
    additions: 30,
    deletions: 90,
  }));
  const changes = { manifest: { totals: { files: 35, additions: 1234, deletions: 3423, exact: true }, files } };
  const mounts = { changedFiles: window.MetabrowserChangedFilesTree, openFile() {} };
  let header;
  let summary;
  if (which === "commit") {
    const now = Date.now() / 1000 - 3 * 86400;
    const detail = {
      commit: {
        id: "c".repeat(40), short_id: "ccccccc", parent_ids: ["d".repeat(40)],
        author: { name: "Jane Author", email: "a@example.invalid" },
        authored_at: now, committed_at: now, subject: "feat(diff): consolidate the diff summaries",
        refs: [
          { name: "main", kind: "local", is_trunk: true, is_head: true },
          { name: "upstream/main", kind: "remote", is_trunk: true },
        ],
      },
      stats: { files_changed: 35, files_added: 2, files_deleted: 3, files_modified: 30, additions: 1234, deletions: 3423 },
      body: "Its counts are the Diff summary's header.",
      files: [],
    };
    const stage = document.createElement("div");
    stage.className = "git-commit-stage";
    stage.innerHTML = '<div class="git-commit-view">' + window.MetabrowserGitPanel._internals.renderCommitSummary(detail) + "</div>";
    pane.replaceChildren(stage);
    header = stage.querySelector(".git-commit-header");
    summary = diff.mountDiffSummary(header.querySelector(".git-commit-diff-summary"), changes, window.metabrowser, mounts);
  } else {
    const recorded = (window.__recorded ??= await (await fetch("/fixtures.json")).json());
    const page = (window.__page ??= await import("/github/pull-page.js"));
    const body = structuredClone(recorded.current.body);
    window.__fetch ??= window.fetch;
    window.fetch = async () => new Response(null, { status: 304 });
    history.replaceState(null, "", "/pull/" + body.number);
    const container = document.createElement("div");
    pane.replaceChildren(container);
    const mb = window.metabrowser;
    window.__handle?.dispose?.();
    window.__handle = page.mountPullPage(
      container,
      { number: body.number, tab: "", reader: { initial: { etag: null, body }, fetchAfterMs: 60000 } },
      {
        ...mb,
        perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
        ensureAsset: async () => {},
        ensureKindAssets: async () => {},
        // The page reads its comparison once idle, and the 304 every request answers here
        // would fail that read and empty the row this draws the summary in: it is never idle.
        whenIdle: () => () => {},
        navigation: { href: () => "/view/" },
        sourceKind: () => "filesystem",
        icons: { toggle: "" },
      },
    );
    await frames();
    header = container.querySelector(".github-pull-header");
    summary = diff.mountDiffSummary(header.querySelector(".github-pull-summary"), changes, mb, mounts);
    // The size line above it, drawn as the page draws it once its summary is (pull-page.js,
    // paintSize), since this draws the summary in place of the page's own read.
    header
      .querySelector(".github-pull-size")
      .replaceChildren(...mb.changeSizeLineNodes(mb.changeSizeLine({ commits: 8, files: 28, pushedBytes: 64_410, diffBytes: 217_600 })));
  }
  await document.fonts.ready;
  await frames();
  const type = (node) => {
    const style = getComputedStyle(node);
    return { size: style.fontSize, lineHeight: style.lineHeight, weight: style.fontWeight, color: style.color };
  };
  const diffSizePaint = [];
  if (which === "pull") {
    const line = header.querySelector(".github-pull-size");
    const visible = line.cloneNode(true);
    for (const hidden of visible.querySelectorAll(".visually-hidden")) hidden.remove();
    const fileRow = document.createElement("div");
    fileRow.className = "tree-item tree-file";
    fileRow.innerHTML = [64_410, 217_600]
      .map((bytes) => window.metabrowser.sizeHtml(bytes, "tree-item-size")).join("");
    document.body.append(fileRow);
    const readSize = (container) => [...container.querySelectorAll(".size")].map((element) => {
      const { color, fontWeight, fontVariantNumeric } = getComputedStyle(element);
      return { text: element.textContent, color, fontWeight, fontVariantNumeric };
    });
    for (const theme of ["light", "dark"]) {
      document.documentElement.dataset.theme = theme;
      diffSizePaint.push({
        theme,
        text: visible.textContent.replace(/\\s+/g, " ").trim(),
        painted: readSize(line),
        files: readSize(fileRow),
        spoken: [...line.querySelectorAll(".visually-hidden")].map((element) => element.textContent),
      });
    }
    delete document.documentElement.dataset.theme;
    fileRow.remove();
  }
  // What a run of text is: a chip keeps its own size, and a revision takes the line's in its
  // own face; any other run is the line's text.
  const kindOf = (element) =>
    element.closest(".git-ref") ? "ref chip"
      : element.closest(".file-header-badge") ? "badge"
      : element.closest(".github-pull-label") ? "label chip"
      : element.closest(".git-commit-sha") ? "revision"
      : "text";
  const runs = (line) => {
    const found = [];
    const walker = document.createTreeWalker(line, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent.replace(/\\s+/g, " ").trim();
      const element = node.parentElement;
      if (!text || element.closest(".visually-hidden, .sr-only, .github-pull-badge-sizer, [hidden]")) {
        continue;
      }
      if (element.getBoundingClientRect().width === 0) {
        continue;
      }
      found.push({ text: text.slice(0, 32), kind: kindOf(element), ...type(element) });
    }
    return found;
  };
  const headerBox = header.getBoundingClientRect();
  const contentLeft = headerBox.left + parseFloat(getComputedStyle(header).paddingLeft);
  // The header's corner, which holds the View on GitHub button, is placed out of the flow in
  // the page's upper right, so it is no line (docs/design-system.md, "View on GitHub").
  const lines = [...header.children].filter(
    (child) =>
      getComputedStyle(child).display !== "none" && !child.classList.contains("view-header-end"),
  );
  const title = lines[0];
  // Each line's top is read from the title's, since the commit's header is padded by its
  // view and the pull request's by itself.
  const read = () => lines.slice(1).map((line) => {
    const box = line.getBoundingClientRect();
    // The Diff summary's line is its header, which the diff plugin draws in the line's place.
    const text = line.querySelector(":scope > .diff-summary") ?? line;
    return {
      cls: line.className,
      top: round(box.top - title.getBoundingClientRect().top),
      height: round(box.height),
      ...type(text),
      runs: runs(text),
    };
  });
  const identity = header.querySelector(".actor-identity");
  const avatar = identity?.querySelector(".actor-avatar") ?? null;
  const name = identity?.querySelector(".actor-name") ?? null;
  const author = () => ({
    line: lines.indexOf(identity?.closest(".page-header > *")),
    box: avatar ? { left: round(avatar.getBoundingClientRect().left - contentLeft), width: round(avatar.getBoundingClientRect().width), height: round(avatar.getBoundingClientRect().height) } : null,
    glyph: avatar ? avatar.querySelector(":scope > svg") !== null : null,
    image: avatar ? avatar.querySelector(":scope > img") !== null : null,
    nameLeft: name ? round(name.getBoundingClientRect().left - contentLeft) : null,
    name: name ? { text: name.textContent, ...type(name) } : null,
  });
  const out = {
    title: { cls: title.className, height: round(title.getBoundingClientRect().height), ...type(title) },
    gap: getComputedStyle(header).rowGap,
    // The space under the title, a page title's gap to its metadata (mb-wcbc).
    titleGap: getComputedStyle(document.documentElement).getPropertyValue("--page-title-gap").trim(),
    body: getComputedStyle(document.documentElement).getPropertyValue("--body-font-size").trim(),
    lines: read(),
    author: author(),
    diffSizePaint,
  };
  // An avatar arriving in the box, in the glyph's place: a data image, so nothing is asked of
  // the network. Nothing moves: the name starts where it did, and every line keeps its place.
  // The image is 40 px, as GitHub serves an avatar (s=40), and has no size of its own on the
  // element, so only the box's own size holds it to 18 px: with the box unsized, the glyph and
  // the image would lay out at their own sizes and the name would move (A4 of review A on
  // #487).
  if (avatar) {
    const image = document.createElement("img");
    image.className = "actor-avatar-image";
    image.alt = "";
    image.src = "data:image/svg+xml," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40"><circle cx="20" cy="20" r="20" fill="#8a8f98"/></svg>');
    avatar.replaceChildren(image);
    await image.decode().catch(() => null);
    await frames();
    out.withAvatar = { lines: read().map(({ top, height }) => ({ top, height })), author: author() };
  }
  summary?.dispose?.();
  return out;
}`;

/** The runs of a page's lines that are the line's text, not a chip or a revision. */
const textRuns = (page) =>
  page.lines.flatMap((line) => line.runs.filter((run) => run.kind === "text"));

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
        `document.readyState === "complete" && Boolean(window.MetabrowserGitPanel) && Boolean(window.MetabrowserChangedFilesTree) && Boolean(window.metabrowser?.actorIdentity)`,
      );
      lap("the page loaded");
      const measured = {};
      for (const width of WIDTHS) {
        measured[width] = {
          commit: await browser.evaluate(`(${MEASURE})("commit", ${width})`),
          pull: await browser.evaluate(`(${MEASURE})("pull", ${width})`),
        };
      }
      lap("both headers drawn at every width");
      for (const width of WIDTHS) {
        const { commit, pull } = measured[width];
        const where = `at ${width} px`;
        const body = commit.body;
        check(`${where}: the body size is 14 px`, body === "14px", body);
        // One title: the same size, weight, and line on both pages, each as tall as its own
        // lines, with no line held empty under it (mb-wcbc).
        const lines = (title) => title.height / Number.parseFloat(title.lineHeight);
        check(
          `${where}: both titles are one treatment`,
          ["size", "weight", "lineHeight"].every((key) => commit.title[key] === pull.title[key]) &&
            commit.title.size === "24px" &&
            [commit.title, pull.title].every(
              (title) => Number.isInteger(lines(title)) && lines(title) >= 1,
            ),
          JSON.stringify({ commit: commit.title, pull: pull.title }),
        );
        check(
          `${where}: both headers set their lines 6 px apart`,
          commit.gap === "6px" && pull.gap === "6px",
          JSON.stringify([commit.gap, pull.gap]),
        );
        // One size: every line under the title computes to the body size, and every run of
        // text in it, the Diff summary's included; a chip keeps its own size, and a revision
        // is the line's (docs/design-system.md, "Page Headers", "Short Commit IDs").
        for (const [name, page] of [
          ["commit", commit],
          ["pull request", pull],
        ]) {
          const labelsRow = (line) => line.cls.includes("github-pull-labels");
          const off = page.lines.filter((line) => !labelsRow(line) && line.size !== body);
          check(
            `${where}: every line under the ${name}'s title is at the body size`,
            off.length === 0 && page.lines.length >= 4,
            JSON.stringify(off.map((line) => [line.cls, line.size])),
          );
          // Each is a page header's line, the Diff summary's row among them; the labels, a
          // row of chips, are the one row that is not (A1 of review A on #487).
          const classless = page.lines.filter(
            (line) => !labelsRow(line) && !line.cls.split(" ").includes("page-header-line"),
          );
          check(
            `${where}: every line under the ${name}'s title but the labels is a page header line`,
            classless.length === 0,
            JSON.stringify(classless.map((line) => line.cls)),
          );
          const runs = textRuns(page);
          const small = runs.filter((run) => run.size !== body);
          check(
            `${where}: every run of the ${name}'s lines' text is at the body size`,
            runs.length > 10 && small.length === 0,
            JSON.stringify(small),
          );
          const summary = page.lines.at(-1);
          check(
            `${where}: the ${name}'s Diff summary is its last line, at the body size`,
            /(git-commit|github-pull)-(diff-)?summary/.test(summary.cls) &&
              summary.size === body &&
              summary.runs.length > 0 &&
              summary.runs.every((run) => run.size === body),
            JSON.stringify(summary),
          );
          // The size line is the line above it, and says the file count, at the body size
          // (docs/design-system.md, "Change Size Line").
          const size = page.lines.at(-2);
          check(
            `${where}: the ${name}'s size line is above its Diff summary, saying its file count`,
            /(git-commit|github-pull)-size/.test(size?.cls ?? "") &&
              size.size === body &&
              size.runs.some((run) => run.text === "files changed" && run.size === body),
            JSON.stringify(size),
          );
          const revision = page.lines
            .flatMap((line) => line.runs)
            .filter((run) => run.kind === "revision");
          check(
            `${where}: the ${name}'s revision, if any, is at the body size, its line's`,
            revision.every((run) => run.size === body),
            JSON.stringify(revision),
          );
        }
        for (const size of pull.diffSizePaint) {
          check(
            `${where} in ${size.theme}: the pull request byte values match the Files size style`,
            JSON.stringify(size.painted) === JSON.stringify(size.files) &&
              size.painted.length === 2 &&
              size.painted.every(
                (value) =>
                  value.fontWeight === "400" && value.fontVariantNumeric === "tabular-nums",
              ),
            JSON.stringify(size),
          );
          check(
            `${where} in ${size.theme}: the visible line has dots and the spoken separators are commas`,
            size.text === "8 commits · 28 files changed · 62.9 KB compressed (212.5 KB raw diff)" &&
              size.spoken.length === 2 &&
              size.spoken.every((separator) => separator === ", "),
            JSON.stringify(size),
          );
        }
        const commitSizes = new Set(textRuns(commit).map((run) => run.size));
        const pullSizes = new Set(textRuns(pull).map((run) => run.size));
        check(
          `${where}: both pages' lines are one size`,
          commitSizes.size === 1 &&
            pullSizes.size === 1 &&
            [...commitSizes][0] === [...pullSizes][0],
          JSON.stringify({ commit: [...commitSizes], pull: [...pullSizes] }),
        );
        check(
          `${where}: both pages' lines are one line height`,
          new Set(
            [...commit.lines, ...pull.lines]
              .filter(
                (line) => !line.cls.includes("github-pull-labels") && !/summary/.test(line.cls),
              )
              .map((line) => line.lineHeight),
          ).size === 1,
          JSON.stringify(
            [...commit.lines, ...pull.lines].map((line) => [line.cls, line.lineHeight]),
          ),
        );
        // One structure: the author first under the title, the age before the size line and
        // the Diff summary, which is last; the commit's revision where the pull request has
        // its branches.
        const order = (page, parts) =>
          parts.map((part) => page.lines.findIndex((line) => line.cls.includes(part)));
        const commitOrder = order(commit, [
          "git-commit-byline",
          "git-commit-revision-line",
          "git-commit-ages",
          "git-commit-size",
          "git-commit-diff-summary",
        ]);
        const pullOrder = order(pull, [
          "github-pull-meta",
          "github-pull-branches",
          "github-pull-opened",
          "github-pull-size",
          "github-pull-summary",
        ]);
        check(
          `${where}: the commit's lines are its author, revision, age, size, and Diff summary`,
          JSON.stringify(commitOrder) === "[0,1,2,3,4]" && commit.lines.length === 5,
          JSON.stringify(commit.lines.map((line) => line.cls)),
        );
        check(
          `${where}: the pull request's are its author, branches, ages, ..., size, and Diff summary`,
          JSON.stringify(pullOrder.slice(0, 3)) === "[0,1,2]" &&
            pullOrder[3] === pull.lines.length - 2 &&
            pullOrder[4] === pull.lines.length - 1,
          JSON.stringify(pull.lines.map((line) => line.cls)),
        );
        // The first line is a page title's gap under the title, the gap a view header leaves
        // between its title and its metadata line, on both pages (mb-wcbc).
        check(
          `${where}: each header's first line is --page-title-gap under its title`,
          Number.parseFloat(commit.titleGap) > 0 &&
            pull.titleGap === commit.titleGap &&
            commit.lines[0].top === commit.title.height + Number.parseFloat(commit.titleGap) &&
            pull.lines[0].top === pull.title.height + Number.parseFloat(pull.titleGap),
          JSON.stringify([
            commit.lines[0].top,
            pull.lines[0].top,
            commit.title.height,
            pull.title.height,
            commit.titleGap,
          ]),
        );
        // One identity: the box, the same size on both pages, holding the person glyph for an
        // author with no avatar, then the bold name, starting at the same x on both.
        for (const [name, page] of [
          ["commit", commit],
          ["pull request", pull],
        ]) {
          const author = page.author;
          check(
            `${where}: the ${name}'s author is the first line's, an 18 px box holding the glyph`,
            author.line === 1 &&
              author.box?.width === 18 &&
              author.box.height === 18 &&
              author.box.left === 0 &&
              author.glyph === true &&
              author.image === false,
            JSON.stringify(author),
          );
          check(
            `${where}: the ${name}'s author's name is bold, at the body size, in the text's ink`,
            author.name?.weight === "700" && author.name.size === body,
            JSON.stringify(author.name),
          );
          const later = page.withAvatar;
          check(
            `${where}: an avatar arriving in the ${name}'s box moves nothing`,
            later?.author.image === true &&
              later.author.nameLeft === author.nameLeft &&
              JSON.stringify(later.lines) ===
                JSON.stringify(page.lines.map(({ top, height }) => ({ top, height }))),
            JSON.stringify({ before: author, after: later }),
          );
        }
        check(
          `${where}: both authors' names start at the same x, the box and its gap in`,
          commit.author.nameLeft === pull.author.nameLeft && commit.author.nameLeft === 22,
          JSON.stringify([commit.author.nameLeft, pull.author.nameLeft]),
        );
        check(
          `${where}: both authors' names are one type`,
          JSON.stringify(commit.author.name && { ...commit.author.name, text: "" }) ===
            JSON.stringify(pull.author.name && { ...pull.author.name, text: "" }),
          JSON.stringify([commit.author.name, pull.author.name]),
        );
      }
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
  console.log(`page header in Chrome: ${checks} checks passed`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
