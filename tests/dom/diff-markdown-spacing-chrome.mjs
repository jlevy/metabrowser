// The space between a rendered Markdown diff's blocks, laid out by headless Chrome beside
// the Document view of the same text: the production `blockRow`, `sanitizeBlock`,
// `changeRuns`, and `removedParts` (builtin_plugins/diff/diff-markdown.js) build the
// server's projection into the article a
// pull request's Changes and Docs mount, under the shell's, the Markdown plugin's, the
// pull request page's, the diff plugin's, and KPress's stylesheets, and KPress's render of
// each version is set in a Document view's frame.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     KPRESS_STATIC=/dir/with/kpress/css/and/fonts SPACING_INPUT=/path/to/input.json \
//     [SPACING_SHOTS=/dir/for/screenshots] node tests/dom/diff-markdown-spacing-chrome.mjs
//
// tests/test_diff_markdown_spacing_chrome.py writes SPACING_INPUT ({sheets, blocks,
// documents: {old, new}, docMaxChars}), copies KPress's stylesheets and faces out of the
// installed package, owns the profile, and runs this in a process group of its own.
// SPACING_SHOTS, when set, receives a screenshot of the new version's Document view, of
// the diff with its removed blocks hidden (Current), and of the whole diff.
//
// The distance this reads is from one block's box to the next's: a heading's or a
// paragraph's line boxes, a list item's, a quote's, a code block's frame. That is the
// space a reader sees between two texts, and it is the Document view's wherever the diff
// shows two blocks a version holds one after the other. A list is read item by item,
// because the diff gives each item of a changed list a row of its own.
//
// Each row is its own box, and a changed row is in its change's run, so it is margin
// collapsing across rows and through the runs and changes around them, which only a browser
// computes, that has to give the document's space. Two of KPress's rules key on a
// heading's next sibling (`h2 + h3`, and `h4 + p` to `h6 + p`), and a row's block has no
// sibling in the row before it. The diff joins the second across rows; the first would
// restate KPress's margin, so an h3 straight after an h2 keeps the h3's own space, and this
// session states that case.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const root = path.resolve(import.meta.dirname, "../..");
const PLUGINS = path.join(root, "src/metabrowser/builtin_plugins");
const STATIC = path.join(root, "src/metabrowser/static");
const KPRESS = path.resolve(/** @type {string} */ (process.env.KPRESS_STATIC));
const INPUT = JSON.parse(
  fs.readFileSync(/** @type {string} */ (process.env.SPACING_INPUT), "utf8"),
);
const SHOTS = process.env.SPACING_SHOTS;
// Layout puts box edges on 1/64 px, and a gap is the difference of two unrounded edges.
const TOLERANCE_PX = 1 / 64;
// Each frame's width: KPress's single-column band, as a pane beside the navigation is.
const FRAME_PX = 900;
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const near = (/** @type {number} */ a, /** @type {number} */ b) => Math.abs(a - b) <= TOLERANCE_PX;

// The order the app loads them in: KPress's tokens and the shell's sheet with the shell, the
// plugins' with their plugins, and KPress's document sheets with the first render.
const PAGE = `<!doctype html><html style="--doc-max-chars: ${INPUT.docMaxChars}" data-prose-font="serif"><head><meta charset="utf-8"><title>diff spacing</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/plugins/markdown/markdown.css">
<link rel="stylesheet" href="/plugins/github/styles.css">
<link rel="stylesheet" href="/plugins/diff/styles.css">
${INPUT.sheets.map((/** @type {string} */ sheet) => `<link rel="stylesheet" href="/kpress/${sheet}">`).join("\n")}
<script src="/static/inert-html.js"></script>
<script type="module">
import { blockRow, changeRuns, removedParts, sanitizeBlock } from "/plugins/diff/diff-markdown.js";
window.diffSpacing = { blockRow, changeRuns, removedParts, sanitizeBlock };
</script>
</head><body><div id="preview-pane" class="preview-pane" style="display: grid; grid-template-columns: repeat(2, ${FRAME_PX}px); align-items: start"></div></body></html>`;

