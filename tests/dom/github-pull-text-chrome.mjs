// The space around a heading in a pull request's text, laid out by a real engine: KPress's
// render of one Markdown text, rebuilt by the production inert path (static/inert-html.js),
// in the page's card under the shell's, the page's, and KPress's stylesheets, in headless
// Chrome. The same render is set in a document's frame beside it.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     KPRESS_STATIC=/dir/with/kpress/css/and/fonts SPACING_INPUT=/path/to/input.json \
//     node tests/dom/github-pull-text-chrome.mjs
//
// tests/test_github_pull_text_chrome.py renders the texts, writes SPACING_INPUT ({sheets,
// texts: [{part, html}], document}), copies KPress's stylesheets and faces out of the
// installed package, owns the profile, and runs this in a process group of its own.
//
// The card is pull-page.js's own (`textBlock` and `kpressHost`): a card head, then the text,
// whose host holds `article.kpress.kpress-inert` around `kpressProse`. The document frame is
// the inert document render's (builtin_plugins/markdown/inert-render.js).
//
// A heading belongs to the section it opens, so it must sit nearer what follows it than what
// precedes it, at the top of a text as much as inside one: docs/design-system.md, "The Pull
// Request Page", "Text". Inside a text the space around a heading is KPress's, so each level
// after each kind of block must measure what it measures in a document. Margins and their
// collapsing are layout, which no browserless DOM computes.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const GITHUB = path.join(root, "src/metabrowser/builtin_plugins/github");
const KPRESS = path.resolve(/** @type {string} */ (process.env.KPRESS_STATIC));
const INPUT = JSON.parse(
  fs.readFileSync(/** @type {string} */ (process.env.SPACING_INPUT), "utf8"),
);
const LEVELS = ["h1", "h2", "h3"];
const BLOCKS = ["p", "ul", "pre", "blockquote"];
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

// The order the page loads them in: KPress's tokens and the shell's sheet with the shell,
// the page's with the plugin, and KPress's document sheets with the first text's render.
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>pull text spacing</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/github/styles.css">
${INPUT.sheets.map((sheet) => `<link rel="stylesheet" href="/kpress/${sheet}">`).join("\n")}
<script src="/static/inert-html.js"></script>
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
    } else if (url.pathname.startsWith("/github/")) {
      file = path.join(GITHUB, url.pathname.slice(8));
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

// In the page: set each text in a card and the document in its frame, then read, for every
// heading, the space between its box and the box before it and after it.
const MEASURE = `async (texts, document_html) => {
  const inert = window.MetabrowserInertHtml;
  const base = "https://github.com/octo/demo/pull/7";
  const el = (tag, className, children = []) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.append(...children);
    return node;
  };
  const prose = (html) => inert.kpressProse(inert.sanitizeHtml(html, base), document);
  const cards = texts.map(({ part, html }) => {
    const text = el("div", "github-pull-text", [
      el("div", "metabrowser-kpress-host", [el("article", "kpress kpress-inert", [prose(html)])]),
    ]);
    text.setAttribute("data-part", part);
    return el("section", "page-card github-pull-card", [el("div", "github-pull-card-head", ["author opened"]), text]);
  });
  const article = el("article", "kpress kpress-doc kpress-inert", [el("div", "kpress-doc-layout", [prose(document_html)])]);
  article.setAttribute("data-kpress-card", "on");
  article.querySelector(".kpress-prose").classList.add("kpress-long-text");
  document.getElementById("preview-pane").replaceChildren(
    el("div", "github-pull", [el("div", "github-pull-body", cards)]),
    el("div", "metabrowser-kpress-host", [article]),
  );
  await document.fonts.ready;
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const round = (value) => Math.round(value * 100) / 100;
  const read = (scope) => {
    const rows = [];
    for (const heading of scope.querySelectorAll(".kpress-prose > :is(h1, h2, h3)")) {
      const before = heading.previousElementSibling;
      // A heading that opens a text: the box before it is the card head.
      const above = before ?? heading.closest(".github-pull-text")?.previousElementSibling;
      const after = heading.nextElementSibling;
      const box = heading.getBoundingClientRect();
      rows.push({
        level: heading.tagName.toLowerCase(),
        after: before ? before.tagName.toLowerCase() : "opening",
        above: above ? round(box.top - above.getBoundingClientRect().bottom) : null,
        below: after ? round(after.getBoundingClientRect().top - box.bottom) : null,
        next: after ? after.tagName.toLowerCase() : null,
      });
    }
    return rows;
  };
  return {
    text: cards.flatMap((card) => read(card)),
    document: read(article),
  };
}`;

const server = await serve();
const { port } = /** @type {import("node:net").AddressInfo} */ (server.address());
/** @type {Awaited<ReturnType<typeof launchChrome>> | null} */
let chrome = null;
try {
  chrome = await launchChrome(/** @type {string} */ (process.env.CHROME_BIN), {
    profiles: /** @type {string} */ (process.env.CHROME_PROFILES),
    width: 1000,
    height: 800,
  });
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `http://127.0.0.1:${port}/` });
  await chrome.waitFor("document.readyState === 'complete' && !!window.MetabrowserInertHtml");
  const measured = await chrome.evaluate(
    `(${MEASURE})(${JSON.stringify(INPUT.texts)}, ${JSON.stringify(INPUT.document)})`,
  );
  process.stderr.write(`${JSON.stringify(measured)}\n`);
  const key = (row) => `${row.level} after ${row.after}`;
  const inText = new Map(measured.text.map((row) => [key(row), row]));
  const inDocument = new Map(measured.document.map((row) => [key(row), row]));
  // Every case the texts were written to hold, so a changed text cannot drop one unseen.
  for (const level of LEVELS) {
    for (const after of ["opening", ...BLOCKS]) {
      check(`${level} after ${after} is in a text`, inText.has(`${level} after ${after}`));
    }
  }
  for (const row of measured.text) {
    const label = `in a text, ${key(row)}`;
    check(`${label} has space above it`, row.above !== null && row.above > 0, `${row.above}`);
    check(`${label} has space below it`, row.below !== null && row.below > 0, `${row.below}`);
    // Nearer its own section than the one before it: at the top of a text, the card head.
    check(
      `${label} is no nearer what precedes it than what follows it`,
      row.above !== null && row.below !== null && row.above + 0.01 >= row.below,
      `${row.above} px above, ${row.below} px below`,
    );
    // Inside a text the space is KPress's, the same as a document's.
    if (row.after !== "opening") {
      const same = inDocument.get(key(row));
      check(
        `${label} is spaced as in a document`,
        same !== undefined &&
          Math.abs(same.above - row.above) < 0.01 &&
          Math.abs(same.below - row.below) < 0.01,
        `${row.above}/${row.below} px against ${same?.above}/${same?.below} px`,
      );
    }
  }
  // An opening heading keeps the space below it that it keeps inside a text.
  for (const level of LEVELS) {
    const opening = inText.get(`${level} after opening`);
    const inside = inText.get(`${level} after p`);
    check(
      `${level} opening a text keeps its space below`,
      opening !== undefined &&
        inside !== undefined &&
        Math.abs(opening.below - inside.below) < 0.01,
      `${opening?.below} px against ${inside?.below} px`,
    );
  }
} finally {
  await chrome?.close();
  server.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`pull text spacing in Chrome: ${checks} checks passed\n`);
