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
  const frames = new Map();
  const paintFrame = () => {
    const ready = [...frames.values()];
    frames.clear();
    for (const callback of ready) {
      callback();
    }
  };
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
    requestAnimationFrame: (callback) => {
      const id = frames.size + 1;
      frames.set(id, callback);
      return id;
    },
    cancelAnimationFrame: (id) => frames.delete(id),
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
    let unsubscriptions = 0;
    let reportFile = null;
    let currentFile = {
      kind: "file",
      path: "src/one.py",
      fileId: "one",
      changeKind: "modified",
      availability: "ready",
    };
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
              currentFile: () => currentFile,
              onCurrentFile(listener) {
                reportFile = listener;
                listener(currentFile);
                return () => {
                  unsubscriptions += 1;
                  reportFile = null;
                };
              },
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
    assert.equal(handle.currentFile(), null);
    const files = [];
    const unwatchFile = handle.onCurrentFile((file) => files.push(file?.path ?? null));
    fail = false;
    retry.events.get("click")();
    await settle();
    await handle.whenFilesReady();
    assert.match(container.textContent, /Mounted comparison/);
    assert.equal(mounted, 1);
    assert.equal(handle.currentFile().path, "src/one.py");
    assert.equal(reportFile, null, "readiness settles without subscribing in the mount task");
    const immediate = [];
    handle.onCurrentFile((file) => immediate.push(file?.path ?? null))();
    assert.deepEqual(immediate, ["src/one.py"], "explicit subscribers get an immediate snapshot");
    paintFrame();
    assert.equal(reportFile, null, "the first frame may paint before the bridge reads layout");
    currentFile = { ...currentFile, path: "src/two.py", fileId: "two" };
    paintFrame();
    assert.equal(files.at(-1), "src/two.py", "the bridge reads the latest selection after paint");
    currentFile = { ...currentFile, path: "src/three.py", fileId: "three" };
    reportFile(currentFile);
    assert.equal(files.at(-1), "src/three.py", "the page forwards a hand-scrolled file");
    handle.land({ tab: "" });
    assert.equal(unsubscriptions, 1, "replacement releases the diff subscription");
    handle.setTab("files");
    await settle();
    await handle.whenFilesReady();
    paintFrame();
    const abandoned = [...frames.values()][0];
    assert.ok(abandoned, "the replacement owns a pending second frame");
    handle.land({ tab: "" });
    assert.equal(frames.size, 0, "replacement cancels the pending frame");
    handle.setTab("files");
    await settle();
    await handle.whenFilesReady();
    const disposedFrame = [...frames.values()][0];
    abandoned();
    assert.equal(reportFile, null, "an already queued old frame cannot observe its replacement");
    unwatchFile();
    handle.dispose();
    disposedFrame();
    assert.equal(reportFile, null, "disposal makes queued bridge work inert");
    assert.equal(frames.size, 0, "disposal cancels owned frames");
    handle.onCurrentFile(() => {
      throw Error("a disposed page must not retain subscriptions");
    });
    assert.equal(disposed, 3);
    retry.events.get("click")();
    await settle();
    assert.equal(mounted, 3, "a stale Retry cannot remount a disposed page");
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
  delete window.requestAnimationFrame;
  delete window.cancelAnimationFrame;
  document.visibilityState = "hidden";
  const fallbackTasks = new Map();
  window.setTimeout = (callback, delay) => {
    const id = Symbol();
    fallbackTasks.set(id, { callback, delay });
    return id;
  };
  window.clearTimeout = (id) => fallbackTasks.delete(id);
  let hiddenSubscriptions = 0;
  let hiddenUnsubscriptions = 0;
  const hiddenOptions = { number: 7, tab: "files", reader: { initial, fetchAfterMs: 0 } };
  const hiddenApi = {
    ensureAsset: async () => {},
    ensureKindAssets: async () => {},
    getRegisteredView: () => ({
      render: async () => ({
        currentFile: () => ({ kind: "file", path: "src/now.py", fileId: "now" }),
        onCurrentFile(listener) {
          hiddenSubscriptions += 1;
          listener({ kind: "file", path: "src/now.py", fileId: "now" });
          return () => {
            hiddenUnsubscriptions += 1;
          };
        },
        dispose() {},
      }),
    }),
    formatAge: () => ({ label: "now", className: "age" }),
    formatTimestamp: () => "now",
    navigation: { href: () => "/view/" },
    sourceKind: () => "git_revision",
    icons: { toggle: "" },
  };
  const hidden = page.mountPullPage(new Element("main"), hiddenOptions, hiddenApi);
  await settle();
  await hidden.whenFilesReady();
  assert.equal(hiddenSubscriptions, 0, "hidden/no-frame readiness does not wait for the bridge");
  const fallback = [...fallbackTasks.values()].find((task) => task.delay === 0);
  assert.ok(fallback, "a nonvisual host owns a later bridge task");
  hidden.dispose();
  fallback.callback();
  assert.equal(hiddenSubscriptions, 0, "disposal invalidates even a queued fallback task");
  assert.equal(fallbackTasks.size, 0);
  const reentrant = page.mountPullPage(new Element("main"), hiddenOptions, hiddenApi);
  await settle();
  await reentrant.whenFilesReady();
  let armed = false;
  reentrant.onCurrentFile(() => {
    if (armed) {
      reentrant.dispose();
    }
  });
  armed = true;
  const reentrantTask = [...fallbackTasks.values()].find((task) => task.delay === 0);
  assert.ok(reentrantTask);
  reentrantTask.callback();
  assert.equal(hiddenSubscriptions, 1);
  assert.equal(
    hiddenUnsubscriptions,
    1,
    "reentrant disposal releases the just-created subscription",
  );
  return {
    failedAssetsRecover: true,
    failedRenderRecovers: true,
    staleRetryIsInert: true,
    bridgeAfterPaint: true,
    bridgeFramesOwned: true,
    hiddenReadiness: true,
  };
}
module.exports = { Element, recorded, root, settle };
if (require.main === module) {
  run()
    .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
    .catch((error) => {
      process.stderr.write(`${error.stack}\n`);
      process.exitCode = 1;
    });
}
