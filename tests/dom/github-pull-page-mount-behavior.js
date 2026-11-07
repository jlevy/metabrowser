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
    this.tagName = tag.toUpperCase();
    this.parentNode = null;
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
  get ownerDocument() {
    return globalThis.document;
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
    if (name === "class") {
      this.classes = new Set(value.split(" "));
    }
  }
  append(...children) {
    for (const child of children) {
      if (typeof child !== "string") {
        child.parentNode = this;
      }
      this.children.push(child);
    }
  }
  prepend(...children) {
    this.children.unshift(...children);
  }
  replaceChildren(...children) {
    for (const child of this.children) {
      if (typeof child !== "string" && child.parentNode === this) {
        child.parentNode = null;
      }
    }
    this.children = [];
    this.append(...children);
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
  querySelectorAll(selector) {
    const direct = selector.startsWith(":scope > ");
    const wanted = direct ? selector.slice(9) : selector;
    const nodes = direct
      ? this.children.filter((node) => typeof node !== "string")
      : [...this.descendants()];
    return nodes.filter((node) =>
      wanted === "a[href]"
        ? node.tag === "a" && node.attributes.has("href")
        : wanted.startsWith(".") && node.classes.has(wanted.slice(1)),
    );
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
  replaceWith(...nodes) {
    const parent = this.parentNode;
    if (!parent) {
      return;
    }
    const at = parent.children.indexOf(this);
    if (at < 0) {
      return;
    }
    parent.children.splice(at, 1, ...nodes);
    for (const node of nodes) {
      if (typeof node !== "string") {
        node.parentNode = parent;
      }
    }
    this.parentNode = null;
  }
  closest() {
    return null;
  }
  after(...nodes) {
    const parent = this.parentNode;
    if (!parent) {
      return;
    }
    for (const node of nodes) {
      if (typeof node !== "string") {
        node.remove();
        node.parentNode = parent;
      }
    }
    parent.children.splice(parent.children.indexOf(this) + 1, 0, ...nodes);
  }
  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((node) => node !== this);
    }
    this.parentNode = null;
  }
  addEventListener(name, callback) {
    this.events.set(name, callback);
  }
}
const perfEntries = [];
const perf = {
  measure(label, work) {
    try {
      return work();
    } finally {
      perfEntries.push(label);
    }
  },
  async measureAsync(label, work) {
    try {
      return await work();
    } finally {
      perfEntries.push(label);
    }
  },
};
async function settle() {
  for (let turn = 0; turn < 10; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}
async function releasedFilesMounts(page, initial, diffView, errors) {
  const results = {};
  for (const phase of ["assets", "renderer", "comparison"]) {
    let finish;
    let fail;
    const held = new Promise((resolve, reject) => {
      finish = resolve;
      fail = reject;
    });
    let started = 0;
    let disposed = 0;
    let requested = 0;
    let requestSignal;
    if (phase === "comparison") {
      window.metabrowser.fetchPluginData = (_plugin, hook, _params, options) => {
        assert.equal(hook, "pull-comparison");
        requested += 1;
        requestSignal = options?.signal;
        requestSignal?.addEventListener("abort", () => fail(requestSignal.reason), { once: true });
        return held;
      };
    }
    const readiness = () => perfEntries.filter((label) => label === "githubPull:filesReady").length;
    const readyBefore = readiness();
    const errorsBefore = errors.length;
    const container = new Element("main");
    const handle = page.mountPullPage(
      container,
      { number: 7, tab: "files", reader: { initial, fetchAfterMs: 0 } },
      {
        perf,
        ensureAsset: async () => {},
        ensureKindAssets: async () => {
          if (phase === "assets") {
            await held;
          }
        },
        getRegisteredView: () =>
          phase === "comparison"
            ? diffView
            : {
                async render() {
                  started += 1;
                  if (phase === "renderer") {
                    await held;
                  }
                  return {
                    currentFile: () => ({ kind: "file", path: "old.txt", fileId: "old" }),
                    dispose() {
                      disposed += 1;
                    },
                  };
                },
              },
        ...require("./sdk-ref-fixture.js").refHelpers(document),
        formatAge: () => ({ label: "now", className: "age" }),
        formatTimestamp: () => "now",
        navigation: { href: () => "/view/" },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
      },
    );
    await settle();
    await handle.ready;
    assert.equal(
      started,
      phase === "renderer" ? 1 : 0,
      `${phase} is held at its intended boundary`,
    );
    assert.equal(requested, phase === "comparison" ? 1 : 0);
    const host = container.querySelector(".github-pull-diff");
    assert.ok(host);
    const text = container.textContent;
    handle.cancelPending();
    const comparisonAborted = phase === "comparison" ? requestSignal?.aborted === true : null;
    if (phase === "comparison") {
      // Also settle the old unbound request on the RED side so the session can inspect it.
      fail(new DOMException("Released Files page", "AbortError"));
    } else {
      finish();
    }
    await handle.whenFilesReady();
    results[phase] = {
      started,
      disposed,
      comparisonAborted,
      preserved:
        container.querySelector(".github-pull-diff") === host && container.textContent === text,
      ownsFile: handle.currentFile() !== null,
      filesReady: readiness() - readyBefore,
      errors: errors.length - errorsBefore,
    };
    handle.dispose();
  }
  assert.deepEqual(
    results,
    {
      assets: {
        started: 0,
        disposed: 0,
        comparisonAborted: null,
        preserved: true,
        ownsFile: false,
        filesReady: 0,
        errors: 0,
      },
      renderer: {
        started: 1,
        disposed: 1,
        comparisonAborted: null,
        preserved: true,
        ownsFile: false,
        filesReady: 0,
        errors: 0,
      },
      comparison: {
        started: 0,
        disposed: 0,
        comparisonAborted: true,
        preserved: true,
        ownsFile: false,
        filesReady: 0,
        errors: 0,
      },
    },
    "released Files work cannot change the retained surface or publish a late renderer",
  );
}

async function markdownOwnership(page) {
  for (const delayed of ["inert", "styles"]) {
    for (const transition of ["response", "replace", "metadata", "tab", "dispose"]) {
      const timers = new Map();
      globalThis.document = {
        visibilityState: "visible",
        addEventListener() {},
        removeEventListener() {},
        createElement: (tag) => new Element(tag),
        importNode: () => new Element("svg"),
      };
      globalThis.window = {
        location: { pathname: "/pull/7" },
        setTimeout(callback, delay) {
          const id = Symbol();
          timers.set(id, { callback, delay });
          return id;
        },
        clearTimeout: (id) => timers.delete(id),
      };
      let release;
      const waiting = new Promise((resolve) => {
        release = resolve;
      });
      // The sanitizer is a dependency boundary here: exact HTML transfer/ownership,
      // not sanitizer policy, is exercised by this mounted controller session.
      const inert = {
        sanitizeHtml: (html) => html,
        kpressProse(html) {
          const node = document.createElement("p");
          node.textContent = html;
          return node;
        },
      };
      const first = structuredClone(recorded.current);
      first.body.record_revision = "a".repeat(64);
      first.body.record.pull.body = "plain A";
      first.body.record.issue_comments = [];
      first.body.record.reviews = [];
      first.body.record.review_comments = [];
      first.body.record.comparison = null;
      first.body.record.unavailable.comparison = "no_store";
      let current = first;
      let releaseResponse;
      let markdownReads = 0;
      let assets = 0;
      globalThis.fetch = async (route) => {
        const response = (body) => ({
          status: 200,
          headers: { get: () => null },
          json: async () => body,
        });
        if (route.startsWith("/api/plugin/github/pull-markdown")) {
          markdownReads += 1;
          const reply = response({
            fetched_at: current.body.fetched_at,
            record_revision: current.body.record_revision,
            html: current.body.record.pull.body === "plain A" ? "rendered A" : "rendered B",
            assets: {},
          });
          if (transition === "response" && markdownReads === 1) {
            return new Promise((resolve) => {
              releaseResponse = () => resolve(reply);
            });
          }
          return reply;
        }
        return route.startsWith("/api/plugin/github/pull?")
          ? response(current.body)
          : { status: 304, headers: { get: () => null } };
      };
      const container = new Element("main");
      const handle = page.mountPullPage(
        container,
        { number: 7, tab: "", reader: { initial: first, fetchAfterMs: 0 } },
        {
          perf,
          ensureAsset: async () => {
            if (delayed === "inert") {
              await waiting;
            }
            window.MetabrowserInertHtml = inert;
          },
          loadKpressAssets: () => {
            assets += 1;
            return delayed === "styles" ? waiting : Promise.resolve();
          },
          ...require("./sdk-ref-fixture.js").refHelpers(document),
          formatAge: () => ({ label: "now", className: "age" }),
          formatTimestamp: () => "now",
          navigation: { href: () => "/view/" },
          sourceKind: () => "git_revision",
          icons: { toggle: "" },
        },
      );
      const body = () =>
        [...container.descendants()].find((node) => node.getAttribute("data-part") === "body");
      const poll = async () => {
        const ready = [...timers.values()];
        timers.clear();
        for (const timer of ready) {
          timer.callback();
        }
        await settle();
      };
      await settle();
      const old = body();
      assert.equal(
        old.textContent,
        "plain A",
        `${delayed}/${transition}: delayed positive control`,
      );
      if (["response", "replace", "metadata"].includes(transition)) {
        current = structuredClone(first);
        current.body.refreshing = true; // A harmless header paint must not strand the body.
        if (transition === "metadata") {
          current.body.fetched_at = "2026-09-17T12:00:01Z";
          current.body.record.fetched_at = current.body.fetched_at;
        } else {
          current.body.record_revision = "b".repeat(64);
          current.body.record.pull.body = "plain B"; // Deliberately the SAME fetched_at.
        }
        await poll();
        assert.equal(body().textContent, transition === "metadata" ? "plain A" : "plain B");
        if (transition === "metadata") {
          assert.equal(body(), old, "same content retains its actual element across a new model");
          assert.equal(markdownReads, 1, "timestamp-only refresh reuses the client Markdown cache");
        } else {
          assert.notEqual(body(), old, "changed text owns a new element");
          assert.equal(markdownReads, 2, "same-second new revision asks for its own Markdown");
        }
        if (releaseResponse) {
          releaseResponse();
          await settle();
        }
      } else if (transition === "tab") {
        handle.land({ tab: "files" });
        handle.land({ tab: "" });
        await settle();
        assert.notEqual(body(), old, "Files/Conversation remount creates its own text element");
      } else {
        handle.dispose();
      }
      release();
      await settle();
      assert.equal(assets, 1, "all admitted parts share the same stylesheet readiness promise");
      const expected =
        transition === "dispose"
          ? "plain A"
          : ["replace", "response"].includes(transition)
            ? "rendered B"
            : "rendered A";
      assert.equal(
        body().textContent,
        expected,
        `${delayed}/${transition}: only current owned HTML appears`,
      );
      handle.dispose();
    }
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
      return { body: { firstElementChild: new Element("svg") } };
    }
  };
  globalThis.fetch = async () => ({ status: 304, headers: { get: () => null } });
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const initial = recorded.current;
  for (const failure of ["assets", "render"]) {
    const readyBefore = perfEntries.filter((label) => label === "githubPull:filesReady").length;
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
        perf,
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
        ...require("./sdk-ref-fixture.js").refHelpers(document),
        formatAge: () => ({ label: "now", className: "age" }),
        formatTimestamp: () => "now",
        navigation: { href: () => "/view/" },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
      },
    );
    await settle();
    await handle.whenFilesReady();
    const title = container.querySelector(".github-pull-title-with-state");
    assert.equal(title.tag, "h1");
    const [icon, titleText] = title.children;
    assert.equal(icon.className, "github-pull-state-icon");
    assert.equal(icon.dataset.state, "open");
    assert.equal(icon.children[0].tag, "svg");
    assert.equal(icon.getAttribute("aria-hidden"), "true");
    assert.equal(icon.getAttribute("aria-label"), null);
    assert.equal(titleText.textContent, "Count to two in the app #7");
    const meta = container.querySelector(".github-pull-meta");
    assert.equal(
      title.parentNode.children.indexOf(meta),
      title.parentNode.children.indexOf(title) + 1,
    );
    const [stateBadge] = meta.children;
    assert.equal(stateBadge.getAttribute("data-state"), "open");
    assert.deepEqual(stateBadge.children, ["Open"]);
    assert.equal(stateBadge.getAttribute("aria-hidden"), null);
    assert.deepEqual(
      container
        .querySelectorAll(".tab-btn")
        .filter((tab) => tab.getAttribute("role") === "tab")
        .map((tab) => [tab.textContent, tab.getAttribute("href")]),
      [
        ["Conversation", "/pull/7"],
        ["Changes", "/pull/7/files"],
        ["Checks", "/pull/7/checks"],
      ],
    );
    assert.match(container.textContent, /Changes could not load/);
    assert.equal(
      perfEntries.filter((label) => label === "githubPull:filesReady").length,
      readyBefore,
      "failed assets and renderer rejection are not useful Files readiness",
    );
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
    assert.equal(
      perfEntries.filter((label) => label === "githubPull:filesReady").length,
      readyBefore + 1,
      "the current successful renderer reports useful DOM readiness",
    );
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
        perf,
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
        ...require("./sdk-ref-fixture.js").refHelpers(document),
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
      perf,
      ensureAsset: async () => {},
      ensureKindAssets: async () => {},
      getRegisteredView: () => {
        throw new Error("no comparison exists before Fetch");
      },
      ...require("./sdk-ref-fixture.js").refHelpers(document),
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
  globalThis.fetch = async () => ({
    status: initial.status,
    headers: { get: () => null },
    json: async () => initial.body,
  });
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
      const readyBefore = perfEntries.filter((label) => label === "githubPull:filesReady").length;
      const container = new Element("main");
      const handle = page.mountPullPage(
        container,
        { number: 7, tab: "files", reader: { initial, fetchAfterMs: 0 } },
        {
          perf,
          ensureAsset: async () => {},
          ensureKindAssets: async () => {},
          getRegisteredView: () => diffView,
          ...require("./sdk-ref-fixture.js").refHelpers(document),
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
      assert.equal(
        perfEntries.filter((label) => label === "githubPull:filesReady").length,
        readyBefore,
        "a resolved production 404/409 notice is not useful Files readiness",
      );
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
    await releasedFilesMounts(page, initial, diffView, errors);
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
    perf,
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
    ...require("./sdk-ref-fixture.js").refHelpers(document),
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
  await markdownOwnership(page);
  for (const label of [
    "githubPull:decode",
    "githubPull:render",
    "githubPull:filesRender",
    "githubPull:conversationReady",
  ]) {
    assert(perfEntries.includes(label), `the existing profiler receives ${label}`);
  }
  return {
    titleStateAndTextBadge: true,
    failedAssetsRecover: true,
    failedRenderRecovers: true,
    staleRetryIsInert: true,
    checkoutFetchIsExplicit: true,
    displayedComparisonRepair: true,
    bridgeAfterPaint: true,
    bridgeFramesOwned: true,
    hiddenReadiness: true,
    markdownOwnership: true,
  };
}
module.exports = { Element, recorded, root, settle, perf };
if (require.main === module) {
  run()
    .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
    .catch((error) => {
      process.stderr.write(`${error.stack}\n`);
      process.exitCode = 1;
    });
}
