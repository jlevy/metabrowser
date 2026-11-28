// The file envelope owns the metadata, and the article owns only its disclosure.
// Drive the same adapter and node table for a trusted and a sanitized article.
const assert = require("node:assert/strict");
const { FakeElement } = require("./pulls-test-dom.js");

const { createSdkSandbox } = require("./sdk-sandbox.js");

const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...args) => {
  if (!String(warning).includes("is not specified and it doesn't parse as CommonJS")) {
    emitWarning.call(process, warning, ...args);
  }
};

class Element extends FakeElement {
  open = false;
  get parentElement() {
    return this.parentNode;
  }
  querySelectorAll(selector) {
    assert.equal(selector, "pre > code > a[href]");
    const links = [];
    function visit(node) {
      if (
        node.localName === "a" &&
        node.getAttribute("href") &&
        node.parentElement?.localName === "code" &&
        node.parentElement.parentElement?.localName === "pre"
      ) {
        links.push(node);
      }
      for (const child of node.childNodes ?? []) {
        visit(child);
      }
    }
    visit(this);
    return links;
  }
  querySelector(selector) {
    if (selector.startsWith(":scope > ")) {
      const [name, classes] = selector.slice(9).split(".");
      return (
        this.childNodes.find(
          (child) =>
            (!name || child.localName === name) &&
            (!classes || child.classList?.contains(classes.split(":")[0])),
        ) ?? null
      );
    }
    return this.find((node) => node.classList?.contains(selector.slice(1)));
  }
  find(match) {
    if (match(this)) {
      return this;
    }
    return this.childNodes.map((node) => node.find?.(match)).find(Boolean);
  }
  prepend(node) {
    this.insertBefore(node, this.firstChild);
  }
  removeEventListener(name) {
    this.listeners.delete(name);
  }
}

async function testFences(doc, mount, mountNodeTable, pageReader) {
  const { attachFencedViews } = await import(
    "../../src/metabrowser/builtin_plugins/markdown/fenced-views.js"
  );
  const host = doc.createElement("div");
  function code(id) {
    const pre = doc.createElement("pre");
    const text = doc.createElement("code");
    const marker = doc.createElement("a");
    marker.setAttribute("href", `#${id}`);
    text.append("Readable code", marker);
    pre.append(text);
    host.append(pre);
    return pre;
  }
  const yaml = code("yaml-marker");
  const json = code("json-marker");
  code("duplicate");
  code("duplicate");
  const lifetime = new AbortController();
  const reads = [];
  const modes = new Map();
  const filterControls = createSdkSandbox().metabrowser.filterControls;
  const mb = {
    filterControls: {
      groupHtml: filterControls.groupHtml,
      keepFocus: () => () => {},
      bind(controls, { onChange }) {
        modes.set(controls, onChange);
        return () => modes.delete(controls);
      },
    },
    mountStructuredNodeTable: async (...args) => mountNodeTable(...args),
    async mountStructuredExcerpt(element, options) {
      return mount(element, this, options);
    },
    async createStructuredPageReader(path, options) {
      return pageReader(this.fetchPluginData, path, options);
    },
    async fetchPluginData(_plugin, _hook, params) {
      const { fence_line: line, path, mtime_hash: revision } = params;
      assert.equal(path, "@pin:doc.md");
      assert.equal(revision, "exact");
      reads.push([line, params.source ? "Source" : params.tree ? "Tree" : "Table"]);
      if (params.source) {
        return { status: "ready", source_text: '\r\n{"key": null}\r\n', source_start_line: 12 };
      }
      if (params.tree) {
        return { status: "ready", tree_value: { key: null } };
      }
      return { status: "ready", node: { kind: "string", child_count: 0, value: "sample" } };
    },
    async loadStructuredTree() {
      return {
        renderInlineTree(el, value) {
          assert.deepEqual(value, { key: null });
          el.textContent = "Tree";
          return {};
        },
      };
    },
    renderSourceView(el, { content, ext }, { lineStart }) {
      assert.equal(ext, ".json");
      assert.equal(lineStart, 1);
      el.textContent = content;
    },
  };
  attachFencedViews(
    host,
    "@pin:doc.md",
    "exact",
    [
      { id: "yaml-marker", opening_line: 4, format: "yaml" },
      { id: "json-marker", opening_line: 11, format: "json" },
      { id: "duplicate", opening_line: 19, format: "yaml" },
    ],
    mb,
    lifetime.signal,
  );
  const disclosures = host.childNodes.filter((node) => node.localName === "details");
  assert.equal(disclosures.length, 2);
  assert.equal(yaml.hidden, false);
  assert.equal(json.hidden, false);
  assert.equal(reads.length, 0);
  const turn = () => new Promise(setImmediate);
  for (const disclosure of disclosures) {
    disclosure.open = true;
    disclosure.listeners.get("toggle")();
    await turn();
  }
  assert.equal(yaml.hidden, true);
  assert.equal(json.hidden, true);
  const [yamlViews, jsonViews] = disclosures.map((node) => node.lastChild);
  const switchJson = modes.get(jsonViews.firstChild);
  switchJson("structured-excerpt-view", "Tree");
  await turn();
  assert.equal(jsonViews.lastChild.textContent, "Tree");
  switchJson("structured-excerpt-view", "Source");
  await turn();
  assert.ok(yamlViews.textContent.includes("sample"));
  assert.equal(jsonViews.lastChild.textContent, '\r\n{"key": null}\r\n');
  const result = { reads, source: jsonViews.lastChild.textContent };
  lifetime.abort();
  assert.equal(modes.size, 0);
  assert.equal(yaml.hidden, false);
  assert.equal(json.hidden, false);
  return result;
}

