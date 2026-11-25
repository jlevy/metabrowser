// A rendered Markdown diff's fold of unchanged blocks, laid out by headless Chrome: the
// production `createMarkdownViews` (builtin_plugins/diff/diff-markdown.js) mounts the
// route's Concise answer into the article a pull request's Changes mounts, under the
// shell's, the diff and GitHub plugins', and KPress's stylesheets, beside a code file's
// fold bar as diff-view.js builds it (`foldExpander` in diff-fold.js).
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     KPRESS_STATIC=/dir/with/kpress/css/and/fonts FOLD_INPUT=/path/to/input.json \
//     [FOLD_SHOTS=/dir/for/screenshots] node tests/dom/diff-markdown-fold-chrome.mjs
//
// tests/test_diff_markdown_fold_chrome.py writes FOLD_INPUT ({sheets, answer, quoted,
// docMaxChars}), copies KPress's stylesheets and faces out of the installed package, owns
// the profile, and runs this in a process group of its own. FOLD_SHOTS, when set,
// receives a screenshot of the comparison closed and open, and of a code fold bar and a
// review comment's fold of earlier lines, closed, under the pointer, and open, in each
// theme and with forced colors.
//
// Every fold of a diff draws as one bar: a rendered Markdown file's run of unchanged
// blocks is the bar a code file's long run of changed lines is, the same element, classes,
// and computed style, at rest and under the pointer, across the file's width. The bar is a
// `button` inside the comparison's `article.kpress`, so KPress's document stylesheets
// reach it, and only a browser computes that cascade. Closed, the bar stands between the
// blocks around it and the space on each side of it is those blocks' margins; open, the
// blocks it held stand after it in the face, measure, and spacing of the blocks around
// them, the bar does not move, and everything after it moves by one amount; closed again,
// the layout is as it was. A KPress document beside the diff keeps its own `<details>` in
// KPress's box and ring: the fold bar's rules are the diff's alone.
//
// Every fold leads with the shell's expand/contract pair, never the registry's chevron
// (docs/design-system.md, "Fold Expanders"): `.fold-expander::before`, Lucide
// chevrons-up-down while closed and chevrons-down-up while open, read from a button's
// `aria-expanded` and from a native summary's `details[open]`, at the chevron's size,
// unturned, muted at rest and in the text's ink under the pointer or the focus ring, in
// the light and the dark theme. The summary is a review comment's fold of earlier lines,
// in pull-page.js's markup under the GitHub plugin's stylesheet. Forced colors force every
// author background to Canvas, the ground a masked glyph sits on, so there each fold's
// glyph, and a document's own summary's chevron, is drawn in CanvasText.
//
// Last, a comparison of a quote holding inline code and of a code block (FOLD_INPUT's
// `quoted` blocks) is drawn beside a document holding the same blocks: in the light and
// the dark theme, its quote and code draw as the document's do, in the app's tokens. The
// comparison's article sits outside `.metabrowser-kpress-host`, so a token bridge keyed on
// that host left it in KPress's own palette.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const DIFF = path.join(root, "src/metabrowser/builtin_plugins/diff");
const GITHUB = path.join(root, "src/metabrowser/builtin_plugins/github");
const KPRESS = path.resolve(/** @type {string} */ (process.env.KPRESS_STATIC));
const INPUT = JSON.parse(fs.readFileSync(/** @type {string} */ (process.env.FOLD_INPUT), "utf8"));
const SHOTS = process.env.FOLD_SHOTS;
// Layout puts box edges on 1/64 px, and the arithmetic below takes the unrounded rects, so
// anything nearer than that is the same place, however many heights are summed.
const TOLERANCE_PX = 1 / 64;
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const near = (a, b) => Math.abs(a - b) <= TOLERANCE_PX;

// KPress's tokens and the shell's sheet load with the shell, then the diff and GitHub
// plugins', as a pull request's page loads them.
// KPress's document stylesheets load last, the order in which the diff's rules must
// still win; in the app they may also load before the diff plugin's. The chooser is the
// shell's filter controls and the bars' chevron the shell's icon, both reached through
// `window.metabrowser` as the plugin SDK gives them.
const PAGE = `<!doctype html><html style="--doc-max-chars: ${INPUT.docMaxChars}"><head><meta charset="utf-8"><title>diff fold</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/diff/styles.css">
<link rel="stylesheet" href="/github/styles.css">
${INPUT.sheets.map((sheet) => `<link rel="stylesheet" href="/kpress/${sheet}">`).join("\n")}
<script src="/static/icons.js"></script>
<script>window.metabrowser = { icons: window.MetabrowserIcons };</script>
<script src="/static/filter-controls.js"></script>
<script src="/static/inert-html.js"></script>
<script type="module">
import { blockRow, createMarkdownViews, renderedFormat, sanitizeBlock } from "/diff/diff-markdown.js";
import { foldExpander } from "/diff/diff-fold.js";
window.diffFold = { blockRow, createMarkdownViews, renderedFormat, sanitizeBlock, foldExpander };
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

// In the page: mount the Concise answer as a pull request's Changes mounts a Markdown
// file, through the views, and below it a code file whose hunk holds a fold bar built as
// diff-view.js builds one, beside a document with a `<details>` of its own. Resolves with
// the comparison's fold bars once it is drawn.
const MOUNT = `async (answer) => {
  const { createMarkdownViews, renderedFormat, foldExpander } = window.diffFold;
  const el = (tag, className, children = []) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.append(...children);
    return node;
  };
  const host = el("div", "github-pull-diff metabrowser-diff-host");
  const section = el("section", "diff-file");
  const end = el("div", "diff-file-end");
  const bar = el("div", "diff-file-bar", [el("button", "diff-file-toggle"), end]);
  const source = el("div", "diff-file-body");
  source.id = "diff-file-guide";
  section.append(bar, source);
  const code = foldExpander({
    id: "diff-fold-group-code",
    expanded: false,
    label: (open) => (open ? "Hide 40 lines" : "40 more changed lines"),
    onToggle: () => {},
  });
  const hunk = el("div", "diff-hunk diff-hunk-unified", [code.control, code.group]);
  const codeFile = el("section", "diff-file diff-file-code", [el("div", "diff-file-body", [hunk])]);
  host.append(section, codeFile);
  const own = el("details", "", [el("summary", "", ["A document's own details"]), el("p", "", ["Inside."])]);
  const documentArticle = el("article", "kpress kpress-doc kpress-inert", [
    el("div", "kpress-doc-layout", [el("div", "kpress-prose", [own])]),
  ]);
  document.getElementById("preview-pane").replaceChildren(
    host,
    el("div", "metabrowser-kpress-host", [documentArticle]),
  );
  const views = createMarkdownViews({
    controls: window.metabrowser.filterControls,
    load: async () => structuredClone(answer),
    ensureInert: async () => window.MetabrowserInertHtml,
    loadStyles: async () => {},
    mutate: (change) => change(),
    opens: "concise",
    holdMs: 0,
  });
  views.add({
    section, bar, end, source, id: "docs/guide.md",
    format: renderedFormat({ new: { entry_type: "file", path: "docs/guide.md" } }),
  });
  views.observe(host, null);
  const article = section.querySelector("article.diff-markdown");
  for (let frame = 0; frame < 600 && !article.querySelector(".diff-markdown-block"); frame += 1) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  window.diffFoldViews = views;
  return [...article.querySelectorAll(".fold-expander")].map((node) => ({
    tag: node.tagName,
    className: node.className,
    expanded: node.getAttribute("aria-expanded"),
    controls: node.getAttribute("aria-controls"),
    group: document.getElementById(node.getAttribute("aria-controls"))?.className ?? null,
  }));
}`;

// Read geometry at two card widths under the same preview pane, so a column based on
// the viewport rather than the file box fails this check. A changed row's band is its
// ::before, set from the row's padding box, whose inline start is past the row's border.
const RENDERED_GEOMETRY = `(width) => {
  const file = document.querySelector(".diff-file");
  const row = file.querySelector(".diff-markdown-added");
  const style = getComputedStyle(row);
  const band = getComputedStyle(row, "::before");
  file.style.inlineSize = width + "px";
  const start = file.getBoundingClientRect().left + file.clientLeft;
  const end = start + file.clientWidth;
  const prose = row.querySelector(".kpress-prose").getBoundingClientRect();
  const rowBox = row.getBoundingClientRect();
  const result = {
    startInset: prose.left - start,
    endInset: end - prose.right,
    proseWidth: prose.width,
    bandStart: rowBox.left + parseFloat(style.borderLeftWidth) + parseFloat(band.left) - start,
    bandEnd: end - (rowBox.right - parseFloat(style.borderRightWidth) - parseFloat(band.right)),
    gutterColor: band.borderInlineStartColor,
    gutterWidth: parseFloat(band.borderInlineStartWidth),
  };
  file.style.removeProperty("inline-size");
  return result;
}`;

// What a fold bar computes, to hold a Markdown file's against a code file's.
const BAR_STYLE = [
  "display",
  "box-sizing",
  "height",
  "min-height",
  "padding-top",
  "padding-right",
  "padding-bottom",
  "padding-left",
  "margin-top",
  "margin-bottom",
  "border-top-width",
  "border-top-style",
  "border-top-color",
  "border-bottom-width",
  "border-bottom-style",
  "border-bottom-color",
  "border-left-width",
  "border-right-width",
  "border-radius",
  "background-color",
  "background-image",
  "box-shadow",
  "color",
  "font-family",
  "font-size",
  "font-weight",
  "font-style",
  "line-height",
  "letter-spacing",
  "text-align",
  "text-transform",
  "gap",
  "align-items",
  "cursor",
  "user-select",
];

// In the page: a fold's glyph, its ::before, which a pseudo-element's box does not report,
// so where it starts is where its label starts, less the bar's gap and the glyph's width;
// with the markup's drawn glyphs, which a fold has none of, and the chevron's size token.
const GLYPH_OF = `(node) => {
  const style = getComputedStyle(node);
  const glyph = getComputedStyle(node, "::before");
  const shown = [...node.children].find((child) => getComputedStyle(child).display !== "none");
  const start = shown.getBoundingClientRect().left - node.getBoundingClientRect().left;
  const probe = document.createElement("span");
  probe.style.display = "block";
  probe.style.width = "var(--toggle-chevron-size)";
  node.append(probe);
  const chevronSize = getComputedStyle(probe).width;
  probe.remove();
  return {
    glyphStart: start - parseFloat(style.columnGap) - parseFloat(glyph.width),
    glyphWidth: parseFloat(glyph.width),
    glyph: {
      content: glyph.content,
      width: glyph.width,
      height: glyph.height,
      chevronSize,
      mask: glyph.maskImage,
      ink: glyph.backgroundColor,
      transform: glyph.transform,
      drawn: node.querySelectorAll("svg, img").length,
      inset: parseFloat(style.paddingLeft) + parseFloat(style.borderLeftWidth),
    },
  };
}`;

// In the page: both bars, their files, and their groups, every block row of the
// comparison, and the document's own details, with box edges unrounded.
const READ = `() => {
  const names = ${JSON.stringify(BAR_STYLE)};
  const glyphOf = ${GLYPH_OF};
  const box = (node) => {
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return {
      top: rect.top, bottom: rect.bottom, left: rect.left, width: rect.width,
      height: rect.height, padding: style.padding, margin: style.margin,
      border: ["top", "right", "bottom", "left"]
        .map((side) => style.getPropertyValue("border-" + side + "-width")).join(" "),
    };
  };
  const bar = (node) => {
    const file = node.closest(".diff-file");
    const fileRect = file.getBoundingClientRect();
    const style = getComputedStyle(node);
    const label = node.querySelector(".diff-fold-label").getBoundingClientRect();
    return {
      ...box(node),
      style: Object.fromEntries(names.map((name) => [name, style.getPropertyValue(name)])),
      text: node.textContent,
      expanded: node.getAttribute("aria-expanded"),
      startInFile: node.getBoundingClientRect().left - fileRect.left - file.clientLeft,
      fileWidth: file.clientWidth,
      ...glyphOf(node),
      labelStart: label.left - node.getBoundingClientRect().left,
      labelMiddle: (label.top + label.bottom) / 2 - node.getBoundingClientRect().top,
    };
  };
  const face = (row) => {
    const style = getComputedStyle(row.querySelector(".kpress-prose > *"));
    return [style.fontFamily, style.fontSize, style.fontWeight, style.lineHeight, style.color,
      style.fontFeatureSettings, style.fontVariant, style.letterSpacing, style.margin].join(" | ");
  };
  const article = document.querySelector("article.diff-markdown");
  const control = article.querySelector(".fold-expander");
  const group = document.getElementById(control.getAttribute("aria-controls"));
  const rows = [...article.querySelectorAll(".diff-markdown-block")].map((row) => ({
    text: row.textContent.trim(),
    folded: group.contains(row),
    // Whether the row comes before the bar in the document, or is in its group or after it.
    first: !!(row.compareDocumentPosition(control) & Node.DOCUMENT_POSITION_FOLLOWING),
    box: box(row),
    face: face(row),
    // Its block's margins, which pass through the row to collapse with its neighbours'.
    marginTop: parseFloat(getComputedStyle(row.querySelector(".kpress-prose > *")).marginTop),
    marginBottom: parseFloat(getComputedStyle(row.querySelector(".kpress-prose > *")).marginBottom),
  }));
  return {
    bar: bar(control),
    code: bar(document.querySelector(".diff-file-code .fold-expander")),
    group: { ...box(group), children: group.children.length, className: group.className },
    rows,
    own: box(document.querySelector(".kpress-doc details")),
  };
}`;

// Wait for an open or a close to finish: the group keeps its height for five frames.
const SETTLE = `new Promise((resolve) => {
  const control = document.querySelector("article.diff-markdown .fold-expander");
  const group = document.getElementById(control.getAttribute("aria-controls"));
  let last = -1;
  let still = 0;
  const frame = () => {
    const height = group.getBoundingClientRect().height;
    still = height === last ? still + 1 : 0;
    last = height;
    if (still >= 5) resolve(height); else requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
})`;
const CLICK = `document.querySelector("article.diff-markdown .fold-expander").click()`;

// A bar's background once its transition is over (one value for five frames), and its
// centre, to put the pointer on.
const BACKGROUND = (/** @type {string} */ selector) => `new Promise((resolve) => {
  const node = document.querySelector(${JSON.stringify(selector)});
  const rect = node.getBoundingClientRect();
  let last = "";
  let still = 0;
  const frame = () => {
    const background = getComputedStyle(node).backgroundColor;
    still = background === last ? still + 1 : 0;
    last = background;
    if (still >= 5) {
      resolve({ background, x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
    } else {
      requestAnimationFrame(frame);
    }
  };
  requestAnimationFrame(frame);
})`;
const MARKDOWN_BAR = "article.diff-markdown .fold-expander";
// The fold's two glyphs, KPress's table-of-contents pair, each known by a path only it has.
const CLOSED_GLYPH = { name: "chevrons-up-down", path: "m7 15 5 5 5-5" };
const OPEN_GLYPH = { name: "chevrons-down-up", path: "m7 20 5-5 5 5" };
// In the page: a review comment's card holding a hunk whose earlier lines fold behind a
// native summary, in the markup pull-page.js builds and the classes the GitHub plugin's
// stylesheet styles, after the diff; its `details[open]` alone says its state.
const MOUNT_SUMMARY = `() => {
  const el = (tag, className, children = []) => {
    const node = document.createElement(tag);
    node.className = className;
    node.append(...children);
    return node;
  };
  const line = (text) => el("div", "github-pull-hunk-line", [text]);
  const details = el("details", "github-pull-hunk-earlier", [
    el("summary", "fold-expander disclosure-toggle", [
      el("span", "github-pull-fold-closed", ["3 earlier lines"]),
      el("span", "github-pull-fold-open", ["Hide 3 lines"]),
    ]),
    el("div", "github-pull-hunk", [line("The three lines above the comment.")]),
  ]);
  const box = el("div", "github-pull-hunk-box", [details, el("div", "github-pull-hunk", [line("+ shown")])]);
  const card = el("div", "page-card github-pull-card", [box]);
  document.querySelector(".metabrowser-diff-host").after(el("div", "github-pull", [card]));
  return true;
}`;
const SUMMARY_DETAILS = ".github-pull-hunk-earlier";
const SUMMARY_FOLD = `${SUMMARY_DETAILS} > summary`;
// In the page: the glyph's ink and the tokens it is held to, where the fold is, whether
// the fold is under the pointer or the focus ring, and the words it shows.
const INK = (/** @type {string} */ selector) => `(() => {
  const node = document.querySelector(${JSON.stringify(selector)});
  const token = (name) => {
    const probe = document.createElement("span");
    probe.style.color = "var(" + name + ")";
    node.append(probe);
    const color = getComputedStyle(probe).color;
    probe.remove();
    return color;
  };
  return {
    ink: getComputedStyle(node, "::before").backgroundColor,
    mask: getComputedStyle(node, "::before").maskImage,
    muted: token("--muted"),
    text: token("--text"),
    hovered: node.matches(":hover"),
    focused: node.matches(":focus-visible"),
    shown: [...node.children]
      .filter((child) => getComputedStyle(child).display !== "none")
      .map((child) => child.textContent),
  };
})()`;
const CODE_BAR = ".diff-file-code .fold-expander";
// A document's own summary, whose trailing chevron the shell masks too.
const OWN_SUMMARY = ".metabrowser-kpress-host .kpress-doc details > summary";
// In the page, with forced colors emulated: the ink of the glyph the control *selector*
// masks on its *pseudo*-element, beside the mode's Canvas and CanvasText resolved there.
const FORCED = (/** @type {string} */ selector, pseudo = "::before") => `(() => {
  const node = document.querySelector(${JSON.stringify(selector)});
  const system = (name) => {
    const probe = document.createElement("span");
    probe.style.color = name;
    node.append(probe);
    const color = getComputedStyle(probe).color;
    probe.remove();
    return color;
  };
  const glyph = getComputedStyle(node, ${JSON.stringify(pseudo)});
  return {
    forced: matchMedia("(forced-colors: active)").matches,
    ink: glyph.backgroundColor,
    mask: glyph.maskImage,
    canvas: system("Canvas"),
    canvasText: system("CanvasText"),
    hovered: node.matches(":hover"),
  };
})()`;
// The chevron a document's own summary trails, known by its path.
const CHEVRON_PATH = "m9 18 6-6-6-6";
// The controls whose keyboard ring the session reads, both bars and a document's own
// summary, and how many presses of Tab it allows to reach them all from the page's start:
// a handful do on this small page, so the bound only stops a page that lost one.
const RINGED = { fold: MARKDOWN_BAR, code: CODE_BAR, own: ".kpress-doc details > summary" };
const TAB_STEPS = 20;
// In the page, once the keyboard has focused the control *selector* names: the ring it
// draws, beside the shell's ring tokens resolved where it is; null while focus is elsewhere.
const RING = `(selector) => {
  const control = document.querySelector(selector);
  if (document.activeElement !== control) return null;
  const probe = document.createElement("span");
  probe.style.outline = "var(--focus-ring-width) solid var(--focus-ring-color)";
  probe.style.outlineOffset = "var(--focus-ring-offset)";
  probe.style.color = "var(--text)";
  control.append(probe);
  const token = getComputedStyle(probe);
  const ring = { width: token.outlineWidth, color: token.outlineColor, offset: token.outlineOffset };
  const textInk = token.color;
  probe.remove();
  const style = getComputedStyle(control);
  return {
    visible: control.matches(":focus-visible"),
    hovered: control.matches(":hover"),
    glyphInk: getComputedStyle(control, "::before").backgroundColor,
    textInk,
    ring,
    drawn: {
      style: style.outlineStyle,
      width: style.outlineWidth,
      color: style.outlineColor,
      offset: style.outlineOffset,
    },
  };
}`;
// In the page: a comparison of a quote and a code block, its rows built as the views
// build them, beside a document holding the same blocks.
const MOUNT_QUOTED = `(blocks) => {
  window.diffFoldViews?.dispose();
  const inert = window.MetabrowserInertHtml;
  const { blockRow, sanitizeBlock } = window.diffFold;
  const el = (tag, className, children = []) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.append(...children);
    return node;
  };
  const scratch = document.implementation.createHTMLDocument("");
  const template = document.createElement("template");
  const content = document.createDocumentFragment();
  const build = (html) => sanitizeBlock(html, inert, template, scratch, () => false);
  content.append(...blocks.map((block) => blockRow(block, build)));
  const rendered = el("article", "kpress kpress-inert diff-markdown", [content]);
  const quote = el("blockquote", "", [
    el("p", "", ["Quoted text with ", el("code", "", ["inline code"]), "."]),
  ]);
  const documentArticle = el("article", "kpress kpress-doc kpress-inert", [
    el("div", "kpress-doc-layout", [
      el("div", "kpress-prose", [quote, el("pre", "kpress-code", [el("code", "", ["make test"])])]),
    ]),
  ]);
  document.getElementById("preview-pane").replaceChildren(
    el("div", "github-pull-diff metabrowser-diff-host", [el("section", "diff-file", [rendered])]),
    el("div", "metabrowser-kpress-host", [documentArticle]),
  );
  return ["blockquote code", "pre.kpress-code"].every(
    (selector) => rendered.querySelectorAll(selector).length === 1,
  );
}`;
// The computed style of the comparison's quote and code and of the document's, once they
// keep one value for five frames, with the app's border and muted tokens resolved where
// the comparison is.
const QUOTED = `new Promise((resolve) => {
  const parts = {
    blockquote: ["border-left-width", "border-left-style", "border-left-color", "color"],
    "blockquote code": ["border-top-color", "border-top-left-radius", "padding-top",
      "padding-left", "color", "background-color"],
    "pre.kpress-code": ["border-top-color", "border-top-left-radius", "color",
      "background-color"],
  };
  const read = (root) => Object.fromEntries(Object.entries(parts).map(([selector, names]) => {
    const style = getComputedStyle(root.querySelector(selector));
    return [selector, Object.fromEntries(names.map((name) => [name, style.getPropertyValue(name)]))];
  }));
  const comparison = document.querySelector(".diff-markdown");
  const token = (name) => {
    const probe = document.createElement("span");
    probe.style.color = "var(" + name + ")";
    comparison.append(probe);
    const color = getComputedStyle(probe).color;
    probe.remove();
    return color;
  };
  let last = "";
  let still = 0;
  const frame = () => {
    const value = JSON.stringify({
      comparison: read(comparison),
      document: read(document.querySelector(".kpress-doc")),
    });
    still = value === last ? still + 1 : 0;
    last = value;
    if (still >= 5) {
      resolve({ ...JSON.parse(value), border: token("--border"), muted: token("--muted") });
    } else {
      requestAnimationFrame(frame);
    }
  };
  requestAnimationFrame(frame);
})`;
/** @param {"light" | "dark"} theme The app's resolved theme, set on the root as it sets it. */
const THEME = (theme) => `(() => {
  document.documentElement.setAttribute("data-theme", "${theme}");
  document.documentElement.setAttribute("data-kpress-resolved-theme", "${theme}");
  return true;
})()`;
// Rounded to hundredths for the record; the checks take the unrounded values.
const rounded = (/** @type {string} */ _key, /** @type {unknown} */ value) =>
  typeof value === "number" ? Math.round(value * 100) / 100 : value;

const server = await serve();
const { port } = /** @type {import("node:net").AddressInfo} */ (server.address());
/** @type {Awaited<ReturnType<typeof launchChrome>> | null} */
let chrome = null;
/** @param {string} name @param {string[]} selectors What it shows. @param {number} scale */
const shot = async (name, selectors = [".metabrowser-diff-host"], scale = 1) => {
  if (!SHOTS || !chrome) {
    return;
  }
  const clip = await chrome.evaluate(`(() => {
    const rects = ${JSON.stringify(selectors)}.map((selector) =>
      document.querySelector(selector).getBoundingClientRect());
    const x = Math.min(...rects.map((rect) => rect.left));
    const y = Math.min(...rects.map((rect) => rect.top));
    const width = Math.max(...rects.map((rect) => rect.right)) - x;
    const height = Math.max(...rects.map((rect) => rect.bottom)) - y;
    return { x, y, width, height, scale: ${scale} };
  })()`);
  const { data } = await chrome.send("Page.captureScreenshot", { format: "png", clip });
  fs.mkdirSync(SHOTS, { recursive: true });
  fs.writeFileSync(path.join(SHOTS, `${name}.png`), Buffer.from(data, "base64"));
};
/** @param {{x: number, y: number}} at */
const point = (at) =>
  chrome?.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: at.x, y: at.y });
/** @param {string} selector Where the centre of the element it names is. */
const centre = (selector) =>
  chrome?.evaluate(`(() => {
    const rect = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  })()`);
/** @param {boolean} open Opens, or closes, the code fold and the review comment's fold. */
const OPEN_FOLDS = (open) =>
  `(document.querySelector(${JSON.stringify(CODE_BAR)}).click(), document.querySelector(${JSON.stringify(SUMMARY_DETAILS)}).open = ${open}, true)`;
// A data URI as the page computes it, with its escapes undone, to find a path in.
const decoded = (/** @type {string} */ value) => {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
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
    "document.readyState === 'complete' && !!window.MetabrowserInertHtml && !!window.diffFold && !!window.metabrowser.filterControls",
  );
  const bars = await chrome.evaluate(`(${MOUNT})(${JSON.stringify(INPUT.answer)})`);
  check(
    "the comparison draws one fold, as the diff's fold bar and the group it controls",
    bars.length === 1 &&
      bars[0].tag === "BUTTON" &&
      bars[0].className === "fold-expander diff-fold-control disclosure-toggle" &&
      bars[0].expanded === "false" &&
      bars[0].group === "diff-fold-group diff-markdown-fold diff-fold-collapsed",
    JSON.stringify(bars),
  );
  await chrome.evaluate("document.fonts.ready.then(() => true)");
  const wide = await chrome.evaluate(`(${RENDERED_GEOMETRY})(1000)`);
  const narrow = await chrome.evaluate(`(${RENDERED_GEOMETRY})(360)`);
  for (const [size, measured] of [
    ["wide", wide],
    ["narrow", narrow],
  ]) {
    check(
      `${size}: the prose is centered in the diff box`,
      near(measured.startInset, measured.endInset),
      JSON.stringify(measured),
    );
    check(
      `${size}: the colored change gutter is at the edge of the full-width band`,
      near(measured.bandStart, 0) &&
        near(measured.bandEnd, 0) &&
        measured.gutterWidth > 0 &&
        measured.gutterColor !== "rgba(0, 0, 0, 0)",
      JSON.stringify(measured),
    );
  }
  check(
    "the prose grows to its reading measure while the wide card keeps extra margins",
    wide.proseWidth > narrow.proseWidth && wide.startInset > narrow.startInset,
    JSON.stringify({ wide, narrow }),
  );
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
  // The pointer has not entered the page yet; then it rests on each bar.
  const resting = await chrome.evaluate(BACKGROUND(MARKDOWN_BAR));
  const codeResting = await chrome.evaluate(BACKGROUND(CODE_BAR));
  await point(resting);
  const hovered = await chrome.evaluate(BACKGROUND(MARKDOWN_BAR));
  await point(codeResting);
  const codeHovered = await chrome.evaluate(BACKGROUND(CODE_BAR));
  // The keyboard walks the page from its start to the Markdown fold's bar, then to the code
  // fold's, then to the document's own summary, so `:focus-visible` holds on each as it
  // does for a reader.
  await chrome.evaluate("(document.activeElement?.blur(), true)");
  /** @type {Record<string, any>} */
  const rings = {};
  for (let step = 0; step < TAB_STEPS && !(rings.fold && rings.code && rings.own); step += 1) {
    for (const type of ["keyDown", "keyUp"]) {
      await chrome.send("Input.dispatchKeyEvent", {
        type,
        key: "Tab",
        code: "Tab",
        windowsVirtualKeyCode: 9,
      });
    }
    for (const [part, selector] of Object.entries(RINGED)) {
      rings[part] ??= await chrome.evaluate(`(${RING})(${JSON.stringify(selector)})`);
    }
  }
  // The glyph's ink in each theme, on a code fold's bar and on a native summary's fold, at
  // rest, under the pointer, and open, with the pointer off the page's folds between.
  await chrome.evaluate(`(${MOUNT_SUMMARY})()`);
  const away = { x: 1, y: 1 };
  const pictured = [".diff-file-code", SUMMARY_DETAILS];
  /** @type {Record<string, any>} */
  const inks = {};
  for (const theme of /** @type {const} */ (["light", "dark"])) {
    await chrome.evaluate(THEME(theme));
    await point(away);
    const rest = {
      code: await chrome.evaluate(INK(CODE_BAR)),
      summary: await chrome.evaluate(INK(SUMMARY_FOLD)),
    };
    await shot(`${theme}-closed`, pictured, 2);
    await point(await centre(CODE_BAR));
    const hoveredCode = await chrome.evaluate(INK(CODE_BAR));
    await shot(`${theme}-code-hover`, pictured, 2);
    await point(await centre(SUMMARY_FOLD));
    const hoveredSummary = await chrome.evaluate(INK(SUMMARY_FOLD));
    await point(away);
    await chrome.evaluate(OPEN_FOLDS(true));
    const open = {
      code: await chrome.evaluate(INK(CODE_BAR)),
      summary: await chrome.evaluate(INK(SUMMARY_FOLD)),
    };
    await shot(`${theme}-open`, pictured, 2);
    await chrome.evaluate(OPEN_FOLDS(false));
    inks[theme] = { rest, hovered: { code: hoveredCode, summary: hoveredSummary }, open };
  }
  // Forced colors, at rest, under the pointer, and open, then the page's own colors again.
  await chrome.send("Emulation.setEmulatedMedia", {
    features: [{ name: "forced-colors", value: "active" }],
  });
  await point(away);
  const forcedRest = {
    code: await chrome.evaluate(FORCED(CODE_BAR)),
    summary: await chrome.evaluate(FORCED(SUMMARY_FOLD)),
    own: await chrome.evaluate(FORCED(OWN_SUMMARY, "::after")),
  };
  await shot("forced-closed", pictured, 2);
  await point(await centre(CODE_BAR));
  const forcedHoveredCode = await chrome.evaluate(FORCED(CODE_BAR));
  await point(await centre(SUMMARY_FOLD));
  const forcedHoveredSummary = await chrome.evaluate(FORCED(SUMMARY_FOLD));
  await shot("forced-summary-hover", pictured, 2);
  await point(away);
  await chrome.evaluate(OPEN_FOLDS(true));
  const forcedOpen = {
    code: await chrome.evaluate(FORCED(CODE_BAR)),
    summary: await chrome.evaluate(FORCED(SUMMARY_FOLD)),
  };
  await shot("forced-open", pictured, 2);
  await chrome.evaluate(OPEN_FOLDS(false));
  await chrome.send("Emulation.setEmulatedMedia", { features: [] });
  const forced = {
    rest: forcedRest,
    hovered: { code: forcedHoveredCode, summary: forcedHoveredSummary },
    open: forcedOpen,
  };
  const quotedMounted = await chrome.evaluate(`(${MOUNT_QUOTED})(${JSON.stringify(INPUT.quoted)})`);
  await chrome.evaluate("document.fonts.ready.then(() => true)");
  /** @type {Record<string, any>} */
  const quoted = {};
  for (const theme of /** @type {const} */ (["light", "dark"])) {
    await chrome.evaluate(THEME(theme));
    quoted[theme] = await chrome.evaluate(QUOTED);
  }
  process.stderr.write(
    `${JSON.stringify({ closed, opened, reclosed, resting, hovered, codeResting, codeHovered, rings, inks, forced, quoted }, rounded)}\n`,
  );

  // The fold draws the shell's one ring (docs/design-system.md, "Focus Ring"). KPress's
  // document sheet rings a `summary` inside `article.kpress` 3px wide and 2px outside its
  // box; the fold's bar is a `button` there, which it does not ring, so the bar keeps the
  // shell's ring, as the code fold's bar outside the article does. A document's own summary
  // keeps KPress's ring, which shows that rule is live and that no fold rule reaches it.
  for (const [part, label] of [
    ["fold", "the Markdown fold's bar"],
    ["code", "a code fold's bar"],
  ]) {
    check(
      `Tab reaches ${label}, which matches :focus-visible`,
      rings[part]?.visible === true,
      JSON.stringify(rings[part] ?? null),
    );
    const drawn = rings[part]?.drawn;
    const oneRing = rings[part]?.ring;
    check(
      `the focused ${label.replace(/^a |^the /, "")} draws the shell's one ring`,
      drawn?.style === "solid" &&
        drawn.width === oneRing.width &&
        drawn.color === oneRing.color &&
        drawn.offset === oneRing.offset,
      JSON.stringify(rings[part] ?? null),
    );
  }
  check(
    "the Markdown fold's glyph takes the text's ink under the focus ring alone",
    rings.fold?.hovered === false && rings.fold.glyphInk === rings.fold.textInk,
    JSON.stringify(rings.fold ?? null),
  );
  check(
    "Tab reaches a document's own summary, which matches :focus-visible",
    rings.own?.visible === true,
    JSON.stringify(rings.own ?? null),
  );
  check(
    "a document's own focused summary keeps KPress's ring",
    rings.own?.drawn.style === "solid" &&
      rings.own.drawn.width !== rings.own.ring.width &&
      rings.own.drawn.offset !== rings.own.ring.offset,
    JSON.stringify(rings.own ?? null),
  );

  // One bar for every fold: the Markdown file's computes as the code file's does.
  for (const [state, measured] of [
    ["closed", closed],
    ["open", opened],
  ]) {
    for (const [name, value] of Object.entries(measured.code.style)) {
      check(
        `${state}, the Markdown fold bar's ${name} is a code fold bar's`,
        measured.bar.style[name] === value,
        `${measured.bar.style[name]} against ${value}`,
      );
    }
    for (const part of [
      "startInFile",
      "glyphStart",
      "glyphWidth",
      "labelStart",
      "labelMiddle",
      "height",
    ]) {
      check(
        `${state}, the Markdown fold bar's ${part} is a code fold bar's`,
        near(measured.bar[part], measured.code[part]),
        `${measured.bar[part]} against ${measured.code[part]}`,
      );
    }
    check(
      `${state}, the fold bar spans its file, as a code fold bar does`,
      near(measured.bar.startInFile, 0) &&
        near(measured.bar.width, measured.bar.fileWidth) &&
        near(measured.code.width, measured.code.fileWidth),
      `${measured.bar.startInFile}+${measured.bar.width} of ${measured.bar.fileWidth}; ` +
        `code ${measured.code.width} of ${measured.code.fileWidth}`,
    );
    // The code fold stays closed here; the theme checks below open it.
    for (const [which, bar, pair] of [
      ["Markdown", measured.bar, state === "closed" ? CLOSED_GLYPH : OPEN_GLYPH],
      ["closed code", measured.code, CLOSED_GLYPH],
    ]) {
      check(
        `${state}, the ${which} fold bar leads with ${pair.name}, drawn by .fold-expander`,
        bar.glyph.content === '""' &&
          decoded(bar.glyph.mask).includes(pair.path) &&
          bar.glyph.drawn === 0 &&
          near(bar.glyphStart, bar.glyph.inset),
        JSON.stringify(bar.glyph),
      );
      check(
        `${state}, the ${which} fold bar's glyph is the chevron's size, unturned`,
        bar.glyph.width === bar.glyph.chevronSize &&
          bar.glyph.height === bar.glyph.chevronSize &&
          bar.glyph.transform === "none",
        JSON.stringify(bar.glyph),
      );
    }
    check(
      `${state}, the fold bar never selects text`,
      measured.bar.style["user-select"] === "none",
      measured.bar.style["user-select"],
    );
  }
  check(
    "under the pointer, the Markdown fold bar takes the code fold bar's hover",
    hovered.background === codeHovered.background &&
      resting.background === codeResting.background &&
      hovered.background !== resting.background,
    `${resting.background} -> ${hovered.background}, code ${codeResting.background} -> ${codeHovered.background}`,
  );

  // The glyph in each theme: muted at rest, the text's ink under the pointer, and the pair's
  // other half once open, on a button's `aria-expanded` and a native summary's `open` alike.
  // Each shows one label, its closed words and then its open ones: the summary's from the
  // GitHub plugin's sheet, which hides the other state's.
  const WORDS = {
    code: ["40 more changed lines", "Hide 40 lines"],
    summary: ["3 earlier lines", "Hide 3 lines"],
  };
  for (const theme of /** @type {const} */ (["light", "dark"])) {
    const { rest, hovered: under, open } = inks[theme];
    for (const form of /** @type {const} */ (["code", "summary"])) {
      const name = form === "code" ? "a code fold bar" : "a review comment's fold";
      check(
        `${theme}, ${name} shows its closed words, then its open ones`,
        JSON.stringify([rest[form].shown, open[form].shown]) ===
          JSON.stringify(WORDS[form].map((words) => [words])),
        JSON.stringify([rest[form].shown, open[form].shown]),
      );
      check(
        `${theme}, ${name} at rest draws ${CLOSED_GLYPH.name} in the muted ink`,
        !rest[form].hovered &&
          rest[form].ink === rest[form].muted &&
          rest[form].muted !== rest[form].text &&
          decoded(rest[form].mask).includes(CLOSED_GLYPH.path),
        JSON.stringify(rest[form]),
      );
      check(
        `${theme}, ${name} under the pointer draws its glyph in the text's ink`,
        under[form].hovered && under[form].ink === under[form].text,
        JSON.stringify(under[form]),
      );
      check(
        `${theme}, ${name} open draws ${OPEN_GLYPH.name}`,
        !open[form].hovered &&
          open[form].ink === open[form].muted &&
          decoded(open[form].mask).includes(OPEN_GLYPH.path),
        JSON.stringify(open[form]),
      );
    }
  }
  // Forced colors: each fold's glyph in CanvasText, never the Canvas its background is
  // forced to, closed, under the pointer, and open, and a document's own chevron alike.
  for (const [state, read] of Object.entries(forced)) {
    for (const [form, value] of Object.entries(read)) {
      const name = {
        code: "a code fold bar",
        summary: "a review comment's fold",
        own: "a document's own summary",
      }[form];
      const glyph =
        form === "own" ? CHEVRON_PATH : state === "open" ? OPEN_GLYPH.path : CLOSED_GLYPH.path;
      check(
        `forced colors, ${name} ${state} draws its glyph in CanvasText, off the Canvas`,
        value.forced &&
          value.hovered === (state === "hovered") &&
          value.ink === value.canvasText &&
          value.ink !== value.canvas &&
          decoded(value.mask).includes(glyph),
        JSON.stringify(value),
      );
    }
  }
  check(
    "the dark theme moves the fold glyph's ink",
    inks.light.rest.code.ink !== inks.dark.rest.code.ink &&
      inks.light.hovered.code.ink !== inks.dark.hovered.code.ink,
    `${inks.light.rest.code.ink} and ${inks.dark.rest.code.ink}`,
  );

  // Closed: the bar between the blocks around it, its group empty and of no height.
  check(
    "closed, the group holds nothing and has no height",
    closed.group.children === 0 && closed.group.height === 0,
    `${closed.group.children} rows, ${closed.group.height}px`,
  );
  const after = closed.rows.findIndex((row) => !row.first);
  const before = after - 1;
  check("the fold has unchanged blocks on each side", before >= 1 && after > 0, `${after}`);
  // A block's margins pass through its row (styles.css), and the bar has none of its own,
  // so the space on each side of it is the margin of the block there.
  check(
    "closed, the space above the bar is the margin of the block before it",
    near(closed.bar.top - closed.rows[before].box.bottom, closed.rows[before].marginBottom),
    `${closed.bar.top - closed.rows[before].box.bottom} against ${closed.rows[before].marginBottom}`,
  );
  check(
    "closed, the space below the bar is the margin of the block after it",
    near(closed.rows[after].box.top - closed.bar.bottom, closed.rows[after].marginTop),
    `${closed.rows[after].box.top - closed.bar.bottom} against ${closed.rows[after].marginTop}`,
  );

  // Open: the hidden blocks after the bar, laid out as the unchanged blocks around them.
  const inserted = opened.rows.filter((row) => row.folded);
  check(
    "open, the group holds the blocks the bar counted",
    inserted.length > 0 &&
      inserted.length === opened.group.children &&
      closed.bar.text === `${inserted.length} unchanged blocks` &&
      opened.bar.text === `Hide ${inserted.length} blocks` &&
      opened.bar.expanded === "true",
    `${inserted.length} blocks, "${closed.bar.text}", "${opened.bar.text}"`,
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
    "open, the space above the first hidden block is its margin",
    inserted.length > 0 && near(inserted[0].box.top - opened.bar.bottom, inserted[0].marginTop),
    `${inserted[0]?.box.top - opened.bar.bottom} against ${inserted[0]?.marginTop}`,
  );
  // The two unchanged blocks right before the fold, spaced as the document spaces them.
  const spacing = opened.rows[before].box.top - opened.rows[before - 1].box.bottom;
  check("the blocks before the fold are spaced", spacing > 0, `${spacing}`);
  for (let index = 1; index < inserted.length; index += 1) {
    const gap = inserted[index].box.top - inserted[index - 1].box.bottom;
    check(
      `open, "${inserted[index].text}" is as far from the block before it as the blocks before the fold are`,
      near(gap, spacing),
      `${gap} against ${spacing}`,
    );
  }
  // The block after the fold, as far from the last block the fold holds as the blocks
  // before the fold are from each other: a group clipped by `overflow: hidden`, the code
  // fold's, kept that block's margin inside the group and doubled the space.
  const next = opened.rows.find((row) => !row.folded && !row.first);
  check(
    "open, the block after the fold is as far from the fold's last block as the blocks before the fold are",
    inserted.length > 0 &&
      next !== undefined &&
      near(next.box.top - inserted.at(-1).box.bottom, spacing),
    `${next?.box.top - inserted.at(-1)?.box.bottom} against ${spacing}`,
  );
  check(
    "open, the group ends where its last block ends",
    inserted.length > 0 && near(opened.group.bottom, inserted.at(-1).box.bottom),
    `${opened.group.bottom} against ${inserted.at(-1)?.box.bottom}`,
  );
  check(
    "open, the bar does not move",
    near(opened.bar.top, closed.bar.top) && near(opened.bar.height, closed.bar.height),
    `${opened.bar.top}/${opened.bar.height} against ${closed.bar.top}/${closed.bar.height}`,
  );
  const shownOpen = opened.rows.filter((row) => !row.folded);
  const moved = shownOpen[after].box.top - closed.rows[after].box.top;
  check("open, the blocks after the fold move down", moved > 0, `${moved}`);
  closed.rows.forEach((row, index) => {
    const by = shownOpen[index].box.top - row.box.top;
    const expected = index < after ? 0 : moved;
    check(
      `open, "${row.text}" moves by ${index < after ? "nothing" : "what the fold adds"}`,
      near(by, expected),
      `moved ${by}, expected ${expected}`,
    );
  });

  // Closing restores the closed layout.
  const layout = (/** @type {any} */ read) =>
    JSON.stringify({ bar: read.bar, group: read.group, rows: read.rows, own: read.own });
  check("closed again, the bar is closed", reclosed.bar.expanded === "false");
  check("closed again, every box is where it was", layout(reclosed) === layout(closed));

  // A document's own details keeps KPress's box: the fold bar's rules are the diff's alone.
  check(
    "a document's own details keeps its border",
    closed.own.border === "1px 1px 1px 1px",
    closed.own.border,
  );

  // A comparison's quote and code draw as a document's do, in the app's tokens, in either
  // theme; the theme switch has to move them for the comparison to mean anything.
  check("the quoted comparison has a quote with code and a code block", quotedMounted === true);
  for (const [theme, measured] of Object.entries(quoted)) {
    for (const [part, properties] of Object.entries(measured.document)) {
      for (const [property, value] of Object.entries(/** @type {object} */ (properties))) {
        const drawn = measured.comparison[part][property];
        check(
          `${theme}, the comparison's ${part} ${property} is the document's`,
          drawn === value,
          `${drawn} against ${value}`,
        );
      }
    }
    const quote = measured.comparison.blockquote;
    check(
      `${theme}, the comparison's quote rule is the app's border`,
      quote["border-left-color"] === measured.border,
      `${quote["border-left-color"]} against ${measured.border}`,
    );
    check(
      `${theme}, the comparison's quoted text is the app's muted tone`,
      quote.color === measured.muted,
      `${quote.color} against ${measured.muted}`,
    );
  }
  check(
    "the dark theme moves the comparison's quote rule",
    quoted.light.comparison.blockquote["border-left-color"] !==
      quoted.dark.comparison.blockquote["border-left-color"],
    quoted.dark.comparison.blockquote["border-left-color"],
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
