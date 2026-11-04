const assert = require("node:assert/strict");
const { createSdkSandbox } = require("./sdk-sandbox.js");

// The real view helper owns its icon node. This DOM keeps authored nodes separate.
class Element {
  constructor(tag, document) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = document;
    this.nodeType = 1;
    this.attributes = new Map();
    this.children = [];
    this.parentNode = null;
    this.className = "";
    this.innerHTML = "";
    this.dataset = {};
  }
  get childNodes() {
    return this.children;
  }
  setAttribute(key, value) {
    this.attributes.set(key, String(value));
  }
  getAttribute(key) {
    return this.attributes.get(key) ?? null;
  }
  append(...nodes) {
    for (const node of nodes) {
      node.remove?.();
      if (typeof node === "object") {
        node.parentNode = this;
      }
      this.children.push(node);
    }
  }
  replaceChildren(...nodes) {
    for (const node of this.children) {
      if (typeof node === "object") {
        node.parentNode = null;
      }
    }
    this.children = [];
    this.append(...nodes);
  }
  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((node) => node !== this);
    }
    this.parentNode = null;
  }
}
const document = {
  createElement: (tag) => new Element(tag, document),
  createTextNode: (text) => ({ nodeType: 3, nodeValue: text }),
};
const sandbox = createSdkSandbox();
sandbox.document = document;
let providerCalls = 0;
sandbox.fetch = globalThis.fetch = () => {
  providerCalls += 1;
  throw new Error("Decoration must not fetch");
};
const decorate = sandbox.metabrowser.decorateExternalLink;
assert.equal(typeof decorate, "function", "view-phase external-link helper exists");
const report = [];
for (const [href, expected] of [
  ["https://github.com/octo/demo", "github"],
  ["https://github.com/octo", "github"],
  ["//github.com/octo/demo/pull/7", "pull"],
  ["https://github.com/octo/demo/PULL/7", "github"],
  ["https://www.github.com/octo/demo", "github"],
  ["https://cli.github.com/", "github"],
  ["https://docs.github.com/en", "github"],
  ["https://gist.github.com/octo/abcd", "github"],
  ["https://api.github.com/repos/octo/demo", "github"],
  ["https://github.com/octo/demo/issues/7#comment", "issue"],
  ["https://github.com/octo/demo/pull/7/files?x=1#L2", "pull"],
  ["https://github.com/octo/demo/issues/0", "github"],
  ["https://github.com/octo/demo/pull/no", "github"],
  ["https://github.com/octo/demo/pull/7evil", "github"],
  ["https://github.com/octo/demo/pull/%37", "github"],
  ["https://example.com/check/7", null],
  ["https://github.com.example.com/octo/demo/pull/7", null],
  ["https://octo.github.io/", null],
  ["https://github.com@evil.example/", null],
  ["https://name@github.com/", null],
  ["https://github.com:444/", null],
  ["javascript:alert(1)", null],
  ["/pull/7", null],
  ["/view/docs/readme.md", null],
]) {
  const link = document.createElement("a");
  link.setAttribute("href", href);
  link.setAttribute("target", "_blank");
  link.setAttribute("rel", "noopener noreferrer");
  link.setAttribute("aria-label", "Authored name");
  const text = { text: "Authored text" };
  const image = document.createElement("img");
  link.append(text, image);
  assert.equal(decorate(link), link);
  const icon = link.children[2];
  assert.equal(icon?.getAttribute("data-external-kind") ?? null, expected);
  assert.equal(icon?.getAttribute("aria-hidden") ?? null, expected === null ? null : "true");
  decorate(link);
  assert.equal(link.children.length, expected === null ? 2 : 3);
  assert.equal(link.children[0], text);
  assert.equal(link.children[1], image);
  assert.equal(link.getAttribute("href"), href);
  assert.equal(link.getAttribute("aria-label"), "Authored name");
  assert.equal(link.getAttribute("target"), "_blank");
  assert.equal(link.getAttribute("rel"), "noopener noreferrer");
  if (expected !== null) {
    assert.equal(link.children[2], icon);
    assert.match(icon.innerHTML, /<svg/);
  }
  report.push({ href, icon: expected });
}
const link = document.createElement("a");
link.setAttribute("href", "https://github.com/octo/demo/pull/7");
const authored = document.createElement("span");
authored.setAttribute("data-external-kind", "forged");
link.append(authored);
decorate(link);
const owned = link.children[1];
const known = document.createElement("span");
known.setAttribute("data-state", "merged");
decorate(link, { icon: known });
assert.equal(link.children[1], owned);
assert.equal(owned.children[0], known);
link.setAttribute("href", "/pull/7");
decorate(link);
assert.deepEqual(link.children, [authored]);
link.setAttribute("href", "https://github.com/octo/demo/issues/8");
decorate(link);
assert.equal(link.children[1].getAttribute("data-external-kind"), "issue");
const summary = {
  destinations: report,
  preserved: ["href", "target", "rel", "accessible name", "authored nodes"],
  updates: [
    "idempotent node",
    "trusted supplied state",
    "internal href removes owned icon",
    "authored forged marker retained without trust",
    "new destination reclassified",
  ],
  providerCalls: 0,
};

(async () => {
  const vm = require("node:vm");
  const fs = require("node:fs");
  const path = require("node:path");
  const { pathToFileURL } = require("node:url");
  const root = path.resolve(__dirname, "../..");
  vm.runInContext(
    fs.readFileSync(path.join(root, "src/metabrowser/static/inert-html.js"), "utf8"),
    sandbox,
  );
  globalThis.document = document;
  globalThis.DOMParser = class {
    parseFromString() {
      return { body: { firstElementChild: null } };
    }
  };
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js"))
  );
  const pull = { htmlUrl: "https://github.com/octo/demo/pull/7", state: "merged" };
  const links = [];
  for (const href of [
    `${pull.htmlUrl}#issuecomment-1`,
    "https://github.com/octo/demo/pull/7/files",
    "https://github.com/other/demo/pull/7",
    "https://github.com/octo/demo/pull/8",
    "https://github.com/octo/demo/issues/7",
    "https://ci.example/check/7",
  ]) {
    const authored = document.createElement("a");
    authored.setAttribute("href", href);
    authored.setAttribute("data-state", "merged");
    authored.setAttribute("data-external-kind", "forged");
    const forgedSvg = document.createElement("svg");
    authored.append(document.createTextNode("Authored"), forgedSvg);
    const [clean] = sandbox.MetabrowserInertHtml.sanitizeNodes([authored], document, pull.htmlUrl);
    assert.equal(clean.getAttribute("data-state"), null);
    assert.equal(clean.getAttribute("data-external-kind"), null);
    assert.ok(!clean.children.some((node) => node.tagName === "SVG"));
    page.decoratePullLink(clean, pull, sandbox.metabrowser);
    const mark = clean.children[1];
    const state = mark?.children[0]?.dataset?.state ?? null;
    const exact = page.samePullDestination(href, pull.htmlUrl);
    assert.equal(state, exact ? "merged" : null);
    assert.equal(clean.children[0].nodeValue, "Authored");
    assert.equal(clean.getAttribute("target"), "_blank");
    assert.equal(clean.getAttribute("rel"), "noopener noreferrer");
    links.push({ href, icon: mark?.getAttribute("data-external-kind") ?? null, state });
  }
  for (const state of ["open", "draft", "closed", "merged"]) {
    const link = document.createElement("a");
    link.setAttribute("href", pull.htmlUrl);
    page.decoratePullLink(link, { ...pull, state }, sandbox.metabrowser);
    assert.equal(link.children[0].children[0].dataset.state, state);
  }
  summary.sanitizedConversation = links;
  summary.knownStates = ["open", "draft", "closed", "merged"];
  assert.equal(providerCalls, 0);
  summary.providerCalls = providerCalls;
  console.log(JSON.stringify(summary, null, 2));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