async function testSourceRecovery(doc, mount, nodeTable, pageReader) {
  const turn = () => new Promise(setImmediate);
  const destinations = [];
  const path = "@pin:notes/data.yaml";
  const views = new Map();
  const calls = [];
  let response;
  const mb = {
    filterControls: { groupHtml: () => "", keepFocus: () => () => {}, bind: () => () => {} },
    navigation: { open: (target, options) => destinations.push([target, options]) },
    loadStructuredTree: async () => ({}),
    registerView: (_kind, view, shape) => views.set(view, shape),
    createStructuredPageReader: (identity, options) =>
      pageReader(
        async (_plugin, _hook, query) => {
          assert.equal(query.path, identity);
          calls.push(query.source ? "Source" : "Values");
          if (response instanceof Error) {
            throw response;
          }
          return response;
        },
        identity,
        options,
      ),
    mountStructuredNodeTable: nodeTable,
    renderSourceView(el, { content }) {
      el.textContent = content;
    },
  };
  global.window = { metabrowser: mb };
  await import("../../src/metabrowser/builtin_plugins/structured/index.js");
  const host = doc.createElement("div");
  function action(label) {
    const button = host.find((el) => el.localName === "button" && el.textContent === label);
    assert.ok(button, label);
    button.listeners.get("click")();
  }
  for (const [failure, message] of [
    [{ status: "too_large" }, "exceeds the Values view’s parsing limit"],
    [{ status: "invalid", diagnostic: "Duplicate mapping key" }, "Duplicate mapping key"],
    [{ status: "missing" }, "selected value is unavailable"],
    [Object.assign(new Error(), { status: 409 }), "file changed"],
    [new Error(), "Values view could not be loaded"],
  ]) {
    response = failure;
    const mounted = await views.get("table").render(host, { path });
    await mounted.ready;
    assert.ok(host.textContent.includes(message), host.textContent);
    action("Open Source");
    assert.deepEqual(destinations.pop(), [{ path }, { viewId: "source" }]);
    mounted.dispose();
  }
  const embeddedPath = "@pin:article.md";
  let selected;
  const branch = nodeTable(
    host,
    async (position) =>
      position.path.length
        ? { status: "missing" }
        : {
            status: "ready",
            node: { kind: "object", child_count: 1 },
            children: [{ segment: "people", node: { kind: "array", child_count: 2 } }],
          },
    {
      openSource: (position) => {
        selected = position;
      },
    },
  );
  await branch.ready;
  host
    .find((element) => element.getAttribute?.("aria-expanded") === "false")
    .listeners.get("click")();
  await turn();
  action("Open Source");
  assert.deepEqual(selected, { document: 0, path: ["people"], offset: 0 });
  branch.dispose();
  const options = {
    label: "Frontmatter",
    ext: ".yaml",
    path: embeddedPath,
    pages: () =>
      mb.createStructuredPageReader(embeddedPath, { revision: "exact", frontmatter: true }),
  };
  for (const available of [true, false]) {
    calls.length = 0;
    response = { status: "too_large" };
    const mounted = mount(host, mb, options);
    await turn();
    assert.deepEqual(calls, ["Values"]);
    response = available ? { status: "invalid", source_text: "key: [\r\n" } : { status: "missing" };
    action("Open Source");
    await turn();
    assert.deepEqual(calls, ["Values", "Source"]);
    if (available) {
      assert.equal(host.lastChild.textContent, "key: [\r\n");
      assert.equal(destinations.length, 0);
    } else {
      action("Open file in Source");
      assert.deepEqual(destinations.pop(), [{ path: embeddedPath }, { viewId: "source" }]);
    }
    mounted.dispose();
  }
  const failed = mount(host, mb, { ...options, pages: () => Promise.reject(new Error()) });
  await turn();
  action("Open file in Source");
  assert.deepEqual(destinations.pop(), [{ path: embeddedPath }, { viewId: "source" }]);
  failed.dispose();
  const { attachStructuredDisclosure } = await import(
    "../../src/metabrowser/builtin_plugins/markdown/structured-disclosure.js"
  );
  const details = doc.createElement("details");
  host.replaceChildren(details);
  details.append(doc.createElement("summary"));
  details.open = true;
  const lifetime = new AbortController();
  const logged = require("node:test").mock.method(console, "error", () => {});
  try {
    attachStructuredDisclosure(
      details,
      {
        ...mb,
        mountStructuredExcerpt: async () => {
          throw new Error("UI unavailable");
        },
      },
      options,
      lifetime.signal,
    );
    await turn();
    assert.equal(logged.mock.callCount(), 1);
  } finally {
    logged.mock.restore();
  }
  action("Open file in Source");
  assert.deepEqual(destinations.pop(), [{ path: embeddedPath }, { viewId: "source" }]);
  lifetime.abort();
  return { standalone: path, excerpt: "Source", unavailableExcerpt: embeddedPath };
}