const TYPES = { ".css": "text/css", ".js": "text/javascript", ".woff2": "font/woff2" };
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
    } else if (url.pathname.startsWith("/plugins/")) {
      file = path.join(PLUGINS, url.pathname.slice(9));
    } else if (url.pathname.startsWith("/kpress/")) {
      file = path.join(KPRESS, url.pathname.slice(8));
    }
    const within = [root, KPRESS].some((dir) => file?.startsWith(dir + path.sep));
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

// In the page: the new version's Document view beside the whole diff, then the diff with its
// removed runs and blocks hidden as Current hides them (`removedParts`) beside the old
// version's.
const MOUNT = `(blocks, documents, frame) => {
  const inert = window.MetabrowserInertHtml;
  const { blockRow, changeRuns, removedParts, sanitizeBlock } = window.diffSpacing;
  const base = "https://github.com/octo/demo/blob/main/docs/guide.md";
  const el = (tag, className, children = []) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.append(...children);
    return node;
  };
  const column = (name, child) => {
    const node = el("div", "", [child]);
    node.dataset.frame = name;
    node.style.cssText = "inline-size: " + frame + "px";
    return node;
  };
  // A Markdown file's Document view (builtin_plugins/markdown): KPress's article in the
  // document host, its prose the long text the host's first-heading rule reads.
  const documentView = (html) => {
    const prose = inert.kpressProse(inert.sanitizeHtml(html, base), document);
    prose.classList.add("kpress-long-text");
    const article = el("article", "kpress kpress-doc kpress-inert", [el("div", "kpress-doc-layout", [prose])]);
    return el("div", "content-body metabrowser-kpress-host md-body metabrowser-markdown-document", [article]);
  };
  // A pull request's rendered diff of one file, as diff-markdown.js mounts it, every block
  // drawn, as the Docs tab draws a document whole.
  const scratch = document.implementation.createHTMLDocument("");
  const template = document.createElement("template");
  const comparison = (current) => {
    const build = (html) => sanitizeBlock(html, inert, template, scratch, () => false);
    const placed = changeRuns(blocks.map((block) => blockRow(block, build)));
    for (const part of removedParts(placed)) part.hidden = current;
    const article = el("article", "kpress kpress-inert diff-markdown", placed);
    const diff = el("div", "github-pull-diff metabrowser-diff-host", [
      el("div", "diff-root", [el("section", "diff-file", [article])]),
    ]);
    return el("div", "content-body pull-request-host github-pull", [el("div", "github-pull-body", [diff])]);
  };
  document.getElementById("preview-pane").replaceChildren(
    column("document", documentView(documents.new)),
    column("diff", comparison(false)),
    column("current", comparison(true)),
    column("old document", documentView(documents.old)),
  );
  return document.querySelectorAll(".diff-markdown .diff-markdown-block").length;
}`;

// In the page: each frame's blocks in order, a list's items one by one, with their boxes
// unrounded and, in a diff, the row's kind; a row in a hidden run is not drawn.
const READ = `() => {
  const read = (node, kind) => {
    const box = node.getBoundingClientRect();
    return {
      tag: node.tagName.toLowerCase(), kind, text: node.textContent.trim().replace(/\\s+/g, " "),
      top: box.top, bottom: box.bottom,
    };
  };
  const units = (blocks, kind) => blocks.flatMap((node) =>
    node.matches("ul, ol") ? [...node.children].map((item) => read(item, kind)) : [read(node, kind)]);
  const frames = {};
  for (const frame of document.querySelectorAll("[data-frame]")) {
    const article = frame.querySelector("article");
    frames[frame.dataset.frame] = article.classList.contains("diff-markdown")
      ? [...article.querySelectorAll(".diff-markdown-block")]
          .filter((row) => row.closest("[hidden]") === null)
          .flatMap((row) => units([...row.querySelector(":scope > .kpress-prose").children],
            ["added", "removed", "context"].find((kind) => row.classList.contains("diff-markdown-" + kind))))
      : units([...article.querySelector(".kpress-prose").children], "document");
  }
  return {
    frames,
    face: getComputedStyle(document.querySelector(".kpress-doc .kpress-prose > p")).fontFamily,
  };
}`;
/** @param {"serif" | "sans"} font The reader's reading font, set on the root as the menu sets it. */
const FONT = (font) => `(() => {
  document.documentElement.setAttribute("data-prose-font", "${font}");
  return document.fonts.ready.then(() => new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)))));
})()`;
// Two frames, so a change to the window is laid out and painted before the next step.
const FRAME = `new Promise((resolve) =>
  requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))`;

/**
 * @typedef {{tag: string, kind: string, text: string, top: number, bottom: number}} Unit
 * @typedef {Unit & {gap: number, after: Unit}} Spaced
 */
/**
 * Each unit after the first, with the space from the one before it.
 * @param {Unit[]} units
 * @returns {Spaced[]}
 */
const spaced = (units) =>
  units.slice(1).map((unit, index) => ({
    ...unit,
    after: units[index],
    gap: unit.top - units[index].bottom,
  }));
/** @param {Spaced} unit */
const pair = (unit) => `${unit.after.tag} -> ${unit.tag}`;
/** @param {number} value */
const px = (value) => `${Math.round(value * 100) / 100} px`;
/** @param {string} text */
const short = (text) => `"${text.slice(0, 30)}"`;
// KPress's one rule keyed on a heading's next sibling that the diff does not carry across
// rows (builtin_plugins/diff/styles.css): an h3 straight after an h2 keeps its own space.
const KEPT_APART = "h2 -> h3";
// The cases the document was written to hold, between unchanged blocks and where a block
// changed, so a changed fixture cannot drop one unseen: each of the first three heading
// levels after a paragraph and a paragraph after each, a list after a paragraph and a
// paragraph after it, and the items of a list whose rows differ in kind.
const CASES = [
  ...["h1", "h2", "h3"].flatMap((level) => [`p -> ${level}`, `${level} -> p`]),
  "p -> li",
  "li -> p",
  "li -> li",
];

const server = await serve();
const { port } = /** @type {import("node:net").AddressInfo} */ (server.address());
/** @type {Awaited<ReturnType<typeof launchChrome>> | null} */
let chrome = null;
try {
  chrome = await launchChrome(/** @type {string} */ (process.env.CHROME_BIN), {
    profiles: /** @type {string} */ (process.env.CHROME_PROFILES),
    width: 2 * FRAME_PX,
    height: 2400,
  });
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `http://127.0.0.1:${port}/` });
  await chrome.waitFor(
    "document.readyState === 'complete' && !!window.MetabrowserInertHtml && !!window.diffSpacing",
  );
  const rows = await chrome.evaluate(
    `(${MOUNT})(${JSON.stringify(INPUT.blocks)}, ${JSON.stringify(INPUT.documents)}, ${FRAME_PX})`,
  );
  check("both diffs draw every block", rows === 2 * INPUT.blocks.length, `${rows} rows`);
  /** @type {Record<string, string>} */
  const faces = {};
  for (const font of /** @type {const} */ (["serif", "sans"])) {
    await chrome.evaluate(FONT(font));
    /** @type {{frames: Record<string, Unit[]>, face: string}} */
    const read = await chrome.evaluate(`(${READ})()`);
    faces[font] = read.face;
    if (SHOTS && font === "serif") {
      fs.mkdirSync(SHOTS, { recursive: true });
      // The frames scroll inside the preview pane, which is the window's height, and Chrome
      // paints only what the pane shows, so the window is made as tall as the pane's content
      // while the shots are taken, and given back before the next reading.
      const height = await chrome.evaluate(
        "Math.ceil(document.getElementById('preview-pane').scrollHeight)",
      );
      await chrome.send("Emulation.setDeviceMetricsOverride", {
        width: 2 * FRAME_PX,
        height,
        deviceScaleFactor: 1,
        mobile: false,
      });
      await chrome.evaluate(FRAME);
      // Each frame, and the Document view and the diff side by side.
      for (const names of [["document"], ["diff"], ["current"], ["document", "diff"]]) {
        const clip = await chrome.evaluate(`(() => {
          const rects = ${JSON.stringify(names)}.map((name) =>
            document.querySelector('[data-frame="' + name + '"]').getBoundingClientRect());
          const left = Math.min(...rects.map((rect) => rect.left));
          const top = Math.min(...rects.map((rect) => rect.top));
          const width = Math.max(...rects.map((rect) => rect.right)) - left;
          const height = Math.max(...rects.map((rect) => rect.bottom)) - top;
          return { x: left, y: top, width, height, scale: 1 };
        })()`);
        const { data } = await chrome.send("Page.captureScreenshot", {
          format: "png",
          clip,
          captureBeyondViewport: true,
        });
        fs.writeFileSync(
          path.join(SHOTS, `${names.join("-and-")}.png`),
          Buffer.from(data, "base64"),
        );
      }
      await chrome.send("Emulation.clearDeviceMetricsOverride");
      await chrome.evaluate(FRAME);
    }
    const document = spaced(read.frames.document);
    const old = spaced(read.frames["old document"]);
    const current = spaced(read.frames.current);
    const diff = spaced(read.frames.diff);
    // The record: each gap of the diff and of Current, in order.
    for (const [name, units] of /** @type {const} */ ([
      ["current", current],
      ["diff", diff],
    ])) {
      for (const unit of units) {
        process.stderr.write(
          `${font} ${name.padEnd(7)} ${pair(unit).padEnd(18)} ${unit.after.kind.padEnd(8)}-> ` +
            `${unit.kind.padEnd(8)} ${px(unit.gap).padStart(9)}  ${unit.text.slice(0, 36)}\n`,
        );
      }
    }
    // The space each version's Document view gives two blocks, by their text, and the
    // first space it gives two blocks of the same kinds.
    /** @type {Map<string, number>} */
    const between = new Map();
    /** @type {Map<string, number>} */
    const byKind = new Map();
    for (const unit of [...document, ...old]) {
      between.set(`${unit.after.text}\n${unit.text}`, unit.gap);
      if (!byKind.has(pair(unit))) {
        byKind.set(pair(unit), unit.gap);
      }
    }
    for (const [label, units] of /** @type {const} */ ([
      ["the whole diff", diff],
      ["Current", current],
    ])) {
      for (const unit of units) {
        const where =
          `${font}, ${label}: ${short(unit.after.text)} to ${short(unit.text)} ` +
          `(${pair(unit)}, ${unit.after.kind} to ${unit.kind})`;
        // Two blocks a version holds one after the other are spaced as that version's
        // Document view spaces them; two that no version holds together, a removed block
        // and the added one that replaces it, as the documents space two such blocks.
        const same = between.get(`${unit.after.text}\n${unit.text}`) ?? byKind.get(pair(unit));
        if (pair(unit) === KEPT_APART) {
          // The h3 keeps the space it has after a paragraph, its own, which is more.
          const own = byKind.get(`p -> ${unit.tag}`);
          check(
            `${where} keeps the h3's own space`,
            same !== undefined && own !== undefined && near(unit.gap, own) && unit.gap > same,
            `${px(unit.gap)}; the document's ${same === undefined ? "none" : px(same)}, ` +
              `the h3's own ${own === undefined ? "none" : px(own)}`,
          );
          continue;
        }
        check(
          `${where} is spaced as in the Document view`,
          same !== undefined && near(unit.gap, same),
          `${px(unit.gap)} against ${same === undefined ? "none" : px(same)}`,
        );
      }
    }
    // Current is the new version alone, block for block the new version's Document view.
    check(
      `${font}: Current shows the new version's blocks in order`,
      JSON.stringify(current.map((unit) => unit.text)) ===
        JSON.stringify(document.map((unit) => unit.text)),
      `${current.length} blocks against ${document.length}`,
    );
    for (const name of CASES) {
      check(
        `${font}: the diff holds ${name} between unchanged blocks`,
        diff.some(
          (unit) => pair(unit) === name && unit.kind === "context" && unit.after.kind === "context",
        ),
      );
      check(
        `${font}: the diff holds ${name} beside a changed block`,
        diff.some(
          (unit) =>
            pair(unit) === name && (unit.kind !== "context" || unit.after.kind !== "context"),
        ),
      );
    }
  }
  // The reading font moved the document's face, so the spacing held in both faces.
  check("the reading fonts set two faces", faces.serif !== faces.sans, JSON.stringify(faces));
} finally {
  await chrome?.close();
  server.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`diff spacing in Chrome: ${checks} checks passed\n`);
