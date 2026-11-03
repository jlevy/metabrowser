// Production route host plus production page: history restores an entry's place; a new
// selection owns its jump even while a previous entry is still holding its saved place.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");

async function run() {
  const timers = new Map();
  const resize = new Set();
  const pane = new Element("pane");
  pane.scrollTop = 0;
  pane.getBoundingClientRect = () => ({ top: 0 });
  Element.prototype.closest = () => pane;
  Element.prototype.querySelectorAll = function (selector) {
    const classes = selector.split(",").map((part) => part.trim().slice(1));
    return [...this.descendants()].filter((element) =>
      classes.some((name) => element.classes.has(name)),
    );
  };
  globalThis.document = {
    visibilityState: "visible",
    addEventListener() {},
    createElement: (tag) => new Element(tag),
    importNode: () => new Element("svg"),
  };
  globalThis.window = {
    location: { pathname: "/pull/7/files/a.py", hash: "" },
    history: {
      state: null,
      replaceState(state) {
        this.state = state;
      },
    },
    addEventListener() {},
    setTimeout(callback) {
      const id = Symbol();
      timers.set(id, callback);
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
  };
  globalThis.DOMParser = class {
    parseFromString() {
      return { body: { firstElementChild: null } };
    }
  };
  globalThis.ResizeObserver = class {
    constructor(callback) {
      this.callback = callback;
      resize.add(callback);
    }
    observe() {}
    disconnect() {
      resize.delete(this.callback);
    }
  };
  globalThis.fetch = async () => ({ status: 304, headers: { get: () => null } });
  vm.runInThisContext(
    fs.readFileSync(path.join(root, "src/metabrowser/static/pull-route.js"), "utf8"),
  );
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const jumps = [];
  let handle = null;
  let claim = 0;
  const navigate = (href) => {
    window.location.pathname = href;
    window.history.state = null;
  };
  const host = window.MetabrowserPullRoute.createPullPageHost({
    claim: () => ++claim,
    isCurrent: (mine) => mine === claim,
    mount: async (_claim, route) => {
      handle = page.mountPullPage(
        new Element("main"),
        {
          ...route,
          reader: { initial: recorded.current, fetchAfterMs: 0 },
        },
        {
          perf,
          ensureAsset: async () => {},
          ensureKindAssets: async () => {},
          getRegisteredView: () => ({
            render: async (container) => {
              for (const top of [100, 400, 700]) {
                const block = new Element("section");
                block.setAttribute("class", "diff-file");
                block.getBoundingClientRect = () => ({ top: top - pane.scrollTop });
                container.append(block);
              }
              return {
                scrollToFile(file) {
                  jumps.push(file);
                  pane.scrollTop = { "a.py": 100, "b.py": 400, "c.py": 700 }[file];
                  return { kind: "jumped", path: file };
                },
                dispose() {},
              };
            },
          }),
          formatAge: () => ({ label: "now", className: "age" }),
          formatTimestamp: () => "now",
          navigation: { href: () => "/view/" },
          sourceKind: () => "git_revision",
          icons: { toggle: "" },
        },
      );
      return handle;
    },
    mountList: async () => null,
    pathname: () => window.location.pathname,
    pushHref: navigate,
    replaceHref: navigate,
  });
  await host.show({ number: 7, tab: "files", file: "a.py" });
  await settle();
  await handle.whenFilesReady();
  assert.equal(pane.scrollTop, 100);
  pane.scrollTop = 350;
  pane.events.get("scroll")();
  await host.open({ number: 7, tab: "files", file: "b.py" });
  const saved = { pullPlace: { block: 0, offset: 250, top: 350 } };
  assert.equal(pane.scrollTop, 400);
  window.location.pathname = "/pull/7/files/a.py";
  window.history.state = saved;
  host.onHistory(window.location.pathname, false);
  assert.equal(pane.scrollTop, 350, "same-tab Back restores the saved offset");
  await host.open({ number: 7, tab: "" });
  window.location.pathname = "/pull/7/files/a.py";
  window.history.state = saved;
  host.onHistory(window.location.pathname, false);
  await settle();
  await handle.whenFilesReady();
  for (const callback of resize) {
    callback();
  }
  assert.equal(
    pane.scrollTop,
    350,
    "Back from Conversation holds the offset through diff mounting",
  );
  await host.open({ number: 7, tab: "files", file: "c.py" });
  assert.equal(pane.scrollTop, 700, "a fresh selection overrides the previous entry's hold");
  assert.deepEqual(jumps, ["a.py", "b.py", "c.py"]);
  host.dispose();
  return { sameTabBack: 350, conversationBack: 350, freshSelection: 700 };
}
run()
  .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });
