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
    currentFile = { ...currentFile, path: "src/two.py", fileId: "two" };
    reportFile(currentFile);
    assert.equal(files.at(-1), "src/two.py", "the page forwards a hand-scrolled file");
    unwatchFile();
    handle.dispose();
    assert.equal(unsubscriptions, 1, "disposal releases the diff subscription");
    handle.onCurrentFile(() => {
      throw Error("a disposed page must not retain subscriptions");
    });
    assert.equal(disposed, 1);
    retry.events.get("click")();
    await settle();
    assert.equal(mounted, 1, "a stale Retry cannot remount a disposed page");
  }
  for (const outcome of ["same", "moved", "failed"]) {
    let current = structuredClone(initial.body);
    let reply;
    const requests = [];
    const mounted = [];
    let disposed = 0;
    globalThis.fetch = async (_route, options = {}) => {
      if (options.method === "POST") {
        requests.push(JSON.parse(options.body));
        return new Promise((resolve) => {
          reply = resolve;
        });
      }
      return { status: 200, headers: { get: () => null }, json: async () => current };
    };
    const container = new Element("main");
    const handle = page.mountPullPage(
      container,
      {
        number: 7,
        tab: "files",
        reader: { initial, fetchAfterMs: 0 },
      },
      {
        ensureAsset: async () => {},
        ensureKindAssets: async () => {},
        getRegisteredView: () => ({
          render: async (host, options) => {
            mounted.push(options.comparison);
            host.textContent = "Displayed changes";
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
    const tick = async () => {
      const [id, callback] = timers.entries().next().value;
      timers.delete(id);
      callback();
      await settle();
    };
    await settle();
    await handle.whenFilesReady();
    assert.equal(mounted.length, 1);
    const displayed = { base: mounted[0].left, head: mounted[0].right };
    if (outcome === "moved") {
      current = structuredClone(current);
      current.record.comparison.head = "e".repeat(40);
      current.record.pull.head.sha = "e".repeat(40);
      await tick();
      assert.equal(mounted.length, 1, "a metadata-only head advance retains displayed changes");
    }
    const refresh = [...container.descendants()].find(
      (element) => element.tag === "button" && element.textContent === "Refresh",
    );
    assert.ok(refresh, "fresh Files offers explicit repair");
    refresh.events.get("click")();
    await settle();
    refresh.events.get("click")();
    await settle();
    assert.deepEqual(requests, [{ number: 7, retry: true, recovery: displayed }]);
    assert.equal(mounted.length, 1, "a pending POST cannot remount");
    current = { ...current, refreshing: true };
    reply({ status: 202, headers: { get: () => null }, json: async () => ({ pull: current }) });
    await settle();
    await tick();
    assert.equal(mounted.length, 1, "waiting for a job cannot remount");
    current = {
      ...current,
      refreshing: false,
      last_refresh: {
        outcome: outcome === "failed" ? "network_error" : "succeeded",
        message: outcome === "failed" ? "offline" : null,
        reset_at: null,
        at: current.fetched_at,
      },
    };
    await tick();
    await handle.whenFilesReady();
    assert.equal(mounted.length, outcome === "failed" ? 1 : 2);
    assert.equal(disposed, outcome === "failed" ? 0 : 1);
    assert.deepEqual(mounted.at(-1), mounted[0], "repair never selects a newer head");
    if (outcome === "moved") {
      assert.match(container.textContent, /Show the newer changes/);
    }
    await tick();
    assert.equal(mounted.length, outcome === "failed" ? 1 : 2, "only one remount per repair");
    handle.dispose();
    refresh.events.get("click")();
    await settle();
    assert.equal(requests.length, 1, "disposed Refresh is inert");
  }
  const checkout = JSON.parse(
    fs.readFileSync(
      path.join(root, "tests/fixtures/github-checkout-comparison-responses.json"),
      "utf8",
    ),
  );
  const posts = [];
  globalThis.fetch = async (_route, options = {}) => {
    const answer = options.method === "POST" ? checkout.started : checkout.before;
    if (options.method === "POST") {
      posts.push(JSON.parse(options.body));
    }
    return { status: answer.status, headers: { get: () => null }, json: async () => answer.body };
  };
  const checkoutContainer = new Element("main");
  const checkoutHandle = page.mountPullPage(
    checkoutContainer,
    {
      number: 10,
      tab: "files",
      reader: { initial: checkout.before, fetchAfterMs: 0 },
    },
    {
      ensureAsset: async () => {},
      ensureKindAssets: async () => {},
      getRegisteredView: () => {
        throw new Error("no comparison exists before Fetch");
      },
      formatAge: () => ({ label: "now", className: "age" }),
      formatTimestamp: () => "now",
      navigation: { href: () => "/view/" },
      sourceKind: () => "filesystem",
      icons: { toggle: "" },
    },
  );
  await settle();
  assert.deepEqual(posts, []);
  const fetchChanges = [...checkoutContainer.descendants()].find(
    (element) => element.tag === "button" && element.textContent === "Fetch changes",
  );
  assert.ok(fetchChanges, "Files changed offers explicit Fetch");
  fetchChanges.events.get("click")();
  await settle();
  assert.deepEqual(posts, [{ number: 10, retry: true, comparison: true }]);
  assert.equal(checkoutContainer.querySelector(".github-pull-fetch-changes"), null);
  checkoutHandle.dispose();
  fetchChanges.events.get("click")();
  await settle();
  assert.equal(posts.length, 1, "a disposed Fetch button starts nothing");
  return {
    failedAssetsRecover: true,
    failedRenderRecovers: true,
    staleRetryIsInert: true,
    checkoutFetchIsExplicit: true,
    displayedComparisonRepair: true,
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
