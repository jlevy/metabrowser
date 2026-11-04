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
    childNodes: [],
    parentElement: null,
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
  return element.nodeType === 1
    ? {
        [element.className
          ? `${element.tagName.toLowerCase()}.${element.className}`
          : element.tagName.toLowerCase()]: element.childNodes.map(proseTree),
      }
    : element.textContent;
}

function renderShaped(tag, ...children) {
  const element = proseElement(tag);
  element.append(...children);
  return element;
}

function escapeText(value) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function serialize(nodes) {
  return nodes
    .map((node) => {
      if ("text" in node) {
        return escapeText(node.text);
      }
      const allowed = inert.ALLOWED_TAGS.includes(node.tag) || node.tag === "img";
      assert(allowed, `the page kept <${node.tag}>`);
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
      const attributes = node.attributes
        .map(([name, value]) =>
          name === "open" ? " open" : ` ${name}="${escapeText(value).replaceAll('"', "&quot;")}"`,
        )
        .join("");
      return ["br", "hr", "img"].includes(node.tag)
        ? `<${node.tag}${attributes}>`
        : `<${node.tag}${attributes}>${serialize(node.children)}</${node.tag}>`;
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
  console.log(
    JSON.stringify(
      {
        inertRender: {
          inert: render.isInertRender({ html: "", inert: true }),
          trusted: render.isInertRender({ html: "" }),
        },
        document: documentMode,
        comment: commentMode,
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
        links: { document: rebuilt(linkTree, null), comment: rebuilt(linkTree, pullRequest) },
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
