// Browserless session: a Markdown document whose front matter is not read, shown once.
//
// The server parses a file's front matter from its own bytes and, when it cannot, says
// why in the render's `frontmatter_error` diagnostic; KPress draws its Frontmatter error
// notice ahead of the layout. This session mounts the production Document view
// (builtin_plugins/markdown/rendered.js) with the production wiki preprocessing run in
// place of its Worker, the production placement (place-rendered.js, then inert-render.js)
// and static/inert-html.js, against render answers of the shapes the server sends:
//
// - The text the view sends to render keeps the front matter as the file has it. Before,
//   the preprocessor read the last key, over the closing `---`, as a setext heading and
//   wrote its anchor into the YAML, and a pin parsed that text.
// - A trusted render carries KPress's notice; an inert one does not (the server takes
//   it out, `kpress_adapter.inert_render`), and the page draws the same notice from the
//   diagnostic. Either way the document's preamble holds one notice with the reader's
//   sentence, never the parser's reason (`frontmatter_error_detail`), and
//   the Diagnostics disclosure lists the render's other diagnostics only; a render whose
//   only diagnostic is the front-matter error has no disclosure.
//
// The server's halves are pinned by goldens: what `/api/kpress/render` answers for a
// pinned blob's front matter (cli-api-pin-frontmatter.tryscript.md), and the inert HTML
// without KPress's notice (cli-api-frontmatter-bounds.tryscript.md). Paint, the box
// KPress's stylesheet draws, is the browser's.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const markdownDir = path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown");
const inertPath = path.join(repoRoot, "src/metabrowser/static/inert-html.js");
// The page window the print theme hold listens on (print-indicator.js); nothing prints here.
const sandbox = { window: { addEventListener() {}, removeEventListener() {} }, URL };
vm.runInNewContext(fs.readFileSync(inertPath, "utf8"), sandbox, { filename: inertPath });
const inert = sandbox.window.MetabrowserInertHtml;

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

// A small element tree: enough of the DOM for the modules under test, with selectors
// limited to compounds of a tag, classes, and attributes, optionally after `:scope >`.
class Text {
  constructor(value, ownerDocument) {
    this.nodeType = 3;
    this.nodeValue = value;
    this.ownerDocument = ownerDocument;
    this.parentElement = null;
  }
  get textContent() {
    return this.nodeValue;
  }
}

class Element {
  constructor(tag, ownerDocument) {
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.attributes = new Map();
    this.childNodes = [];
    this.parentElement = null;
    this.classList = {
      add: (...names) => this.setClasses([...this.classes(), ...names]),
      contains: (name) => this.classes().includes(name),
    };
  }
  classes() {
    return (this.getAttribute("class") ?? "").split(/\s+/).filter(Boolean);
  }
  setClasses(names) {
    this.setAttribute("class", [...new Set(names)].join(" "));
  }
  get className() {
    return this.getAttribute("class") ?? "";
  }
  set className(value) {
    this.setAttribute("class", value);
  }
  get textContent() {
    return this.childNodes.map((node) => node.textContent).join("");
  }
  get children() {
    return this.childNodes.filter((node) => node.nodeType === 1);
  }
  get firstElementChild() {
    return this.children[0] ?? null;
  }
  get childElementCount() {
    return this.children.length;
  }
  // The markup the page sets as HTML: a loading spinner, an error box, or the
  // Diagnostics disclosure built from a string. It is kept as written, one element.
  set innerHTML(value) {
    const markup = new Element(/^<([a-z]+)/.exec(value)?.[1] ?? "div", this.ownerDocument);
    markup.markup = value;
    this.replaceChildren(markup);
  }
  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  detach(node) {
    const parent = node.parentElement;
    if (parent) {
      parent.childNodes = parent.childNodes.filter((child) => child !== node);
    }
    node.parentElement = this;
  }
  // A template's content is a fragment: placing it moves its children.
  expand(nodes) {
    return nodes.flatMap((node) => (node.fragment ? [...node.childNodes] : [node]));
  }
  append(...nodes) {
    for (const node of this.expand(nodes)) {
      this.detach(node);
      this.childNodes.push(node);
    }
  }
  prepend(...nodes) {
    const placed = this.expand(nodes);
    for (const node of placed) {
      this.detach(node);
    }
    this.childNodes.unshift(...placed);
  }
  replaceChildren(...nodes) {
    for (const child of this.childNodes) {
      child.parentElement = null;
    }
    this.childNodes = [];
    this.append(...nodes);
  }
  descendants() {
    return this.children.flatMap((node) => [node, ...node.descendants()]);
  }
  matches(selector) {
    return selector.split(",").some((one) => matchesCompound(this, one.trim()));
  }
  closest(selector) {
    for (let element = this; element; element = element.parentElement) {
      if (element.matches(selector)) {
        return element;
      }
    }
    return null;
  }
  querySelectorAll(selector) {
    const child = /^:scope\s*>\s*/.exec(selector);
    const pool = child ? this.children : this.descendants();
    const rest = child ? selector.slice(child[0].length) : selector;
    return pool.filter((element) => element.matches(rest));
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
}

function matchesCompound(element, selector) {
  const parts = selector.match(/^[a-z0-9]+|\.[\w-]+|\[[^\]]+\]/gi) ?? [];
  assert(parts.join("") === selector, `the session cannot match selector ${selector}`);
  return parts.every((part) => {
    if (part.startsWith(".")) {
      return element.classes().includes(part.slice(1));
    }
    if (part.startsWith("[")) {
      const [, name, value] = /^\[([\w-]+)(?:="((?:[^"\\]|\\.)*)")?\]$/.exec(part) ?? [];
      assert(name, `the session cannot match attribute ${part}`);
      const actual = element.getAttribute(name);
      return value === undefined ? actual !== null : actual === value.replace(/\\(.)/g, "$1");
    }
    return element.tagName.toLowerCase() === part.toLowerCase();
  });
}

// The parse of each render's HTML, as a browser's would build it: KPress's markup for a
// trusted render, and the inert HTML the server sends, in the tree shape
// tests/test_inert_html.py records (a tag, its attributes, and its children).
const parses = new Map();

function build(nodes, doc) {
  return nodes.map((node) => {
    if (typeof node === "string") {
      return doc.createTextNode(node);
    }
    const element = doc.createElement(node.tag);
    for (const [name, value] of node.attrs) {
      element.setAttribute(name, value);
    }
    element.append(...build(node.children, doc));
    return element;
  });
}

const pageDocument = {
  createElement(tag) {
    const element = new Element(tag, pageDocument);
    if (tag === "template") {
      Object.defineProperty(element, "innerHTML", {
        set(value) {
          assert(parses.has(value), "the session has a parse of every trusted render");
          const content = new Element("fragment", pageDocument);
          content.fragment = true;
          content.append(...build(parses.get(value), pageDocument));
          element.content = content;
        },
      });
    }
    return element;
  },
  createTextNode: (value) => new Text(String(value), pageDocument),
};
globalThis.document = pageDocument;

function templateNodes(nodes) {
  return nodes.map((node) =>
    typeof node === "string"
      ? { nodeType: 3, nodeValue: node }
      : {
          nodeType: 1,
          tagName: node.tag.toUpperCase(),
          getAttribute: (name) => node.attrs.find(([key]) => key === name)?.[1] ?? null,
          childNodes: templateNodes(node.children),
        },
  );
}

// The page's own parse of inert HTML is a real browser's; the allowlist after it is
// production code.
sandbox.window.MetabrowserInertHtml = Object.freeze({
  ...inert,
  sanitizeHtml: (html, base) => {
    assert(parses.has(html), "the session has a parse of every inert render");
    return inert.sanitizeNodes(templateNodes(parses.get(html)), pageDocument, base);
  },
});
globalThis.window = sandbox.window;

const tag = (name, attrs, ...children) => ({ tag: name, attrs, children });

// An invented note of the shape a reader reported, whose description holds a `: ` YAML
// reads as a second mapping. The server's diagnostic says what the reader sees, the
// sentence `FRONTMATTER_ERROR_MESSAGE` (metabrowser/frontmatter_yaml.py); the parser's
// reason is the answer's `frontmatter_error_detail`, for `metab --api` and not the page.
const note = [
  "---",
  'title: "Tide Tables for a Small Harbor"',
  "description: Tides: how the harbor office reads its tables",
  'as_of: "2026-03-02"',
  "status: draft",
  "bead: tide-k7m2",
  "---",
  "",
  "# Tide Tables",
  "",
  "The office posts the table by eight.",
  "",
].join("\n");
const reason = "The frontmatter could not be read.";
const detail =
  "Error parsing YAML metadata: mapping values are not allowed here\n" +
  '  in "<unicode string>", line 2, column 19:\n' +
  "    description: Tides: how the harbor office reads it ... \n" +
  "                      ^ (line: 2)";
const body = [tag("h1", [], "Tide Tables"), "\n", tag("p", [], "The office posts the table.")];
const otherDiagnostic = {
  type: "broken_anchor",
  message: "Link to #missing has no heading",
  severity: "warning",
};
const frontmatterError = { type: "frontmatter_error", message: reason, severity: "warning" };

// KPress's trusted document: its notice, then the layout and prose.
const trustedHtml = "trusted render";
parses.set(trustedHtml, [
  tag(
    "article",
    [["class", "kpress kpress-doc kpress-print-surface"]],
    tag(
      "aside",
      [
        ["class", "kpress-frontmatter-error"],
        ["role", "alert"],
        ["aria-label", "Frontmatter error"],
      ],
      tag("strong", [], "Frontmatter error"),
      tag("span", [], reason),
    ),
    tag(
      "div",
      [["class", "kpress-doc-layout kpress-content-with-toc"]],
      tag("div", [["class", "kpress-prose kpress-long-text"]], ...body),
    ),
  ),
]);
// The inert HTML the server sends: KPress's notice and classes gone, its wrappers kept.
const inertHtml = "inert render";
parses.set(inertHtml, [tag("div", [], tag("div", [], ...body))]);

const sent = [];
function mbAnswering(answer) {
  return {
    escapeHtml: (value) =>
      String(value).replace(/[&<>"]/g, (character) => `&#${character.charCodeAt(0)};`),
    errors: { isAbortError: (error) => error?.name === "AbortError" },
    ensureAsset: async () => undefined,
    fetchCompleteText: async () => note,
    fetchKpressRender: async (_ctx, _view, options) => {
      sent.push(options.sourceText);
      return answer;
    },
    kpressInitToc: () => () => {},
  };
}

// What the reader sees at the top of the document: the preamble's children, in order.
function preamble(container) {
  const meta = container.querySelector(".metabrowser-doc-meta");
  return {
    inProse: meta?.parentElement?.classList.contains("kpress-prose") ?? false,
    children: (meta?.children ?? []).map((child) => {
      if (child.classList.contains("kpress-frontmatter-error")) {
        return {
          notice: child.querySelector("strong")?.textContent,
          role: child.getAttribute("role"),
          reason: child.querySelector("span")?.textContent,
        };
      }
      const listed = [...(child.markup ?? "").matchAll(/<dt>(\w+)<\/dt><dd>([^<]*)<\/dd>/g)];
      return {
        disclosure: /<summary[^>]*>([^<]*)</.exec(child.markup ?? "")?.[1],
        listed: listed.filter(([, key]) => key === "type").map(([, , value]) => value),
      };
    }),
    notices: container.querySelectorAll(".kpress-frontmatter-error").length,
    detailShown: (meta?.children ?? []).some((child) =>
      `${child.textContent ?? ""}${child.markup ?? ""}`.includes("Error parsing YAML"),
    ),
  };
}

async function mount(answer) {
  const { mountRenderedMarkdown } = await import(
    pathToFileURL(path.join(markdownDir, "rendered.js")).href
  );
  const { preparePrimaryMarkdownSource } = await import(
    pathToFileURL(path.join(markdownDir, "wiki-parser.js")).href
  );
  // The production preprocessing, run in place of its Worker.
  const workerClient = {
    run: async (_op, payload) => preparePrimaryMarkdownSource(payload.source),
    dispose() {},
  };
  const container = pageDocument.createElement("div");
  const view = mountRenderedMarkdown(
    container,
    { raw: { content: note, content_truncated: false, type: "text" } },
    mbAnswering(answer),
    { workerClient },
  );
  await view.ready;
  const shown = preamble(container);
  view.dispose();
  return shown;
}

async function main() {
  const { placeRendered } = await import(
    pathToFileURL(path.join(markdownDir, "inert-render.js")).href
  );
  const valid = "sanitized metadata and authored disclosure";
  parses.set(valid, [
    tag("details", [], tag("summary", [], "Frontmatter"), tag("dl", [], tag("dt", [], "title"))),
    tag("div", [], tag("details", [], tag("summary", [], "Authored disclosure"))),
  ]);
  for (const identified of [true, false]) {
    const host = pageDocument.createElement("div");
    await placeRendered(
      host,
      { html: valid, inert: true, frontmatter_disclosure: identified },
      mbAnswering({}),
    );
    const article = host.querySelector("article");
    const chrome = article.querySelector(":scope > details.kpress-frontmatter");
    assert(
      Boolean(chrome) === identified,
      "only metadata identified by the server moves to the article preamble",
    );
    assert(
      article.querySelector(".kpress-prose").textContent.includes("Authored disclosure"),
      "authored disclosure stays in prose",
    );
    assert(article.querySelectorAll("details").length === 2, "neither disclosure is duplicated");
  }
  const transcript = {};

  transcript.trusted = await mount({
    html: trustedHtml,
    diagnostics: [frontmatterError, otherDiagnostic],
    frontmatter_error_detail: detail,
  });
  transcript.inert = await mount({
    html: inertHtml,
    inert: true,
    toc: false,
    diagnostics: [frontmatterError, otherDiagnostic],
    frontmatter_error_detail: detail,
  });
  transcript.inertOnlyFrontmatterError = await mount({
    html: inertHtml,
    inert: true,
    toc: false,
    diagnostics: [frontmatterError],
    frontmatter_error_detail: detail,
  });
  transcript.inertWithoutFrontmatterError = await mount({
    html: inertHtml,
    inert: true,
    toc: false,
    diagnostics: [otherDiagnostic],
  });

  const frontMatter = note.slice(0, note.indexOf("---\n", 4) + 4);
  transcript.sentText = {
    renders: sent.length,
    frontMatterAsWritten: sent.every((text) => text.startsWith(frontMatter)),
    headingAnchored: sent.every((text) =>
      text.includes('# <span class="metabrowser-wiki-heading" id="obsidian-heading-Tide Tables">'),
    ),
  };
  for (const name of ["trusted", "inert"]) {
    assert(transcript[name].notices === 1, `the ${name} document shows one notice`);
    assert(!transcript[name].detailShown, `the ${name} document leaves the parser's reason out`);
  }
  assert(transcript.sentText.frontMatterAsWritten, "the front matter is sent as written");
  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
