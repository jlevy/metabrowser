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

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const tree = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/inert-html-kpress-tree.json"), "utf8"),
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
  const documentMode = serialize(inert.sanitizeNodes(templateNodes(tree), pageDocument, null));
  const commentMode = serialize(
    inert.sanitizeNodes(templateNodes(tree), pageDocument, "https://github.com/octo/demo/pull/7"),
  );
  console.log(
    JSON.stringify(
      {
        inertRender: {
          inert: render.isInertRender({ html: "", inert: true }),
          trusted: render.isInertRender({ html: "" }),
        },
        document: documentMode,
        comment: commentMode,
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
