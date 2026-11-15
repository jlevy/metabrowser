// A rendered Markdown diff's fold of unchanged blocks, laid out by headless Chrome: the
// production `appendBlocks` and `sanitizeBlock` (builtin_plugins/diff/diff-markdown.js)
// build the server's projection into the article a pull request's Changes mounts, under
// the shell's, the diff plugin's, and KPress's stylesheets.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     KPRESS_STATIC=/dir/with/kpress/css/and/fonts FOLD_INPUT=/path/to/input.json \
//     [FOLD_SHOTS=/dir/for/screenshots] node tests/dom/diff-markdown-fold-chrome.mjs
//
// tests/test_diff_markdown_fold_chrome.py writes FOLD_INPUT ({sheets, blocks}), copies
// KPress's stylesheets and faces out of the installed package, owns the profile, and runs
// this in a process group of its own. FOLD_SHOTS, when set, receives a screenshot of the
// comparison closed and open.
//
// The fold is a `<details>` inside the comparison's `article.kpress`, so KPress's own
// document disclosure styling reached it. A fold is a place in the document, not a box in
// it: closed, it is one quiet line between the blocks around it; open, the blocks it held
// stand where they stood, laid out as the blocks around them are, and nothing else moves.
// A document's own `<details>` keeps KPress's box.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const DIFF = path.join(root, "src/metabrowser/builtin_plugins/diff");
const KPRESS = path.resolve(/** @type {string} */ (process.env.KPRESS_STATIC));
const INPUT = JSON.parse(fs.readFileSync(/** @type {string} */ (process.env.FOLD_INPUT), "utf8"));
const SHOTS = process.env.FOLD_SHOTS;
// Box edges are fractional; under a hundredth of a pixel is the same place.
const TOLERANCE_PX = 0.01;
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const near = (a, b) => Math.abs(a - b) <= TOLERANCE_PX;

