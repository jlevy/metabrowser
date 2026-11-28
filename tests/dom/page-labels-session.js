// The shell's label projection and publication, with the production route readers.
// The fixture exposes only direct committed headings to the publisher.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class Element {
  constructor(attributes = {}, textContent = null) {
    this.attributes = attributes;
    this.dataset = {};
    this.children = new Map();
    this.textContent = textContent;
    this.classList = { contains: (name) => (attributes.class ?? "").split(" ").includes(name) };
  }
  getAttribute(name) {
    return this.attributes[name] ?? null;
  }
  querySelector(selector) {
    return this.children.get(selector) ?? null;
  }
}

const staticDir = path.resolve(__dirname, "../../src/metabrowser/static");
const preview = new Element();
const rootMark = { dataset: { rootKind: "folder" } };
const document = {
  title: "demo",
  getElementById: (id) =>
    id === "preview-pane" ? preview : id === "header-root-kind" ? rootMark : null,
};
const listeners = new Map();
const history = { state: null };
const messages = [];
const calls = [];
let observer;
const sandbox = {
  Element,
  document,
  history,
  URLSearchParams,
  TextEncoder,
  TextDecoder,
  location: new URL("http://localhost:8457/view/src/index.md#L12C2-L18C4"),
  queueMicrotask: (call) => calls.push(call),
  MutationObserver: class {
    constructor(call) {
      observer = call;
    }
    observe() {}
  },
  addEventListener: (name, call) => listeners.set(name, call),
  metabrowser: { registerView() {} },
  metabrowserHost: { actions: ["navigation-history"] },
  webkit: { messageHandlers: { metabrowserNavigation: { postMessage: (m) => messages.push(m) } } },
};
sandbox.window = sandbox;
vm.createContext(sandbox);
function load(name) {
  const filename = path.join(staticDir, name);
  vm.runInContext(fs.readFileSync(filename, "utf8"), sandbox, { filename });
}
function show(name) {
  while (calls.length) {
    calls.shift()();
  }
  const current = messages.at(-1);
  console.log(
    JSON.stringify({
      name,
      browser: document.title,
      messages: messages.length,
      native:
        current?.url === sandbox.location.href
          ? { title: current.title, icon: current.icon, context: current.context }
          : null,
    }),
  );
}
function address(href, event) {
  sandbox.location = new URL(href, sandbox.location);
  if (event) {
    listeners.get(event)();
  } else {
    sandbox.MetabrowserPageLabels.addressChanged();
  }
}
function commit(selector, node) {
  preview.children.clear();
  preview.children.set(selector, node);
  observer([{ target: preview }]);
}

const file = new Element({ "data-path": "src/index.md" });
file.children.set(".view-header-title", new Element({}, "index.md"));
file.children.set(".view-header-icon", new Element({ "data-page-icon": "fileText" }));
preview.children.set(":scope > .view-header", file);

for (const name of [
  "navigation.js",
  "pull-route.js",
  "formatters.js",
  "plugin-sdk-views.js",
  "icons.js",
  "page-labels.js",
]) {
  load(name);
}
show("direct file link and selected lines");
address("/view/docs/index.md");
show("address changes while the previous file is retained");
file.attributes["data-path"] = "docs/index.md";
commit(":scope > .view-header", file);
show("new file commits");
address("/view/docs/index.md?table");
show("addressed file view");
address("/view/");
const root = new Element({ "data-path": "", class: "folder-header" });
root.children.set(".view-header-title", new Element({}, "demo"));
commit(":scope > .view-header", root);
show("served root preserves its distinct folder glyph");

const pull = new Element();
pull.parentElement = { parentElement: new Element({ class: "pull-request-host" }) };
pull.children.set(".github-pull-title-text", new Element({}, "  Refine\n navigation  "));
pull.children.set(".github-pull-number", new Element({}, "#23"));
const state = new Element({ "data-state": "draft" });
pull.children.set(".github-pull-state-icon", state);
address("/pull/23/files/src/index.md");
commit(":scope > .github-pull > .page-header > .github-pull-title", pull);
show("PR commits with its draft icon and changed file");
address("/pull/23/conversation");
show("another tab uses the same PR heading");
address("/pull/23/conversation", "popstate");
show("traversal to an equal URL reports the new entry");
address("/pull/23/conversation");
show("redundant address notification is silent");

pull.parentElement.parentElement = new Element({ class: "pull-stack-host" });
pull.children.get(".github-pull-title-text").textContent = "Stack Overview";
address("/stack/23/guided");
commit(":scope > .github-pull > .page-header > .github-pull-title", pull);
show("stack overview and selected view");

const revision = "abc1234567890";
const commitPage = new Element({ "data-revision": revision });
commitPage.children.set("h1.git-commit-subject", new Element({}, "feat: share page labels"));
commitPage.children.set(".git-commit-sha", new Element({}, "abc1234"));
address(`/commit/${revision}/src/index.md`, "popstate");
commit(":scope > .git-commit-stage", commitPage);
show("commit subject and change context");

address("/pulls?state=closed", "popstate");
commit(":scope > .pull-request-list-host[data-preview-empty]", new Element());
show("pulls overview and filter");

history.state = { gitLanding: true };
preview.dataset.previewOwner = "git";
address("/view/");
show("neutral Commits entry owns the preview");
history.state = null;

sandbox.metabrowserHost = undefined;
address("/view/docs/index.md", "popstate");
commit(":scope > .view-header", file);
show("ordinary browser updates its title without posting");
