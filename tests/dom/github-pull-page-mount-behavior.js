// Mount the production pull page with failed assets and renderers. Layout is irrelevant:
// this exercises the asynchronous mount, its recovery control, and replacement ownership.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const root = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/github-pull-page-responses.json"), "utf8"),
);
for (const answer of Object.values(recorded)) {
  for (const envelope of [answer.body, answer.body?.pull]) {
    const holder = envelope?.record?.same_as;
    if (holder !== undefined) {
      envelope.record = recorded[holder].body.record;
    }
  }
}
class Element {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.attributes = new Map();
    this.dataset = {};
    this.events = new Map();
    this.classes = new Set();
    this.classList = {
      add: (...names) =>
        names.forEach((name) => {
          this.classes.add(name);
        }),
      remove: (...names) =>
        names.forEach((name) => {
          this.classes.delete(name);
        }),
      toggle: (name, on) => (on ? this.classes.add(name) : this.classes.delete(name)),
    };
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
    if (name === "class") {
      this.classes = new Set(value.split(" "));
    }
  }
  append(...children) {
    this.children.push(...children);
  }
  prepend(...children) {
    this.children.unshift(...children);
  }
  replaceChildren(...children) {
    this.children = children;
  }
  get textContent() {
    return this.children
      .map((child) => (typeof child === "string" ? child : child.textContent))
      .join("");
  }
  set textContent(value) {
    this.children = [value];
  }
  *descendants() {
    for (const child of this.children) {
      if (typeof child !== "string") {
        yield child;
        yield* child.descendants();
      }
    }
  }
  querySelector(selector) {
    return (
      [...this.descendants()].find((element) => element.classes.has(selector.slice(1))) ?? null
    );
  }
  closest() {
    return null;
  }
  after() {}
  remove() {}
  addEventListener(name, callback) {
    this.events.set(name, callback);
  }
}
async function settle() {
  for (let turn = 0; turn < 10; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}
async function run() {
  const timers = new Map();
  globalThis.document = {
    visibilityState: "visible",
    addEventListener() {},
    createElement: (tag) => new Element(tag),
    importNode: () => new Element("svg"),
  };
  globalThis.window = {
    location: { pathname: "/pull/7/files" },
    setTimeout: (callback) => {
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
  globalThis.fetch = async () => ({ status: 304, headers: { get: () => null } });
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const initial = recorded.current;
  for (const failure of ["assets", "render"]) {
    globalThis.fetch = async () => ({
      status: initial.status,
      headers: { get: () => null },
      json: async () => initial.body,
    });
    const container = new Element("main");
    let fail = true;
    let mounted = 0;
    let disposed = 0;
    const handle = page.mountPullPage(
      container,
      {
        number: 7,
        tab: "files",
        reader: { initial, fetchAfterMs: 0 },
      },
      {
        ensureAsset: async () => {},
        ensureKindAssets: async () => {
          if (fail && failure === "assets") {
            throw Error("asset failed");
          }
        },
        getRegisteredView: () => ({
          render: async (host) => {
            if (fail && failure === "render") {
              throw Error("render failed");
            }
            mounted += 1;
            host.textContent = "Mounted comparison";
            return {
              dispose: () => {
                disposed += 1;
              },
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
    await settle();
    await handle.whenFilesReady();
    assert.match(container.textContent, /Files changed could not load/);
    const retry = [...container.descendants()].find(
      (element) => element.tag === "button" && element.textContent === "Retry",
    );
    assert.ok(retry, "a failed mount offers recovery");
    fail = false;
    retry.events.get("click")();
    await settle();
    await handle.whenFilesReady();
    assert.match(container.textContent, /Mounted comparison/);
    assert.equal(mounted, 1);
    handle.dispose();
    assert.equal(disposed, 1);
    retry.events.get("click")();
    await settle();
    assert.equal(mounted, 1, "a stale Retry cannot remount a disposed page");
  }
  // A comparison request failure is handled inside the production diff renderer: it
  // resolves with a disposable error notice, rather than rejecting the mount.
  let diffView;
  let failureStatus;
  const errors = [];
  window.metabrowser = {
    registerView: (_kind, _name, view) => {
      diffView = view;
    },
    fetchPluginData: async () => {
      throw Object.assign(new Error("comparison failed"), { status: failureStatus });
    },
  };
  const logError = console.error;
  console.error = (...args) => errors.push(args);
  try {
    await import(pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/diff/index.js")));
    for (failureStatus of [404, 409]) {
      const container = new Element("main");
      const handle = page.mountPullPage(
        container,
        { number: 7, tab: "files", reader: { initial, fetchAfterMs: 0 } },
        {
          ensureAsset: async () => {},
          ensureKindAssets: async () => {},
          getRegisteredView: () => diffView,
          formatAge: () => ({ label: "now", className: "age" }),
          formatTimestamp: () => "now",
          navigation: { href: () => "/view/" },
          sourceKind: () => "git_revision",
          icons: { toggle: "" },
        },
      );
      await settle();
      await handle.whenFilesReady();
      assert.match(container.textContent, /Could not load this diff/);
      const absent = { kind: "no_diff", path: "src/app.txt" };
      assert.deepEqual(handle.fileForPath(absent.path), absent);
      assert.deepEqual(handle.scrollToFile(absent.path), absent);
      handle.dispose();
      assert.deepEqual(handle.scrollToFile(absent.path), absent);
    }
    assert.deepEqual(
      errors.map((entry) => entry[1].status),
      [404, 409],
    );
  } finally {
    console.error = logError;
  }
  return { failedAssetsRecover: true, failedRenderRecovers: true, staleRetryIsInert: true };
}
run()
  .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });
