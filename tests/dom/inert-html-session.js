// Browserless session: untrusted Markdown through the production inert allowlist.
//
// static/inert-html.js loads whole, as the shell loads it on demand, and rebuilds the
// nodes of KPress's render of tests/fixtures/untrusted-markdown/README.md -- a document
// carrying every payload of the hostile corpus -- in both link modes: a document inside
// the served tree (null base), and a pull-request comment (its github.com page). The
// render's tree is Python's HTML parse of it, recorded in
// tests/fixtures/inert-html-kpress-tree.json by tests/test_inert_html.py, which fails when
// KPress renders it differently. builtin_plugins/markdown/inert-render.js decides from the
// server's answer which renders go through the allowlist. The real browser's parse, and
// that nothing loads, are checked in the QA runbook's walkthrough with a network watch.
//
// KPress removes a link whose scheme is not http(s) before the allowlist sees it, so the
// README cannot show what the allowlist itself does with one. The links of
// tests/fixtures/inert-html-hostile-links.json are handed to it directly, the same
// corpus tests/test_inert_html.py hands the server's side.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const tree = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/inert-html-kpress-tree.json"), "utf8"),
);
const hostileLinks = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/inert-html-hostile-links.json"), "utf8"),
);
const linkTree = Object.entries({ ...hostileLinks.refused, ...hostileLinks.kept }).map(
  ([name, href]) => ({ tag: "a", attrs: [["href", href]], children: [name] }),
);
// KPress (from jlevy/kpress#82) removes a raw `<link>` and any `<input>` that is not a
// checkbox before the allowlist sees them, so the README no longer shows what the allowlist
// itself does with one. The ones it carried are handed to it directly.
const kpressRemoved = [
  {
    tag: "link",
    attrs: [
      ["rel", "stylesheet"],
      ["href", "http://127.0.0.1:9/evil.css"],
    ],
    children: [],
  },
  { tag: "input", attrs: [["src", "https://e.x/i.png"]], children: [] },
];
// What the allowlist itself keeps of a checkbox, wherever a document writes one. KPress
// rewrites every checkbox it keeps in one canonical shape before the allowlist sees it, and
// the recorded tree has no room for a task list inside the review budget
// (devtools/check_goldens.py), so these are handed to it directly: KPress's own box in a
// task item, ticked and not, a checkbox in a table cell, one in mixed case with every
// attribute a form control can carry, and the inputs the allowlist drops whole.
const input = (...attrs) => ({ tag: "input", attrs, children: [] });
const kpressBox = (...state) =>
  input(
    ["class", "task-list-item-checkbox"],
    ...state,
    ["disabled", "disabled"],
    ["type", "checkbox"],
  );
const taskItem = (box, text) => ({
  tag: "li",
  attrs: [["class", "kpress-task task-list-item"]],
  children: [box, text],
});
const cell = (...children) => ({ tag: "td", attrs: [], children });
const boxTree = [
  {
    tag: "ul",
    attrs: [["class", "contains-task-list"]],
    children: [
      taskItem(kpressBox(), " open"),
      taskItem(kpressBox(["checked", "checked"]), " ticked"),
    ],
  },
  {
    tag: "table",
    attrs: [],
    children: [
      {
        tag: "tbody",
        attrs: [],
        children: [
          {
            tag: "tr",
            attrs: [],
            children: [cell("in a cell"), cell(input(["type", "checkbox"], ["checked", ""]))],
          },
        ],
      },
    ],
  },
  {
    tag: "p",
    attrs: [],
    children: [
      input(
        ["type", "CheckBox"],
        ["name", "agree"],
        ["form", "f"],
        ["value", "yes"],
        ["onclick", "alert(1)"],
        ["autofocus", ""],
        ["checked", ""],
      ),
      " mixed case,",
      input(["type", " checkbox"], ["checked", ""]),
      " padded,",
      input(["type", "text"], ["value", "typed"]),
      " text,",
      input(["type", "submit"]),
      " submit,",
      input(),
      " bare",
    ],
  },
];
// The fallback's span as the server's hardener writes it, and every other shape of one: the
// page keeps the class exactly and an address for the tooltip, and nothing else of a span.
const span = (attrs, text) => ({ tag: "span", attrs, children: [text] });
const FALLBACK = "mb-image-fallback";
// The badges of a README that the fixture's tree is too long to hold each of: an image in a
// link, over https and over http, one in no link in each, and one in a link to GitHub.
const badge = (src, alt, href) => {
  const image = {
    tag: "img",
    attrs: [
      ["src", src],
      ["alt", alt],
    ],
    children: [],
  };
  return href === undefined ? image : { tag: "a", attrs: [["href", href]], children: [image] };
};
const badgeTree = [
  badge("https://img.shields.io/badge/a-b", "Linked", "https://x.com/ojoshe"),
  " ",
  badge(
    "https://github.com/octo/demo/actions/workflows/ci.yml/badge.svg",
    "CI",
    "https://github.com/octo/demo/actions/workflows/ci.yml",
  ),
  " ",
  badge("http://example.com/insecure.png", "Linked over http", "https://example.com/dest"),
  " ",
  badge("https://img.shields.io/badge/c-d", "Standalone"),
  " ",
  badge("http://example.com/plain.png", "Plain over http"),
  " ",
  badge("https://img.shields.io/badge/e-f", "", "docs/guide.md"),
];
const chipTree = [
  span(
    [
      ["class", FALLBACK],
      ["data-tip-text", "https://example.com/a.png"],
    ],
    "valid",
  ),
  span([["class", FALLBACK]], "no address"),
  span(
    [
      ["class", FALLBACK],
      ["data-tip-text", "javascript:alert(1)"],
    ],
    "bad address",
  ),
  span(
    [
      ["class", FALLBACK],
      ["data-tip-text", "/api/tree"],
    ],
    "relative address",
  ),
  span(
    [
      ["class", `modal-overlay ${FALLBACK}`],
      ["data-tip-text", "https://example.com/b"],
    ],
    "other class",
  ),
  span(
    [
      ["class", FALLBACK],
      ["style", "position:fixed"],
      ["onclick", "alert(1)"],
      ["id", "x"],
      ["title", "t"],
    ],
    "extras",
  ),
  span(
    [
      ["data-tip-text", "https://example.com/c"],
      ["data-nav-dir", "up"],
    ],
    "no class",
  ),
];
const inertPath = path.join(repoRoot, "src/metabrowser/static/inert-html.js");
const context = { window: {}, URL };
vm.runInNewContext(fs.readFileSync(inertPath, "utf8"), context, { filename: inertPath });
const inert = context.window.MetabrowserInertHtml;

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

// The template the page parses a render into, as plain objects from the recorded tree.
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

// What sanitizeNodes builds: new elements and text, serialized as a browser would.
const pageDocument = {
  createTextNode: (value) => ({ text: String(value) }),
  createElement: (tag) => ({
    tag,
    attributes: [],
    children: [],
    setAttribute(name, value) {
      this.attributes.push([name, String(value)]);
    },
    append(...nodes) {
      this.children.push(...nodes);
    },
  }),
};

// What kpressProse builds from what sanitizeNodes built: enough of a DOM to walk its tree.
function proseElement(tag) {
  const element = {
    nodeType: 1,
    tagName: tag.toUpperCase(),
    className: "",
    attributes: [],
    childNodes: [],
    parentElement: null,
    setAttribute(name, value) {
      element.attributes.push({ name, value: String(value) });
    },
    append(...nodes) {
      for (const node of nodes) {
        node.parentElement = element;
        element.childNodes.push(node);
      }
    },
    querySelectorAll(name) {
      const found = [];
      const walk = (parent) => {
        for (const child of parent.childNodes) {
          if (child.nodeType === 1) {
            if (child.tagName === name.toUpperCase()) {
              found.push(child);
            }
            walk(child);
          }
        }
      };
      walk(element);
      return found;
    },
  };
  return element;
}

function proseTree(element) {
  if (element.nodeType !== 1) {
    return element.textContent;
  }
  const label = element.className
    ? `${element.tagName.toLowerCase()}.${element.className}`
    : element.tagName.toLowerCase();
  const attributes = element.attributes.map(({ name, value }) => `[${name}=${value}]`).join("");
  return { [`${label}${attributes}`]: element.childNodes.map(proseTree) };
}

function renderShaped(tag, ...children) {
  const element = proseElement(tag);
  element.append(...children);
  return element;
}

// A document's own `<div align>`, the one attribute a kept `<div>` can carry.
function aligned(element, align) {
  element.setAttribute("align", align);
  return element;
}

function escapeText(value) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function serialize(nodes, inLink = false) {
  return nodes
    .map((node) => {
      if ("text" in node) {
        return escapeText(node.text);
      }
      // A link never holds another: a browser reads that as the first's end.
      assert(!(inLink && node.tag === "a"), "the page kept a link inside a link");
      const allowed =
        inert.ALLOWED_TAGS.includes(node.tag) || node.tag === "img" || node.tag === "input";
      assert(allowed, `the page kept <${node.tag}>`);
      // An input is only ever a disabled checkbox, ticked or not.
      assert(
        node.tag !== "input" ||
          JSON.stringify(node.attributes.filter(([name]) => name !== "checked")) ===
            JSON.stringify(inert.CHECKBOX_ATTRIBUTES),
        `the page kept an input with ${JSON.stringify(node.attributes)}`,
      );
      for (const [name] of node.attributes) {
        const names = inert.ALLOWED_ATTRIBUTES[node.tag] ?? [];
        assert(names.includes(name), `the page kept ${node.tag}[${name}]`);
      }
      const id = node.attributes.find(([name]) => name === "id")?.[1];
      assert(id === undefined || id.startsWith(inert.ANCHOR_PREFIX), `the page kept id=${id}`);
      const loading = node.attributes.find(([name]) => name === "loading")?.[1];
      assert(
        node.tag !== "img" || loading === "lazy",
        `the page kept an image, loading=${loading}`,
      );
      // An image from the web is fetched over https with no referrer; an image of the
      // document's own is in its tree.
      const source = node.attributes.find(([name]) => name === "src")?.[1] ?? "";
      const referrer = node.attributes.find(([name]) => name === "referrerpolicy")?.[1];
      const fromTheWeb = source.startsWith("https://");
      assert(
        node.tag !== "img" ||
          (fromTheWeb
            ? referrer === "no-referrer"
            : referrer === undefined && !/^[a-z][a-z0-9+.-]*:|^\/\//i.test(source)),
        `the page kept an image from ${source}, referrerpolicy=${referrer}`,
      );
      const tip = node.attributes.find(([name]) => name === "data-tip-text")?.[1];
      assert(
        node.tag !== "span" ||
          node.attributes.length === 0 ||
          (node.attributes[0][1] === inert.IMAGE_FALLBACK_CLASS &&
            (tip === undefined || /^https?:\/\//.test(tip))),
        `the page kept a span with ${JSON.stringify(node.attributes)}`,
      );
      const attributes = node.attributes
        .map(([name, value]) =>
          ["open", "disabled", "checked"].includes(name)
            ? ` ${name}`
            : ` ${name}="${escapeText(value).replaceAll('"', "&quot;")}"`,
        )
        .join("");
      return ["br", "hr", "img", "input"].includes(node.tag)
        ? `<${node.tag}${attributes}>`
        : `<${node.tag}${attributes}>${serialize(node.children, inLink || node.tag === "a")}</${node.tag}>`;
    })
    .join("");
}

async function main() {
  const render = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/inert-render.js"))
      .href
  );
  const pullRequest = "https://github.com/octo/demo/pull/7";
  const rebuilt = (nodes, base) =>
    serialize(inert.sanitizeNodes(templateNodes(nodes), pageDocument, base));
  const documentMode = rebuilt(tree, null);
  const commentMode = rebuilt(tree, pullRequest);
  // The reader has turned off the images of the web: the shell's settings say so. Read
  // each time the page sanitizes, so it is a change of what the page carries and no more.
  context.window.METABROWSER_SETTINGS = { BLOCK_REMOTE_IMAGES: true };
  const blockedDocument = rebuilt(tree, null);
  const blockedComment = rebuilt(tree, pullRequest);
  const blockedBadges = rebuilt(badgeTree, null);
  context.window.METABROWSER_SETTINGS = { BLOCK_REMOTE_IMAGES: false };
  assert(rebuilt(tree, null) === documentMode, "an off setting changed the document");
  delete context.window.METABROWSER_SETTINGS;
  assert(rebuilt(tree, pullRequest) === commentMode, "no setting changed the comment");
  assert(!blockedDocument.includes("referrerpolicy"), "a blocked image loaded in a document");
  assert(!blockedComment.includes("referrerpolicy"), "a blocked image loaded in a comment");
  console.log(
    JSON.stringify(
      {
        inertRender: {
          inert: render.isInertRender({ html: "", inert: true }),
          trusted: render.isInertRender({ html: "" }),
        },
        document: documentMode,
        comment: commentMode,
        // The same with the reader's setting on: every image from the web is its fallback, in
        // the link it was in or in a link to the image; the document's own image still loads.
        blocked: { document: blockedDocument, comment: blockedComment },
        // A row of badges: in the link they were in, or in a link to the image, whatever loads.
        badges: {
          document: rebuilt(badgeTree, null),
          comment: rebuilt(badgeTree, pullRequest),
          blocked: blockedBadges,
        },
        // What the page keeps of a span the server did not write as the fallback.
        fallbacks: rebuilt(chipTree, null),
        // A render arrives in KPress's two wrappers, classes gone. The blocks become the prose
        // element's children, and a code block and a table get back the classes KPress's
        // stylesheets hang their type on, from the module and never from the document.
        prose: proseTree(
          inert.kpressProse(
            [
              { nodeType: 3, textContent: "\n" },
              renderShaped(
                "div",
                renderShaped(
                  "div",
                  renderShaped("h1"),
                  renderShaped("pre", renderShaped("code")),
                  renderShaped("div", renderShaped("table")),
                ),
              ),
            ],
            { createElement: proseElement },
          ),
        ),
        // A document whose one block is its own `<div align>`, here inside one wrapper: the
        // unwrapping stops at a `<div>` with an attribute, which is the document's and keeps
        // its align.
        alignedProse: proseTree(
          inert.kpressProse(
            [renderShaped("div", aligned(renderShaped("div", renderShaped("h1")), "center"))],
            { createElement: proseElement },
          ),
        ),
        links: { document: rebuilt(linkTree, null), comment: rebuilt(linkTree, pullRequest) },
        kpressRemoved: rebuilt(kpressRemoved, null),
        // Each checkbox as a disabled box, ticked as written, and no other input.
        boxes: rebuilt(boxTree, null),
      },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