// The order the page loads them in: KPress's tokens and the shell's sheet with the shell,
// the diff plugin's with the plugin, and KPress's document sheets with the first render.
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>diff fold</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/diff/styles.css">
${INPUT.sheets.map((sheet) => `<link rel="stylesheet" href="/kpress/${sheet}">`).join("\n")}
<script src="/static/inert-html.js"></script>
<script type="module">
import { appendBlocks, sanitizeBlock } from "/diff/diff-markdown.js";
window.diffFold = { appendBlocks, sanitizeBlock };
</script>
</head><body><div id="preview-pane" class="preview-pane" style="width: 900px"></div></body></html>`;

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
    } else if (url.pathname.startsWith("/diff/")) {
      file = path.join(DIFF, url.pathname.slice(6));
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

// In the page: mount the comparison as diff-markdown.js mounts it, in a pull request's
// diff host, beside a document with a `<details>` of its own.
const MOUNT = `(blocks) => {
  const inert = window.MetabrowserInertHtml;
  const { appendBlocks, sanitizeBlock } = window.diffFold;
  const el = (tag, className, children = []) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.append(...children);
    return node;
  };
  const scratch = document.implementation.createHTMLDocument("");
  const template = document.createElement("template");
  const content = document.createDocumentFragment();
  appendBlocks(content, blocks, (html) =>
    sanitizeBlock(html, inert, template, scratch, () => false),
  );
  const rendered = el("article", "kpress kpress-inert diff-markdown", [content]);
  const own = el("details", "", [el("summary", "", ["A document's own details"]), el("p", "", ["Inside."])]);
  const documentArticle = el("article", "kpress kpress-doc kpress-inert", [
    el("div", "kpress-doc-layout", [el("div", "kpress-prose", [own])]),
  ]);
  document.getElementById("preview-pane").replaceChildren(
    el("div", "github-pull-diff metabrowser-diff-host", [el("section", "diff-file", [rendered])]),
    el("div", "metabrowser-kpress-host", [documentArticle]),
  );
  return document.querySelectorAll("details.diff-markdown-context").length;
}`;

// In the page: the fold, its summary, every block row, and the document's own details.
const READ = `() => {
  const round = (value) => Math.round(value * 100) / 100;
  const box = (node) => {
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return {
      top: round(rect.top), bottom: round(rect.bottom), left: round(rect.left),
      width: round(rect.width), height: round(rect.height),
      border: ["top", "right", "bottom", "left"]
        .map((side) => style.getPropertyValue("border-" + side + "-width")).join(" "),
      background: style.backgroundColor + " " + style.backgroundImage,
      padding: style.padding, margin: style.margin, boxShadow: style.boxShadow,
    };
  };
  const face = (row) => {
    const style = getComputedStyle(row.querySelector(".kpress-prose > *"));
    return [style.fontFamily, style.fontSize, style.fontWeight, style.lineHeight, style.color,
      style.margin].join(" | ");
  };
  const fold = document.querySelector("details.diff-markdown-context");
  const summary = fold.querySelector(":scope > summary");
  const rows = [...document.querySelectorAll(".diff-markdown .diff-markdown-block")]
    .filter((row) => row.parentElement !== fold || fold.open)
    .map((row) => ({
      text: row.textContent.trim(),
      folded: row.parentElement === fold,
      // Whether the row comes before the fold in the document, or is in it or after it.
      first: !!(row.compareDocumentPosition(fold) & Node.DOCUMENT_POSITION_FOLLOWING),
      box: box(row),
      face: face(row),
      textLeft: round(row.querySelector(".kpress-prose > *").getBoundingClientRect().left),
    }));
  return {
    open: fold.open,
    children: fold.children.length,
    fold: box(fold),
    summary: { ...box(summary), userSelect: getComputedStyle(summary).userSelect,
      text: summary.textContent,
      contentLeft: round(summary.getBoundingClientRect().left
        + parseFloat(getComputedStyle(summary).paddingLeft)) },
    rows,
    own: box(document.querySelector(".kpress-doc details")),
  };
}`;

// Wait for an open or a close to finish: the fold keeps its height for five frames.
const SETTLE = `new Promise((resolve) => {
  const fold = document.querySelector("details.diff-markdown-context");
  let last = -1;
  let still = 0;
  const frame = () => {
    const height = fold.getBoundingClientRect().height;
    still = height === last ? still + 1 : 0;
    last = height;
    if (still >= 5) resolve(height); else requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
})`;
const CLICK = `document.querySelector("details.diff-markdown-context > summary").click()`;

const server = await serve();
const { port } = /** @type {import("node:net").AddressInfo} */ (server.address());
/** @type {Awaited<ReturnType<typeof launchChrome>> | null} */
let chrome = null;
/** @param {string} name */
const shot = async (name) => {
  if (!SHOTS || !chrome) {
    return;
  }
  const clip = await chrome.evaluate(`(() => {
    const rect = document.querySelector(".metabrowser-diff-host").getBoundingClientRect();
    return { x: rect.left, y: rect.top, width: rect.width, height: rect.height, scale: 1 };
  })()`);
  const { data } = await chrome.send("Page.captureScreenshot", { format: "png", clip });
  fs.mkdirSync(SHOTS, { recursive: true });
  fs.writeFileSync(path.join(SHOTS, `${name}.png`), Buffer.from(data, "base64"));
};
try {
  chrome = await launchChrome(/** @type {string} */ (process.env.CHROME_BIN), {
    profiles: /** @type {string} */ (process.env.CHROME_PROFILES),
    width: 1000,
    height: 1200,
  });
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `http://127.0.0.1:${port}/` });
  await chrome.waitFor(
    "document.readyState === 'complete' && !!window.MetabrowserInertHtml && !!window.diffFold",
  );
  const folds = await chrome.evaluate(`(${MOUNT})(${JSON.stringify(INPUT.blocks)})`);
  check("the comparison has one fold", folds === 1, `${folds}`);
  await chrome.evaluate("document.fonts.ready.then(() => true)");
  await chrome.evaluate(SETTLE);
  const closed = await chrome.evaluate(`(${READ})()`);
  await shot("closed");
  await chrome.evaluate(CLICK);
  await chrome.evaluate(SETTLE);
  const opened = await chrome.evaluate(`(${READ})()`);
  await shot("open");
  await chrome.evaluate(CLICK);
  await chrome.evaluate(SETTLE);
  const reclosed = await chrome.evaluate(`(${READ})()`);
  process.stderr.write(`${JSON.stringify({ closed, opened, reclosed })}\n`);

  // Closed: one quiet line, the summary, between the blocks around it.
  check("closed, the fold holds only its summary", closed.children === 1, `${closed.children}`);
  // The rows before the fold, then the rows after it.
  const after = closed.rows.findIndex((row) => !row.first);
  const before = after - 1;
  check("the fold has unchanged blocks on each side", before >= 0 && after > 0, `${after}`);
  check(
    "closed, the fold starts where the block before it ends",
    near(closed.rows[before].box.bottom, closed.fold.top),
    `${closed.fold.top} against ${closed.rows[before].box.bottom}`,
  );
  check(
    "closed, the next block starts where the fold ends",
    near(closed.rows[after].box.top, closed.fold.bottom),
    `${closed.rows[after].box.top} against ${closed.fold.bottom}`,
  );
  check(
    "closed, the summary is the fold's whole box",
    near(closed.summary.top, closed.fold.top) && near(closed.summary.bottom, closed.fold.bottom),
    `${closed.summary.top}-${closed.summary.bottom} in ${closed.fold.top}-${closed.fold.bottom}`,
  );
  const block = closed.rows[0].box;
  for (const [state, measured] of [
    ["closed", closed],
    ["open", opened],
  ]) {
    for (const [part, part_box] of [
      ["fold", measured.fold],
      ["summary", measured.summary],
    ]) {
      const label = `${state}, the ${part}`;
      check(`${label} has no border`, part_box.border === "0px 0px 0px 0px", part_box.border);
      check(
        `${label} has no background`,
        part_box.background === "rgba(0, 0, 0, 0) none",
        part_box.background,
      );
      check(`${label} has no shadow`, part_box.boxShadow === "none", part_box.boxShadow);
      check(`${label} has no margin`, part_box.margin === "0px", part_box.margin);
    }
    check(
      `${state}, the fold has no padding`,
      measured.fold.padding === "0px",
      measured.fold.padding,
    );
    check(
      `${state}, the fold spans the blocks' width`,
      near(measured.fold.left, block.left) && near(measured.fold.width, block.width),
      `${measured.fold.left}+${measured.fold.width} against ${block.left}+${block.width}`,
    );
    check(
      `${state}, the summary's label starts on the blocks' text edge`,
      near(measured.summary.contentLeft, measured.rows[0].textLeft),
      `${measured.summary.contentLeft} against ${measured.rows[0].textLeft}`,
    );
    check(
      `${state}, the summary never selects text`,
      measured.summary.userSelect === "none",
      measured.summary.userSelect,
    );
  }

  // Open: the hidden blocks, in place, laid out as the unchanged blocks around them.
  const inserted = opened.rows.filter((row) => row.folded);
  check(
    "open, the fold holds the blocks its summary counts",
    inserted.length > 0 &&
      inserted.length === opened.children - 1 &&
      closed.summary.text === `${inserted.length} unchanged blocks`,
    `${inserted.length} blocks, "${closed.summary.text}"`,
  );
  const neighbour = opened.rows[before];
  for (const row of inserted) {
    const label = `open, "${row.text}"`;
    check(
      `${label} is set in the neighbours' face`,
      row.face === neighbour.face,
      `${row.face} against ${neighbour.face}`,
    );
    check(
      `${label} has the neighbours' measure`,
      near(row.box.left, neighbour.box.left) && near(row.box.width, neighbour.box.width),
      `${row.box.left}+${row.box.width} against ${neighbour.box.left}+${neighbour.box.width}`,
    );
    check(
      `${label} has the neighbours' padding, border, margin, and height`,
      row.box.padding === neighbour.box.padding &&
        row.box.border === neighbour.box.border &&
        row.box.margin === neighbour.box.margin &&
        near(row.box.height, neighbour.box.height),
      `${row.box.padding} / ${row.box.border} / ${row.box.margin} / ${row.box.height} against ` +
        `${neighbour.box.padding} / ${neighbour.box.border} / ${neighbour.box.margin} / ${neighbour.box.height}`,
    );
  }
  check(
    "open, the first hidden block starts where the summary ends",
    inserted.length > 0 && near(inserted[0].box.top, opened.summary.bottom),
    `${inserted[0]?.box.top} against ${opened.summary.bottom}`,
  );
  for (let index = 1; index < inserted.length; index += 1) {
    check(
      `open, "${inserted[index].text}" starts where the block before it ends`,
      near(inserted[index].box.top, inserted[index - 1].box.bottom),
      `${inserted[index].box.top} against ${inserted[index - 1].box.bottom}`,
    );
  }
  check(
    "open, the fold ends where its last block ends",
    inserted.length > 0 && near(opened.fold.bottom, inserted.at(-1).box.bottom),
    `${opened.fold.bottom} against ${inserted.at(-1)?.box.bottom}`,
  );
  check(
    "open, the summary does not move",
    near(opened.summary.top, closed.summary.top) &&
      near(opened.summary.height, closed.summary.height),
    `${opened.summary.top}/${opened.summary.height} against ${closed.summary.top}/${closed.summary.height}`,
  );
  const added = inserted.reduce((sum, row) => sum + row.box.height, 0);
  const shownOpen = opened.rows.filter((row) => !row.folded);
  closed.rows.forEach((row, index) => {
    const moved = shownOpen[index].box.top - row.box.top;
    const expected = index < after ? 0 : added;
    check(
      `open, "${row.text}" moves by the inserted blocks alone`,
      Math.abs(moved - expected) <= 2 * TOLERANCE_PX,
      `moved ${moved}, inserted ${expected}`,
    );
  });

  // Closing restores the closed layout.
  const layout = (/** @type {any} */ read) =>
    JSON.stringify({ fold: read.fold, summary: read.summary, rows: read.rows, own: read.own });
  check("closed again, the fold is closed", reclosed.open === false);
  check("closed again, every box is where it was", layout(reclosed) === layout(closed));

  // A document's own details keeps KPress's box: the fold's rule is the diff's alone.
  check(
    "a document's own details keeps its border",
    closed.own.border === "1px 1px 1px 1px",
    closed.own.border,
  );
} finally {
  await chrome?.close();
  server.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`diff fold in Chrome: ${checks} checks passed\n`);