async function main() {
  const { attachFrontmatter } = await import(
    "../../src/metabrowser/builtin_plugins/markdown/frontmatter-view.js"
  );
  const { mountNodeTable } = await import("../../src/metabrowser/static/structured-node-table.js");
  const { mountStructuredExcerpt } = await import(
    "../../src/metabrowser/static/structured-excerpt.js"
  );
  const { createStructuredPageReader } = await import(
    "../../src/metabrowser/static/structured-page-reader.js"
  );
  let clipboard;
  const doc = {
    createElement: (tag) => new Element(tag),
    createComment: () => new Element("#comment"),
    defaultView: {
      navigator: {
        clipboard: {
          async writeText(text) {
            clipboard = text;
          },
        },
      },
      metabrowser: {
        icons: {},
        ownDelegate() {},
        showCopyResult(_button, writing) {
          void writing;
        },
      },
    },
  };
  global.document = doc;
  const summaryText = [];
  for (const inert of [false, true]) {
    const host = doc.createElement("div");
    const article = doc.createElement("article");
    article.className = inert ? "kpress-doc kpress-inert" : "kpress-doc";
    const prose = doc.createElement("div");
    prose.className = "kpress-doc-layout";
    prose.textContent = "Readable prose";
    if (!inert) {
      const details = doc.createElement("details");
      details.className = "kpress-frontmatter";
      const summary = doc.createElement("summary");
      summary.textContent = "Frontmatter";
      details.append(summary);
      article.append(details);
    }
    article.append(prose);
    host.append(article);
    const lifetime = new AbortController();
    const fetches = [];
    let treeDisposed = 0;
    let changeMode;
    const filterControls = createSdkSandbox().metabrowser.filterControls;
    const raw = {
      frontmatter: { title: "Workshop", roles: ["host", "editor"] },
      mtime_hash: "revision",
    };
    const exact = "[host,\r\n editor]";
    const path = "@pin:doc.md";
    attachFrontmatter(
      host,
      path,
      raw,
      {
        filterControls: {
          groupHtml: filterControls.groupHtml,
          keepFocus: () => () => {},
          bind(_controls, { onChange }) {
            changeMode = onChange;
            return () => {
              changeMode = undefined;
            };
          },
        },
        mountStructuredNodeTable: async (...args) => mountNodeTable(...args),
        async mountStructuredExcerpt(host, options) {
          return mountStructuredExcerpt(host, this, options);
        },
        async createStructuredPageReader(path, options) {
          return createStructuredPageReader(this.fetchPluginData, path, options);
        },
        async fetchPluginData(_, __, params) {
          assert.equal(params.path, path);
          assert.equal(params.mtime_hash, "revision");
          const address = JSON.parse(params.node);
          fetches.push(address);
          if (params.copy) {
            assert.equal(params.copy, "row");
            assert.deepEqual(address, ["title"]);
            return { status: "ready", copy_text: "title: Workshop" };
          }
          if (params.source) {
            assert.deepEqual(address, ["roles"]);
            return { status: "ready", source_text: exact, source_start_line: 7 };
          }
          assert.equal(params.depth, address.length ? 1 : 3);
          const array = { kind: "array", child_count: 2 };
          return !address.length
            ? {
                status: "ready",
                node: { kind: "object", child_count: 2 },
                children: [
                  { segment: "roles", node: array },
                  {
                    segment: "title",
                    node: { kind: "string", value: "Workshop", child_count: 0 },
                  },
                ],
              }
            : {
                status: "ready",
                node: array,
                children: ["host", "editor"].map((value, segment) => ({
                  segment,
                  node: { kind: "string", value, child_count: 0 },
                })),
              };
        },
        async loadStructuredTree() {
          return {
            renderInlineTree(el, value) {
              assert.deepEqual(value, ["host", "editor"]);
              el.textContent = "Tree of roles";
              return {
                dispose() {
                  treeDisposed++;
                },
              };
            },
          };
        },
        renderSourceView(el, { content, ext }, { lineStart }) {
          assert.equal(lineStart, 1);
          assert.equal(ext, ".yaml");
          assert.equal(content, exact);
          const wrap = doc.createElement("div");
          wrap.className = "content-copy-wrap";
          wrap.textContent = content;
          el.append(wrap);
        },
      },
      lifetime.signal,
    );
    assert.equal(fetches.length, 0);
    const details = article.firstChild;
    details.open = true;
    details.listeners.get("toggle")();
    const turn = () => new Promise(setImmediate);
    await turn();
    async function click(label) {
      const item = host.find(
        (node) =>
          node.localName === "button" &&
          (node.textContent === label || node.getAttribute?.("aria-label") === label),
      );
      if (item) {
        item.listeners.get("click")();
      } else {
        assert.ok(details.lastChild.firstChild.markup.includes(`data-chip-value="${label}"`));
        changeMode("structured-excerpt-view", label, "one");
      }
      await turn();
    }
    await click("[…] (2 items)");
    const copy = host.find((node) => node.getAttribute?.("aria-label") === "Copy title");
    copy.listeners.get("click")();
    await turn();
    assert.equal(clipboard, "title: Workshop");
    await click("Tree");
    assert.ok(host.textContent.includes("Tree of roles"));
    await click("Source");
    assert.equal(treeDisposed, 1);
    assert.equal(host.querySelector(".content-copy-wrap").textContent, exact);
    await click("Table");
    assert.ok(host.textContent.includes("editor"));
    details.open = false;
    details.listeners.get("toggle")();
    assert.equal(changeMode, undefined);
    assert.equal(details.textContent, "Frontmatter");
    assert.equal(prose.textContent, "Readable prose");
    lifetime.abort();
    assert.equal(details.listeners.has("toggle"), false);
    summaryText.push({
      article: inert ? "sanitized" : "trusted",
      opened: fetches,
      row: clipboard,
      copied: exact,
      prose: prose.textContent,
    });
  }
  console.log(JSON.stringify(summaryText, null, 2));
  const fences = await testFences(
    doc,
    mountStructuredExcerpt,
    mountNodeTable,
    createStructuredPageReader,
  );
  console.log(JSON.stringify(fences, null, 2));
  console.log(
    JSON.stringify(
      await testSourceRecovery(
        doc,
        mountStructuredExcerpt,
        mountNodeTable,
        createStructuredPageReader,
      ),
      null,
      2,
    ),
  );
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
