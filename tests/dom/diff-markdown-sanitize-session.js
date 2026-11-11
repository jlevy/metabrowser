// Browserless session: rendered Markdown diff blocks through the page's own defense.
//
// tests/test_diff_browser_js.py projects hostile Markdown with the production server
// code, records Python's HTML parse of every block, and adds blocks written by hand that
// the server would never send. Each runs through the production sanitizeBlock of
// builtin_plugins/diff/diff-markdown.js and static/inert-html.js, loaded whole: the
// template the page parses a block into is built from the recorded parse, so the swap of
// snapshot targets, the shared allowlist and the restore all run as the page runs them.
//
// argv: <repo root> <cases.json>: {route, cases}, the comparison's snapshot route and a
// list of {name, html, tree, expect}.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

const repoRoot = process.argv[2];
const { route, cases } = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const ORIGIN = "http://127.0.0.1:8123";
globalThis.window = { location: { origin: ORIGIN } };
const inertPath = path.join(repoRoot, "src/metabrowser/static/inert-html.js");
const context = { window: {}, URL };
vm.runInNewContext(fs.readFileSync(inertPath, "utf8"), context, { filename: inertPath });
const inert = context.window.MetabrowserInertHtml;

/** Elements answer the two selectors the code asks of them. */
function select(root, selector) {
  const found = [];
  const walk = (parent) => {
    for (const child of parent.childNodes) {
      if (child.nodeType !== 1) {
        continue;
      }
      const tag = child.tagName;
      const wanted =
        selector === "a[href], img[src]"
          ? (tag === "A" && child.getAttribute("href") !== null) ||
            (tag === "IMG" && child.getAttribute("src") !== null)
          : tag === selector.toUpperCase();
      if (wanted) {
        found.push(child);
      }
      walk(child);
    }
  };
  walk(root);
  return found;
}

function element(tag, attrs = []) {
  const attributes = new Map(attrs);
  const node = {
    nodeType: 1,
    tagName: tag.toUpperCase(),
    className: "",
    childNodes: [],
    parentElement: null,
    getAttribute: (name) => (attributes.has(name) ? attributes.get(name) : null),
    setAttribute(name, value) {
      attributes.set(name, String(value));
    },
    removeAttribute(name) {
      attributes.delete(name);
    },
    attributes,
    append(...nodes) {
      for (const child of nodes) {
        child.parentElement = node;
        node.childNodes.push(child);
      }
    },
    querySelectorAll: (selector) => select(node, selector),
  };
  return node;
}

function parsed(nodes) {
  return nodes.map((node) => {
    if (typeof node === "string") {
      return { nodeType: 3, nodeValue: node, textContent: node };
    }
    const built = element(node.tag, node.attrs);
    built.append(...parsed(node.children));
    return built;
  });
}

const trees = new Map(cases.map(({ html, tree }) => [html, tree]));
const template = {
  set innerHTML(html) {
    assert.ok(trees.has(html), `no recorded parse for ${html}`);
    const content = element("#fragment");
    content.append(...parsed(trees.get(html)));
    this.content = content;
  },
};
const scratch = {
  createElement: (tag) => element(tag),
  createTextNode: (value) => ({ nodeType: 3, textContent: String(value) }),
};

function serialize(nodes) {
  return nodes
    .map((node) => {
      if (node.nodeType === 3) {
        return node.textContent.replaceAll("&", "&amp;").replaceAll("<", "&lt;");
      }
      const tag = node.tagName.toLowerCase();
      assert.ok(inert.ALLOWED_TAGS.includes(tag) || tag === "img", `kept <${tag}>`);
      const names = inert.ALLOWED_ATTRIBUTES[tag] ?? [];
      for (const name of node.attributes.keys()) {
        assert.ok(names.includes(name), `kept ${tag}[${name}]`);
      }
      const attributes = [...node.attributes]
        .map(([name, value]) => ` ${name}="${value.replaceAll('"', "&quot;")}"`)
        .join("");
      return ["br", "hr", "img"].includes(tag)
        ? `<${tag}${attributes}>`
        : `<${tag}${attributes}>${serialize(node.childNodes)}</${tag}>`;
    })
    .join("");
}

async function main() {
  const { snapshotTargets, sanitizeBlock } = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-markdown.js")).href
  );
  const isSnapshotTarget = snapshotTargets(route);
  let checked = 0;
  for (const { name, html, expect } of cases) {
    const prose = sanitizeBlock(html, inert, template, scratch, isSnapshotTarget);
    assert.equal(prose.className, "kpress-prose", name);
    const shown = serialize(prose.childNodes);
    for (const link of select(prose, "a[href], img[src]")) {
      const image = link.tagName === "IMG";
      const value = link.getAttribute(image ? "src" : "href");
      assert.ok(
        isSnapshotTarget(value, image) ||
          (!image && value.startsWith(`#${inert.ANCHOR_PREFIX}`)) ||
          (!image && /^https?:\/\//i.test(value) && !value.startsWith(ORIGIN)),
        `${name}: kept ${value}`,
      );
      assert.ok(!value.startsWith("mb-snapshot-target-"), `${name}: a marker was not restored`);
    }
    for (const part of expect.contains ?? []) {
      assert.ok(shown.includes(part), `${name}: ${shown} lacks ${part}`);
    }
    for (const part of expect.lacks ?? []) {
      assert.ok(!shown.includes(part), `${name}: ${shown} has ${part}`);
    }
    checked += 1;
  }
  assert.equal(checked, cases.length);
  console.log(`diff Markdown sanitize OK (${checked} blocks)`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
