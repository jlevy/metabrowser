// A browserless collection visit. Mount the real view, catalog, and SDK progress
// component against successive collection answers and a delayed table renderer.
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
  querySelector(selector) {
    const className = selector.slice(1);
    for (const child of this.childNodes) {
      if (child instanceof Element) {
        const found = child.classList.contains(className) ? child : child.querySelector(selector);
        if (found) {
          return found;
        }
      }
    }
    return null;
  }
}

async function main() {
  const plugins = "../../src/metabrowser/builtin_plugins";
  const { renderTableCatalog } = await import(`${plugins}/table/table-catalog.js`);
  const sdk = createSdkSandbox();
  const path = "people";
  let current = { path, query: "table=" };
  let answer = {
    root: "kb",
    state: "indexing",
    generation: "indexing",
    complete: false,
    paths_checked: 0,
    tables: [],
    summary: null,
  };
  let render;
  let popstate;
  let poll;
  let mounted = null;
  const refreshed = [];
  let releaseTree;
  const tree = new Promise((resolve) => {
    releaseTree = resolve;
  });
  const turn = () => new Promise(setImmediate);
  const href = ({ path, query }) => `/view/${path}?${query}`;
  const realTimers = { setTimeout: global.setTimeout, clearTimeout: global.clearTimeout };
  global.document = { createElement: (tag) => new Element(tag) };
  global.window = {
    metabrowser: {
      ...sdk.metabrowser,
      registerView(_kind, _view, definition) {
        render = definition.render;
      },
      fetchPluginData: async () => answer,
      navigation: {
        current: () => current,
        href,
        open: async (target) => {
          current = target;
        },
      },
      plugins: {
        load: async (name) =>
          name === "table"
            ? {
                renderTableCatalog,
                mountTable(_, options) {
                  mounted = options;
                  return {
                    dispose() {},
                    async refresh(options) {
                      refreshed.push(options);
                    },
                  };
                },
              }
            : tree,
      },
    },
    addEventListener: (_name, fn) => {
      popstate = fn;
    },
    removeEventListener() {},
  };
  await import(`${plugins}/softschema/index.js`);
  global.setTimeout = (callback) => {
    poll = callback;
  };
  global.clearTimeout = () => {
    poll = undefined;
  };
  try {
    const container = new Element("div");
    const view = render(container, { path });
    await turn();
    const progress = container.querySelector(".index-progress");
    assert.equal(progress.hidden, false);
    assert.equal(progress.getAttribute("role"), "status");
    const indicator = progress.querySelector(".index-progress-spinner");
    assert.equal(indicator.getAttribute("aria-hidden"), "true");
    const cold = progress.textContent;
    assert.equal(sdk.MetabrowserSourceLineAnchors.preferredView(current), "table");

    answer = { ...answer, paths_checked: 512 };
    poll();
    await turn();
    assert.equal(progress.querySelector(".index-progress-spinner"), indicator);
    const discovery = progress.textContent;

    answer = {
      ...answer,
      state: "ready",
      generation: "1",
      complete: true,
      summary: { problems: [{ code: "invalid" }] },
      tables: [{ id: "person/v2", label: "Person", count: 577 }],
    };
    poll();
    await turn();
    const catalog = container.querySelector(".table-catalog");
    const row = catalog.querySelector(".table-catalog-name");
    const link = row.firstElementChild;
    const count = catalog.querySelector(".table-catalog-estimate").textContent;
    assert.equal(progress.hidden, true);
    assert.equal(link.getAttribute("href"), "/view/people?table=person%2Fv2");

    answer = { ...answer, state: "indexing" };
    poll();
    await turn();
    assert.equal(progress.hidden, true);
    assert.equal(container.querySelector(".table-catalog"), catalog);

    link.listeners.get("click")({ button: 0, preventDefault() {} });
    await turn();
    current = { path, query: "table=" };
    popstate();
    const renderRecordValue = () => ({ dispose() {} });
    releaseTree({ renderRecordValue });
    await turn();
    assert.equal(mounted, null);
    assert.equal(container.querySelector(".table-catalog"), catalog);

    link.listeners.get("click")({ button: 0, preventDefault() {} });
    await turn();
    assert.equal(mounted.renderJson, renderRecordValue);
    assert.equal(mounted.table, "person/v2");
    assert.equal(href(mounted.catalogAddress), "/view/people?table=");
    answer = { ...answer, generation: "2" };
    poll();
    await turn();
    assert.deepEqual(refreshed, [{ generation: "2" }]);
    poll();
    await turn();
    assert.equal(refreshed.length, 1);
    answer = { ...answer, generation: "3", tables: [] };
    poll();
    await turn();
    assert.equal(refreshed.length, 1, "a removed table is disposed before refresh");
    const status = container.querySelector(".table-status");
    answer = {
      ...answer,
      complete: false,
      state: "ready",
      generation: "partial",
      summary: {
        problems: [
          { code: "total_byte_limit" },
          { code: "directory_unreadable" },
          { code: "file_unreadable" },
          { code: "invalid" },
        ],
      },
    };
    poll();
    await turn();
    assert.equal(status.hidden, false);
    assert.equal(status.dataset.severity, "warning");
    const partial = status.textContent;
    answer = {
      ...answer,
      generation: "bounded",
      summary: { problems: [{ code: "entry_limit" }, { code: "file_too_large" }] },
    };
    poll();
    await turn();
    const bounded = status.textContent;
    answer = {
      ...answer,
      complete: true,
      generation: "complete",
      tables: [{ id: "person/v2", label: "Person", count: 1 }],
      summary: { problems: [{ code: "invalid" }] },
    };
    poll();
    await turn();
    assert.equal(status.hidden, true, "complete discovery can still report invalid records");
    view.dispose();
    console.log(
      JSON.stringify(
        {
          "cold index": cold,
          "collection discovery": discovery,
          "partial index": partial,
          "bounded scan": bounded,
          "published table": { label: link.textContent, count, href: link.getAttribute("href") },
          "background refresh": "the catalog stays visible without its indexing spinner",
          "return before the renderer arrives": "the catalog keeps the same links",
          "return from a mounted table": href(mounted.catalogAddress),
        },
        null,
        2,
      ),
    );
  } finally {
    Object.assign(global, realTimers);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
