// A replacement list reaches the production controller and paint. Removing a focused
// element makes BODY active, as in a browser, so focus recovery has to happen after paint.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
class Element {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.dataset = {};
    this.style = { setProperty() {} };
    this.textContent = "";
    this.classList = { toggle() {} };
  }
  get firstElementChild() {
    return this.children[0] ?? null;
  }
  get nextElementSibling() {
    const siblings = this.parentNode?.children;
    return siblings?.[siblings.indexOf(this) + 1] ?? null;
  }
  get isConnected() {
    return this === document.body || !!this.parentNode?.isConnected;
  }
  setAttribute(name, value) {
    this.attributes.set(name, value);
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  append(...nodes) {
    for (let node of nodes) {
      if (typeof node === "string") {
        node = Object.assign(new Element("text"), { textContent: node });
      }
      node.remove();
      node.parentNode = this;
      this.children.push(node);
    }
  }
  replaceChildren(...nodes) {
    for (const node of [...this.children]) {
      node.remove();
    }
    this.append(...nodes);
  }
  insertBefore(node, cursor) {
    node.remove();
    node.parentNode = this;
    this.children.splice(
      cursor === null ? this.children.length : this.children.indexOf(cursor),
      0,
      node,
    );
  }
  remove() {
    if (document.activeElement === this) {
      document.activeElement = document.body;
    }
    if (this.parentNode !== null) {
      this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1);
      this.parentNode = null;
    }
  }
  addEventListener() {}
  getBoundingClientRect() {
    return { top: 0, bottom: 700 };
  }
  focus() {
    document.activeElement = this;
  }
  scrollIntoView() {}
}
async function settle() {
  await new Promise((resolve) => setImmediate(resolve));
}
async function run() {
  globalThis.Element = Element;
  globalThis.document = { visibilityState: "visible", createElement: (tag) => new Element(tag) };
  globalThis.getComputedStyle = () => ({ getPropertyValue: () => "24px" });
  const { mountFileTree } = await import(
    pathToFileURL(
      path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/github/pull-files-view.js"),
    ).href
  );
  const results = [];
  for (const scenario of [
    "survivor",
    "empty",
    "other focus",
    "windowed survivor",
    "windowed other focus",
  ]) {
    const timers = new Map();
    globalThis.window = {
      setTimeout(callback, delay) {
        const id = Symbol();
        timers.set(id, { callback, delay });
        return id;
      },
      clearTimeout: (id) => timers.delete(id),
      requestAnimationFrame: () => 1,
      cancelAnimationFrame() {},
    };
    document.body = new Element("body");
    document.activeElement = document.body;
    const parent = new Element("li"),
      owner = new Element("a"),
      elsewhere = new Element("button");
    owner.dataset.id = "owner";
    elsewhere.dataset.id = "elsewhere";
    document.body.append(parent, elsewhere);
    parent.append(owner);
    let generation = 0;
    const view = mountFileTree({
      number: 7,
      autoExpandFiles: 3000,
      current: null,
      shown: true,
      scrollRoot: document.body,
      chevron: () => null,
      href: (file) => `/${file}`,
      request: async (_method, route) => {
        const windowed = scenario.startsWith("windowed");
        const files =
          generation === 0
            ? windowed
              ? Array.from({ length: 300 }, (_, at) => `a${String(at).padStart(3, "0")}.py`)
              : ["a.py", "b.py"]
            : scenario === "empty"
              ? []
              : windowed
                ? ["a000.py"]
                : ["a.py"];
        const offset = Number(new URL(route, "http://example").searchParams.get("offset"));
        return {
          status: 200,
          etag: null,
          body: {
            state: "current",
            reason: null,
            number: 7,
            listed_from: "github",
            fetched_at: `2026-11-03T00:00:0${generation}Z`,
            reader: "gh:test",
            head: null,
            base: null,
            fresh_for_s: 60,
            refreshing: false,
            last_refresh: null,
            fetched: files.length,
            pages: 1,
            last_page: null,
            complete: true,
            capped: false,
            truncated: false,
            offset,
            limit: 3000,
            rows: files.slice(offset).map((file) => ({
              path: file,
              display: file,
              previous_path: null,
              previous_display: null,
              status: "modified",
              additions: 1,
              deletions: 0,
            })),
          },
        };
      },
      formatTime: (value) => value,
      page: () => null,
      open() {},
      leave: () => owner.focus(),
      focusedIn() {},
    });
    view.attach(parent, owner);
    view.controller.expand();
    await settle();
    const list = view.group.children[3];
    const selectedId = scenario.startsWith("windowed") ? "a250.py" : "b.py";
    view.controller.focused(selectedId);
    const selected = list.children.find((element) => element.dataset.id === selectedId);
    assert.ok(selected, "the anchor is retained outside the visible row window");
    (scenario.endsWith("other focus") ? elsewhere : selected).focus();
    generation = 1;
    for (const delay of [60000, 0]) {
      const entry = [...timers].find(([, timer]) => timer.delay === delay);
      assert.ok(entry, "the replacement is read from its start");
      timers.delete(entry[0]);
      entry[1].callback();
      await settle();
    }
    const expected =
      scenario === "survivor"
        ? "a.py"
        : scenario === "windowed survivor"
          ? "a000.py"
          : scenario === "empty"
            ? "owner"
            : "elsewhere";
    assert.equal(document.activeElement.dataset.id, expected, scenario);
    results.push({ scenario, focus: expected });
    view.dispose();
  }
  return results;
}
run()
  .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });
