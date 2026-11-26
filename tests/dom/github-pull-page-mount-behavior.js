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
// A status whose checks were listed when it was observed is recorded without the time they
// were listed, which is its own `observed_at`, and one whose checks were never seen
// otherwise without `moved_at`, which is none; any other value is as recorded.
function listedWhenObserved(field, value) {
  if (field !== "status" || value === null || typeof value !== "object" || !value.checks) {
    return value;
  }
  if (value.same_as !== undefined) {
    return value;
  }
  const checks = { ...value.checks };
  if (!("listed_at" in checks)) {
    checks.listed_at = value.observed_at;
  }
  if (!("moved_at" in checks)) {
    checks.moved_at = null;
  }
  return { ...value, checks };
}
for (const answer of Object.values(recorded)) {
  for (const envelope of [answer.body, answer.body?.pull]) {
    for (const field of ["record", "status", "readiness", "checks"]) {
      const holder = envelope?.[field]?.same_as;
      if (holder !== undefined) {
        // Anything kept beside the name, a status's own time, is this answer's; a dotted
        // name is a part of a part, as the time its checks were listed. Checks the held
        // status listed when it was observed are listed when this one was, unless it says.
        const { same_as: _held, ...own } = envelope[field];
        const held = listedWhenObserved(field, recorded[holder].body[field]);
        const value = { ...held };
        if (held.checks?.listed_at !== undefined && held.checks.listed_at === held.observed_at) {
          value.checks = { ...held.checks, listed_at: own.observed_at ?? held.observed_at };
        }
        for (const [name, part] of Object.entries(own)) {
          const [outer, inner] = name.split(".");
          value[outer] = inner === undefined ? part : { ...value[outer], [inner]: part };
        }
        envelope[field] = value;
      } else if (envelope?.[field] !== undefined) {
        envelope[field] = listedWhenObserved(field, envelope[field]);
      }
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
  // A class written as `className`, as the shell's painter of count summaries writes it, is
  // the element's classes, as a page's are.
  get className() {
    return [...this.classes].join(" ");
  }
  set className(value) {
    this.classes = new Set(String(value).split(" ").filter(Boolean));
  }
  get ownerDocument() {
    return globalThis.document;
  }
  // In the page while its root is a mount's container, a `main`, which stands for the
  // document here: a control taken out of the header is not (mb-9zp5).
  get isConnected() {
    let at = this;
    while (at.parentNode) {
      at = at.parentNode;
    }
    return at.tag === "main";
  }
  get childNodes() {
    return this.children;
  }
  get firstChild() {
    return this.children[0] ?? null;
  }
  get lastChild() {
    return this.children.at(-1) ?? null;
  }
  get nextSibling() {
    const peers = this.parentNode?.children ?? [];
    return peers[peers.indexOf(this) + 1] ?? null;
  }
  insertBefore(node, before) {
    if (node === before) {
      return node;
    }
    node.remove();
    const at = before === null ? this.children.length : this.children.indexOf(before);
    assert(at >= 0, "insertBefore reference belongs to its parent");
    node.parentNode = this;
    this.children.splice(at, 0, node);
    return node;
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  removeAttribute(name) {
    this.attributes.delete(name);
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
        child.remove();
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
    // A list of compounds: a class, `a[href]`, or an attribute's value with or without its
    // tag, as the page and the Markdown plugin probe a text for a diagram
    // (`pre[lang="mermaid"]`, `[data-kpress-diagram="mermaid"]`).
    const compounds = wanted.split(",").map((part) => {
      const compound = part.trim();
      const valued = /^([a-z]*)\[([a-z-]+)="([^"]*)"\]$/.exec(compound);
      if (compound === "a[href]") {
        return (node) => node.tag === "a" && node.attributes.has("href");
      }
      if (valued !== null) {
        return (node) =>
          (valued[1] === "" || node.tag === valued[1]) &&
          node.attributes.get(valued[2]) === valued[3];
      }
      return (node) => compound.startsWith(".") && node.classes.has(compound.slice(1));
    });
    return nodes.filter((node) => compounds.some((matches) => matches(node)));
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
  replaceWith(...nodes) {
    const parent = this.parentNode;
    if (!parent) {
      return;
    }
    // A node already in a tree moves, as the DOM moves it, the guide's step from where it
    // waited out of sight among them (guided-review.js).
    for (const node of nodes) {
      if (typeof node !== "string" && node !== this) {
        node.remove();
      }
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
  // Where *other* is from this node, as a document orders them (Node.compareDocumentPosition):
  // the shortcut registry numbers controls in that order, so the header's numbers here are the
  // ones a page gives them, as tests/dom/key-reveal-dom.js orders its nodes. Nodes of two
  // trees are disconnected.
  compareDocumentPosition(other) {
    const path = (node) => {
      const nodes = [];
      for (let at = node; at; at = at.parentNode) {
        nodes.unshift(at);
      }
      return nodes;
    };
    const here = path(this);
    const there = path(other);
    if (this === other) {
      return 0;
    }
    if (here[0] !== there[0]) {
      return 1;
    }
    let at = 0;
    while (at < here.length && at < there.length && here[at] === there[at]) {
      at += 1;
    }
    if (at === here.length) {
      return 16 | 4;
    }
    if (at === there.length) {
      return 8 | 2;
    }
    const siblings = here[at - 1].children;
    return siblings.indexOf(there[at]) > siblings.indexOf(here[at]) ? 4 : 2;
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
// What a page reads of a comparison is kept for the document (mb-neg9), in module state that
// outlives a mount. Each mount here is a fresh load of the page, with an empty keep, unless
// it is mountScripted's revisit in the same document, so no story takes what another kept,
// whatever order they run in (B10 of review B on #478).
const comparisonPrefetchUrl = pathToFileURL(
  path.join(root, "src/metabrowser/builtin_plugins/github/comparison-prefetch.js"),
).href;

/**
 * The pull page module at *url*, whose `mountPullPage` mounts a fresh load of the page, its
 * document's keep empty, and whose `revisitPullPage` mounts it again in the same document.
 *
 * @param {string} url
 * @returns {Promise<Record<string, any>>}
 */
async function importPage(url) {
  const page = await import(url);
  const { documentComparisons } = await import(comparisonPrefetchUrl);
  return {
    ...page,
    mountPullPage(...args) {
      documentComparisons.clear();
      return page.mountPullPage(...args);
    },
    revisitPullPage: page.mountPullPage,
  };
}

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
      window.metabrowser.fetchPluginData = (_plugin, hook, params, options) => {
        assert.equal(hook, "pull-comparison");
        if (params?.view === "types") {
          // The page's own question whether Docs has anything (`askDocs`), apart from the
          // diff's read this phase holds.
          return Promise.resolve({ type_presets: [["docs", 1, 0]], truncated: false });
        }
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
        whenIdle: require("./sdk-idle-fixture.js").whenIdle,
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
        ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
          label: "now",
          className: "age",
        })),
        formatTimestamp: () => "now",
        navigation: {
          href: () => "/view/",
          async open(target) {
            asked.push(`navigation.open /view/${target.path}`);
          },
        },
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

async function markdownOwnership() {
  for (const delayed of ["inert", "styles"]) {
    for (const transition of ["response", "replace", "metadata", "tab", "dispose"]) {
      // Kept renders and loaded styles belong to the module, so each story has its own.
      const page = await importPage(
        `${pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href}?${delayed}-${transition}`,
      );
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
          ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
            label: "now",
            className: "age",
          })),
          formatTimestamp: () => "now",
          navigation: {
            href: () => "/view/",
            async open(target) {
              asked.push(`navigation.open /view/${target.path}`);
            },
          },
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
      const holding = () =>
        [...container.descendants()]
          .find((node) => node.classes.has("github-pull-body"))
          ?.classes.has("github-pull-body-holding");
      assert.equal(
        holding(),
        true,
        `${delayed}/${transition}: the first paint waits, out of sight, for the description's Markdown`,
      );
      // The wait is bounded: past it the description paints plain.
      const [hold] = [...timers].filter(([, timer]) => timer.delay === page.DESCRIPTION_HOLD_MS);
      assert.ok(hold, `${delayed}/${transition}: the first paint's wait has its bound`);
      timers.delete(hold[0]);
      hold[1].callback();
      await settle();
      assert.equal(holding(), false, `${delayed}/${transition}: past the bound it shows`);
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
        assert.equal(body(), old, "Conversation again keeps the text element it painted");
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

// A refused text on the mounted page (review A of #527, A6, A8, and review D's D8): the
// production `refusedText` puts one notice directly after the text's plain text, a second
// refusal adds none, a text element rebuilt for the same text says it again, and a render
// that arrives later takes the notice away with the plain text. Returns what each step
// shows, as words.
async function textRefusal() {
  const page = await importPage(
    `${pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href}?text-refusal`,
  );
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
  const inert = {
    sanitizeHtml: (html) => html,
    kpressProse(html) {
      const node = document.createElement("p");
      node.textContent = html;
      return node;
    },
  };
  const record = (revision, text) => {
    const answer = structuredClone(recorded.current);
    answer.body.record_revision = revision.repeat(64);
    answer.body.record.pull.body = text;
    answer.body.record.issue_comments = [];
    answer.body.record.reviews = [];
    answer.body.record.review_comments = [];
    answer.body.record.comparison = null;
    answer.body.record.unavailable.comparison = "no_store";
    return answer;
  };
  const first = record("a", "plain A");
  let current = first;
  const refusal = (code, status) => ({
    status,
    body: {
      code,
      error: "refused",
      deadline_ms: 5000,
      remembered: false,
      number: 7,
      part: "body",
    },
  });
  // What the description's Markdown answers next. One that waits answers when the session
  // says, with what the route answers then: the route always answers, within its deadline.
  let markdown = refusal("render_deadline", 422);
  /** @type {(() => void) | null} */
  let answerWaiting = null;
  const response = (status, body) => ({
    status,
    headers: { get: () => null },
    json: async () => body,
  });
  globalThis.fetch = async (route) => {
    if (route.startsWith("/api/plugin/github/pull-markdown")) {
      return markdown === "waits"
        ? new Promise((resolve) => {
            answerWaiting = () => resolve(response(markdown.status, markdown.body));
          })
        : response(markdown.status, markdown.body);
    }
    return route.startsWith("/api/plugin/github/pull?")
      ? response(200, current.body)
      : { status: 304, headers: { get: () => null } };
  };
  const container = new Element("main");
  const handle = page.mountPullPage(
    container,
    { number: 7, tab: "", reader: { initial: first, fetchAfterMs: 0 } },
    {
      perf,
      ensureAsset: async () => {
        window.MetabrowserInertHtml = inert;
      },
      loadKpressAssets: () => Promise.resolve(),
      ...require("./sdk-ref-fixture.js").refHelpers(document),
      ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
        label: "now",
        className: "age",
      })),
      formatTimestamp: () => "now",
      navigation: { href: () => "/view/", async open() {} },
      sourceKind: () => "git_revision",
      icons: { toggle: "" },
    },
  );
  const poll = async () => {
    const ready = [...timers.values()];
    timers.clear();
    for (const timer of ready) {
      timer.callback();
    }
    await settle();
  };
  const body = () =>
    [...container.descendants()].find((node) => node.getAttribute("data-part") === "body");
  const steps = [];
  let previous = null;
  const look = (label) => {
    const element = body();
    const kids = element.children.filter((node) => typeof node !== "string");
    const plain = kids.findIndex((node) => node.classes.has("github-pull-plain"));
    const notices = kids.filter((node) => node.classes.has("github-pull-text-refused"));
    const shows = plain >= 0 ? "plain" : `rendered ${element.textContent}`;
    const notice =
      notices.length === 0
        ? "no notice"
        : `${notices.length} notice${notices.length === 1 ? "" : "s"}` +
          (plain >= 0 && kids[plain + 1] === notices[0] ? " right after it" : " elsewhere") +
          (notices[0].getAttribute("role") === "status" ? ", a status" : "") +
          `: ${notices[0].textContent}`;
    const same = previous === null ? "" : previous === element ? ", same element" : ", new element";
    previous = element;
    steps.push(`${label}: ${shows}, ${notice}${same}`);
  };
  await settle();
  // The first paint's bounded hold, if a refusal did not already end it.
  await poll();
  look("refused past the deadline");
  // A record in another state paints the description anew, and its Markdown has not
  // answered yet: the rebuilt text says why it is plain from what the page kept.
  current = record("b", "plain A");
  current.body.record.pull.state = "closed";
  markdown = "waits";
  await poll();
  look("rebuilt for another state, its Markdown not yet answered");
  current = record("c", "plain A");
  markdown = refusal("renderer_unavailable", 503);
  await poll();
  // The newer record's same text joined the render on its way (mb-d59o), which is refused
  // now; the page asks again under the newer record, which refuses it too.
  answerWaiting?.();
  await settle();
  look("a newer record, the same text refused again as unavailable");
  current = record("d", "plain A");
  markdown = {
    status: 200,
    body: {
      fetched_at: current.body.fetched_at,
      record_revision: current.body.record_revision,
      html: "rendered A",
      assets: {},
    },
  };
  await poll();
  look("a newer record whose Markdown renders");
  handle.dispose();
  return steps;
}

// What a text's links open on the mounted page (`inertProse`, `textReading`, `relinkTexts`),
// with static/repository-links.js run whole beside the GitPath codec, as the
// `repository-links` bundle carries them, and answered by the SDK's loader
// (`loadRepositoryLinks`). The allowlist is a stand-in that
// makes each link absolute against the pull request's page, as static/inert-html.js does
// (tests/dom/inert-html-session.js pins that), so a path-relative reference arrives under
// `/pull/` as github.com resolves it. At the served head, such a link opens the head's file
// in place. Away from it, it opens github.com at the head until the comparison is read, and
// then, for a file the comparison changes on either side, that file in Changes, in place
// and through the page's own `open`; an unchanged file stays on github.com. The read lands
// while Checks shows, so the description's section kept for a return to Conversation is read
// again too, once, and its link keeps its one click listener. Returns each step's links, as
// "text → href", and what each click did.
async function textLinks() {
  const page = await importPage(
    `${pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href}?text-links`,
  );
  const vm = require("node:vm");
  const sandbox = { Object, URL, TextEncoder, TextDecoder, btoa, atob, console };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  for (const name of ["git-path.js", "repository-links.js"]) {
    const file = path.join(root, "src/metabrowser/static", name);
    vm.runInContext(fs.readFileSync(file, "utf8"), sandbox, { filename: file });
  }
  const comparison = recorded.current.body.record.comparison;
  // Each pass of the links over a text, which the steps count.
  let passes = 0;
  const links = {
    ...sandbox.MetabrowserRepositoryLinks,
    enhance(...args) {
      passes += 1;
      return sandbox.MetabrowserRepositoryLinks.enhance(...args);
    },
  };
  // The allowlist's stand-in: each `<a href>` of a text's HTML becomes a link made absolute
  // against *base*, the pull request's page, an outside link as the allowlist leaves one.
  const inert = {
    sanitizeHtml(html, base, keepPathRelative) {
      return [
        ...html.matchAll(/<a href="([^"]*)"( data-metabrowser-path-relative="")?>([^<]*)<\/a>/g),
      ].map(([, href, relative, text]) => {
        const link = new Element("a");
        link.setAttribute("href", new URL(href, base).href);
        if (keepPathRelative && relative) {
          link.setAttribute("data-metabrowser-path-relative", "");
        }
        link.setAttribute("target", "_blank");
        link.setAttribute("rel", "noopener noreferrer");
        link.textContent = text;
        return link;
      });
    },
    kpressProse(nodes) {
      const prose = new Element("div");
      prose.className = "kpress-prose";
      prose.append(...nodes);
      return prose;
    },
  };
  const COMMENT = recorded.current.body.record.issue_comments[0].id;
  const texts = {
    body: [
      '<a href="https://github.com/octo/demo/pull/docs/changed.md" data-metabrowser-path-relative="">the changed guide</a>',
      '<a href="https://github.com/octo/demo/pull/docs/same.md" data-metabrowser-path-relative="">an unchanged file</a>',
      '<a href="https://github.com/octo/demo/pull/7/files">the Changes tab</a>',
    ].join(""),
    [`issue_comment/${COMMENT}`]:
      '<a href="https://github.com/octo/demo/pull/docs/before.md" data-metabrowser-path-relative="">the renamed file</a>',
  };
  // The comparison's read: one file changed in place and one renamed, whose old path a link
  // names too.
  const raw = {
    manifest: {
      files: [
        {
          id: "1",
          kind: "modified",
          old: { path: "docs/changed.md" },
          new: { path: "docs/changed.md" },
        },
        {
          id: "2",
          kind: "renamed",
          old: { path: "docs/before.md" },
          new: { path: "docs/after.md" },
        },
      ],
      totals: { files: 2, additions: 1, deletions: 1, exact: true },
      truncated: false,
    },
  };
  const steps = [];
  const plain = () => ({
    altKey: false,
    button: 0,
    ctrlKey: false,
    defaultPrevented: false,
    metaKey: false,
    shiftKey: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
  });
  // The click listeners each link was given, however many passes read it.
  const listeners = new Map();
  const addEventListener = Element.prototype.addEventListener;
  Element.prototype.addEventListener = function (name, callback) {
    if (this.tag === "a" && name === "click") {
      listeners.set(this, (listeners.get(this) ?? 0) + 1);
    }
    return addEventListener.call(this, name, callback);
  };

  /** Mount the page on Conversation with the code served at *revision*. */
  async function mount(revision) {
    const tasks = [];
    globalThis.document = {
      visibilityState: "visible",
      addEventListener() {},
      removeEventListener() {},
      createElement: (tag) => new Element(tag),
      importNode: () => new Element("svg"),
    };
    const listeners = new EventTarget();
    globalThis.window = {
      location: { pathname: "/pull/7" },
      addEventListener: listeners.addEventListener.bind(listeners),
      setTimeout(callback) {
        tasks.push(callback);
        return Symbol();
      },
      clearTimeout() {},
    };
    const body = structuredClone(recorded.current.body);
    body.record_revision = "f".repeat(64);
    body.record.pull.body = "Text links.";
    body.record.issue_comments = [{ ...body.record.issue_comments[0], body: "A comment." }];
    body.record.reviews = [];
    body.record.review_comments = [];
    globalThis.fetch = async (route) => {
      const part = new URL(route, "http://localhost").searchParams.get("part");
      if (route.startsWith("/api/plugin/github/pull-markdown") && part in texts) {
        const answer = {
          number: 7,
          fetched_at: body.fetched_at,
          record_revision: body.record_revision,
          part,
          html: texts[part],
          assets: {},
        };
        return { ok: true, status: 200, headers: { get: () => null }, json: async () => answer };
      }
      return { status: 304, headers: { get: () => null } };
    };
    const opened = [];
    const viewed = [];
    const diffView = {
      prefetch: async (asked) => (asked.right === comparison.head ? raw : null),
      summary: async () => ({ dispose() {} }),
    };
    const container = new Element("main");
    const handle = page.mountPullPage(
      container,
      {
        number: 7,
        tab: "",
        reader: { initial: { etag: null, body }, fetchAfterMs: 60_000 },
        open(route) {
          opened.push(route);
          return Promise.resolve({ status: "opened" });
        },
      },
      {
        perf,
        ensureAsset: async (name) => {
          if (name === "inert-html") {
            window.MetabrowserInertHtml = inert;
          }
        },
        // As static/plugin-sdk-views.js answers it on a repository's page: the resolver.
        loadRepositoryLinks: async () => links,
        loadKpressAssets: async () => {},
        whenIdle: require("./sdk-idle-fixture.js").whenIdle,
        ensureKindAssets: async () => {},
        loadChangedFilesTree: async () => {},
        getRegisteredView: () => diffView,
        decorateExternalLink: (anchor) => anchor,
        ...require("./sdk-ref-fixture.js").refHelpers(document),
        ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
          label: "now",
          className: "age",
        })),
        formatTimestamp: () => "now",
        repository: {
          host: "github.com",
          owner: "octo",
          name: "demo",
          branch: null,
          revision,
          served_prefix: "",
        },
        navigation: {
          href: (target) => `/view/${target.path}`,
          async open(target) {
            viewed.push(`/view/${target.path}`);
          },
        },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
      },
    );
    await settle();
    const idle = async () => {
      for (const task of tasks.splice(0)) {
        task();
      }
      await settle();
    };
    const movePin = () => listeners.dispatchEvent(new Event("metabrowser:pin-changed"));
    return { container, handle, opened, viewed, idle, movePin };
  }
  const anchors = (holder) => holder.querySelectorAll("a[href]");
  const told = (holder) =>
    anchors(holder)
      .map((link) => `${link.textContent} → ${link.getAttribute("href")}`)
      .join("; ");
  /** Click *text*'s link: what it opened in place, or that the browser follows it. */
  const click = (holder, text, mounted) => {
    const link = anchors(holder).find((anchor) => anchor.textContent === text);
    const event = plain();
    link.events.get("click")?.(event);
    const routes = mounted.opened.splice(0);
    const viewed = mounted.viewed.splice(0);
    // What a plain click opens in place is the address the link holds, as pull-route.js
    // spells a route, so a new tab and a copied link open the same.
    const spelled = routes.map(
      (route) => `/pull/${route.number}/${route.tab}${route.file ? `/${route.file}` : ""}`,
    );
    for (const address of [...spelled, ...viewed]) {
      assert.equal(address, link.getAttribute("href"), "a click opens the link's own address");
    }
    assert.equal(routes.length + viewed.length > 0, event.defaultPrevented, "opened in place");
    const opened = [...routes.map((route) => JSON.stringify(route)), ...viewed];
    return `${text}: ${event.defaultPrevented ? opened.join(", ") : "the browser follows it"}`;
  };
  const proses = (container) => container.querySelectorAll(".kpress-prose");

  // Served at the head the text describes: the head's file opens in place, before the
  // comparison is read and after.
  const atHead = await mount(comparison.head);
  const [headBody] = proses(atHead.container);
  steps.push(`served at the head: ${told(headBody)}`);
  steps.push(`  click ${click(headBody, "the changed guide", atHead)}`);
  await atHead.idle();
  steps.push(`  the comparison read: ${told(headBody)}`);
  atHead.movePin();
  assert.equal(
    anchors(headBody)[1].getAttribute("href"),
    `https://github.com/octo/demo/blob/${comparison.head}/docs/same.md`,
    "a stale pin drops view links and keeps the PR head",
  );
  steps.push(`  after the served revision moves: ${told(headBody)}`);
  atHead.handle.dispose();

  // Served away from it: github.com at the head, then Changes for a changed file.
  const away = await mount(comparison.base_commit);
  const [description, comment] = proses(away.container);
  steps.push(`served away from the head: ${told(description)}; ${told(comment)}`);
  steps.push(`  click ${click(description, "the changed guide", away)}`);
  steps.push(`  click ${click(description, "the Changes tab", away)}`);
  passes = 0;
  // The address moves first, as the shell's `open` moves it before the page's tab.
  window.location.pathname = "/pull/7/checks";
  away.handle.setTab("checks");
  await settle();
  assert.equal(description.isConnected, false, "Checks shows in the description's place");
  await away.idle();
  steps.push(
    `  the comparison read on Checks, ${passes} texts read again: ${told(description)}; ${told(comment)}`,
  );
  assert.equal(passes, 2, "the read reads each drawn text again, once");
  passes = 0;
  window.location.pathname = "/pull/7";
  away.handle.setTab("");
  await settle();
  await away.idle();
  assert.equal(description.isConnected, true, "Conversation shows the same description again");
  steps.push(`  back on Conversation, ${passes} texts read again: ${told(description)}`);
  for (const [text, holder] of [
    ["the changed guide", description],
    ["an unchanged file", description],
    ["the Changes tab", description],
    ["the renamed file", comment],
  ]) {
    steps.push(`  click ${click(holder, text, away)}`);
  }
  assert.equal(
    anchors(comment)[0].getAttribute("href"),
    `https://github.com/octo/demo/blob/${comparison.head}/docs/before.md`,
    "a renamed-away path does not select the destination diff",
  );
  const counted = [...anchors(description), ...anchors(comment)].map(
    (link) => `${link.textContent} ${listeners.get(link) ?? 0}`,
  );
  steps.push(`  click listeners: ${counted.join(", ")}`);
  for (const link of [...anchors(description), ...anchors(comment)]) {
    const inApp = link.getAttribute("href").startsWith("/");
    assert.equal(listeners.get(link) ?? 0, inApp ? 1 : 0, "an in-app link has one listener");
  }
  away.handle.dispose();
  Element.prototype.addEventListener = addEventListener;
  return steps;
}

// A text's Mermaid blocks on the mounted page (A3 of the review of #597): github.com draws
// them in a description and in comments, and so does the page, each as an image, since a
// text is untrusted. The page loads the Markdown plugin's exported host
// (`drawDiagrams`, through `mb.plugins.load`) once a text has a block, and a page with none asks
// for nothing. A folder's page draws them as a pinned revision's does: on either, each
// binding's Mermaid is the Markdown plugin's diagram frame's, whose own policy bounds what
// Mermaid loads while it lays a diagram out, never the page's (markdown/diagram-frame.js).
// A binding lasts as long as its text's section: a poll or a tab that keeps the section
// keeps it, a section the conversation drops ends it, one dropped before the plugin
// arrives never binds, and the page's end ends them all. The Markdown plugin's index.js,
// place-rendered.js, diagrams.js, and diagram-frame.js run as production code; KPress's two
// diagram modules are stubs that `ensureModule` returns, and record the placement each
// binding asks for, the figures it holds, where its Mermaid comes from, and its disposal.
// The SDK publishes no Mermaid bundle, so a frame's lease says so before any frame opens.
// Returns what each step asked and bound.
async function textDiagrams() {
  const pullPage = pathToFileURL(
    path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js"),
  ).href;
  const markdownPlugin = path.join(root, "src/metabrowser/builtin_plugins/markdown");
  const page = await importPage(`${pullPage}?text-diagrams`);
  // Loaded once up front, as the browser keeps a module: place-rendered.js imports it on the
  // first diagram, and an import from the module cache settles within the session's turns.
  await import(pathToFileURL(path.join(markdownPlugin, "diagrams.js")).href);
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
  // The allowlist is a dependency boundary here, as in markdownOwnership: a line
  // `mermaid: <source>` of a text stands for the `<pre lang="mermaid">` both sides of the
  // allowlist keep (tests/test_inert_html.py), and any other line for a paragraph.
  const inert = {
    sanitizeHtml: (html) => html,
    kpressProse(html) {
      const prose = document.createElement("div");
      prose.className = "kpress-prose";
      for (const line of String(html).split("\n")) {
        const diagram = line.startsWith("mermaid: ");
        const block = document.createElement(diagram ? "pre" : "p");
        if (diagram) {
          block.setAttribute("lang", "mermaid");
        }
        block.append(diagram ? line.slice("mermaid: ".length) : line);
        prose.append(block);
      }
      return prose;
    },
  };
  const record = (revision, description, comment) => {
    const answer = structuredClone(recorded.current);
    answer.body.record_revision = revision.repeat(64);
    answer.body.record.pull.body = description;
    answer.body.record.issue_comments[0].body = comment;
    answer.body.record.issue_comments.splice(1);
    answer.body.record.reviews = [];
    answer.body.record.review_comments = [];
    answer.body.record.comparison = null;
    answer.body.record.unavailable.comparison = "no_store";
    return answer;
  };
  let current = record("a", "No diagram here.", "Nor here.");
  const response = (status, body) => ({
    status,
    headers: { get: () => null },
    json: async () => body,
  });
  globalThis.fetch = async (route) => {
    if (route.startsWith("/api/plugin/github/pull-markdown")) {
      const part = new URL(route, "http://page").searchParams.get("part");
      const held = current.body.record;
      return response(200, {
        number: 7,
        fetched_at: current.body.fetched_at,
        record_revision: current.body.record_revision,
        part,
        html: part === "body" ? held.pull.body : held.issue_comments[0].body,
        assets: {},
      });
    }
    return route.startsWith("/api/plugin/github/pull?")
      ? response(200, current.body)
      : { status: 304, headers: { get: () => null } };
  };
  /** What the page asked to load, in order, since the last step. */
  const asked = [];
  /** Every binding KPress's stub made, in order. */
  const bound = [];
  const partOf = (node) => {
    let at = node;
    while (at && at.getAttribute?.("data-part") === null) {
      at = at.parentNode;
    }
    return at?.getAttribute?.("data-part") ?? "outside any text";
  };
  const modules = {
    "kpress-diagrams": {
      mermaidFigureFor(pre) {
        const figure = document.createElement("figure");
        figure.setAttribute("data-kpress-diagram", "mermaid");
        pre.replaceWith(figure);
        figure.append(pre);
        return figure;
      },
      initKpressDiagrams(root, options) {
        const binding = {
          part: partOf(root),
          placement: options.placement,
          figures: root.querySelectorAll('[data-kpress-diagram="mermaid"]').length,
          mermaid: "not asked",
          disposed: false,
        };
        bound.push(binding);
        // KPress asks for Mermaid once a figure needs it; the stub asks at once, to show
        // where the binding's Mermaid comes from.
        Promise.resolve(options.mermaid?.()).then(
          () => {
            binding.mermaid = "the page's";
          },
          (error) => {
            binding.mermaid =
              error.message === "The Mermaid module bundle is not published"
                ? "the diagram frame's"
                : error.message;
          },
        );
        return {
          figures: [],
          ready: Promise.resolve(),
          rerender() {},
          dispose() {
            binding.disposed = true;
          },
        };
      },
    },
    "kpress-diagram-controls": { diagramControls: () => ({}) },
  };
  // Opened by the story to hold the Markdown plugin's arrival.
  let arrives = Promise.resolve();
  const loads = [];
  // A pinned revision's page, always under the untrusted policy, unless a step serves a
  // folder's, which may have none.
  let served = "git_revision";
  const sdk = {
    perf,
    registerView() {},
    renderSourceView() {},
    ensureAsset: async () => {
      window.MetabrowserInertHtml = inert;
    },
    loadKpressAssets: () => Promise.resolve(),
    plugins: {
      load(name) {
        asked.push(`${name} plugin`);
        // The plugin's index.js registers its views on the SDK it finds, this one, and
        // its exports are the module's.
        const load = arrives.then(() => {
          window.metabrowser = sdk;
          return import(`${pathToFileURL(path.join(markdownPlugin, "index.js")).href}?pull-text`);
        });
        loads.push(load);
        return load;
      },
    },
    async ensureModule(name) {
      asked.push(name);
      return modules[name];
    },
    moduleUrl(name) {
      asked.push(`the ${name} bundle's address`);
      return null;
    },
    ...require("./sdk-ref-fixture.js").refHelpers(document),
    ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
      label: "now",
      className: "age",
    })),
    formatTimestamp: () => "now",
    navigation: { href: () => "/view/", async open() {} },
    sourceKind: () => served,
    icons: { toggle: "" },
  };
  const settled = async () => {
    await settle();
    await Promise.all(loads.splice(0));
    await settle();
  };
  const poll = async () => {
    const ready = [...timers.values()];
    timers.clear();
    for (const timer of ready) {
      timer.callback();
    }
    await settled();
  };
  /** The page the story looks at. */
  let shownIn = new Element("main");
  const mount = async () => {
    shownIn = new Element("main");
    const handle = page.mountPullPage(
      shownIn,
      { number: 7, tab: "", reader: { initial: current, fetchAfterMs: 0 } },
      sdk,
    );
    await settled();
    // The first paint's bounded hold, if the Markdown did not already end it.
    await poll();
    return handle;
  };
  const steps = [];
  const look = (label) => {
    // The blocks the page shows, and how many of them KPress's stub made a figure of.
    const blocks = shownIn.querySelectorAll('pre[lang="mermaid"]');
    const figures = blocks.filter(
      (pre) => pre.parentNode?.getAttribute("data-kpress-diagram") === "mermaid",
    );
    const shown = `${blocks.length} block${blocks.length === 1 ? "" : "s"}, ${figures.length} in a figure`;
    const loaded = asked.splice(0);
    const bindings = bound.map(
      (binding) =>
        `${binding.part} as ${binding.placement}, ${binding.figures} figure, ` +
        `Mermaid ${binding.mermaid}${binding.disposed ? ", disposed" : ""}`,
    );
    steps.push(
      `${label}: ${shown}; asked ${loaded.length === 0 ? "nothing" : loaded.join(", ")}; ` +
        `bindings ${bindings.length === 0 ? "none" : bindings.join("; ")}`,
    );
  };
  const plain = await mount();
  look("a description and a comment with no Mermaid block");
  plain.dispose();

  current = record("b", "Two boxes:\nmermaid: flowchart LR; A --> B", "mermaid: pie; a: 1");
  served = "filesystem";
  const folder = await mount();
  look("the same with Mermaid blocks, on a folder's page");
  folder.dispose();
  served = "git_revision";
  const handle = await mount();
  look("a description and a comment each with a Mermaid block");
  await poll();
  look("a poll of the same record");
  handle.land({ tab: "files" });
  handle.land({ tab: "" });
  await settled();
  look("Changes and back to Conversation");
  current = record(
    "c",
    "Two boxes, renamed:\nmermaid: flowchart LR; A --> C",
    "mermaid: pie; a: 1",
  );
  await poll();
  look("the description edited, the comment not");
  current = record("d", "No diagram any more.", "mermaid: pie; a: 1");
  await poll();
  look("the description's block taken out");
  let arrive = () => {};
  arrives = new Promise((resolve) => {
    arrive = resolve;
  });
  current = record("e", "mermaid: flowchart TD; X --> Y", "mermaid: pie; a: 1");
  const waiting = poll();
  await settle();
  current = record("f", "Plain again.", "mermaid: pie; a: 1");
  const ready = [...timers.values()];
  timers.clear();
  for (const timer of ready) {
    timer.callback();
  }
  await settle();
  arrive();
  await waiting;
  await settled();
  look("a block whose text is replaced before the Markdown plugin arrives");
  handle.dispose();
  await settled();
  look("the page ends");
  return steps;
}

// Mount the page on a recorded answer, read nothing more from the server, and return what
// it painted. `ageLabel` plays the age primitive's label for a time, so a test chooses
// which ages read the same.
async function mountOn(page, body, tab, ageLabel, more = {}) {
  globalThis.document = {
    visibilityState: "visible",
    addEventListener() {},
    removeEventListener() {},
    createElement: (tag) => new Element(tag),
    importNode: () => new Element("svg"),
  };
  // *fetchFirst* answers a route it knows, or null for the 304 every other route gets;
  // *setTimeout* is the page's timer, one that never fires unless a story says otherwise.
  const { fetchFirst, setTimeout: schedule, ...sdk } = more;
  globalThis.window = {
    location: { pathname: `/pull/${body.number}${tab ? `/${tab}` : ""}` },
    setTimeout: schedule ?? (() => Symbol()),
    clearTimeout() {},
  };
  globalThis.fetch = async (route) =>
    (await fetchFirst?.(route)) ?? { status: 304, headers: { get: () => null } };
  const container = new Element("main");
  const handle = page.mountPullPage(
    container,
    { number: body.number, tab, reader: { initial: { etag: null, body }, fetchAfterMs: 60_000 } },
    {
      perf,
      ensureAsset: async () => {},
      whenIdle: require("./sdk-idle-fixture.js").whenIdle,
      ensureKindAssets: async () => {},
      ...require("./sdk-ref-fixture.js").refHelpers(document),
      ...require("./sdk-ref-fixture.js").agesFrom(document, (seconds) => ({
        label: ageLabel(seconds),
        className: "age",
      })),
      formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
      navigation: {
        href: () => "/view/",
        async open(target) {
          asked.push(`navigation.open /view/${target.path}`);
        },
      },
      sourceKind: () => "filesystem",
      icons: { toggle: "" },
      // The resolver of a text's links, which a story that serves a repository asks for: none
      // loads here, as the SDK answers when it cannot load.
      loadRepositoryLinks: async () => null,
      ...sdk,
    },
  );
  await settle();
  return { container, handle };
}

// Guided Review's overview is the description, which shows with the guide's first answer
// once its Markdown is in, so the overview's first paint is its last (mb-7bu6). A guide that
// answers before that Markdown waits for it out of sight, and shows the moment the render
// replaces the description's plain text, whatever the guide answered: here that the
// description has no guide, as `/pull/10/guided` answers in Chrome
// (tests/dom/github-guided-review-chrome.mjs). A render that replaced the plain text without
// telling the wait left the guide out of sight for good. With *bounded*, the Markdown never
// comes: past `GUIDE_INTRODUCTION_HOLD_MS` the guide shows all the same, the description
// with its placeholder, so no render that never ends keeps the guide out of sight.
async function guideIntroduction(page, bounded = false) {
  const { GUIDE_INTRODUCTION_HOLD_MS } = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/guide-reads.js")).href
  );
  /** The page's timers that run out at the introduction's bound. */
  const bounds = [];
  const body = structuredClone(recorded.current.body);
  body.record_revision = "c".repeat(64);
  // A text of its own for each, since the page keeps the renders it has inserted.
  const said = bounded ? "Counts to three." : "Counts to two.";
  body.record.pull.body = `${said}\n\n\`\`\`guided-review\nsoftschema: {}\n\`\`\`\n`;
  body.record.issue_comments = [];
  body.record.reviews = [];
  body.record.review_comments = [];
  let releaseMarkdown = () => {};
  const markdown = new Promise((resolve) => {
    releaseMarkdown = resolve;
  });
  const answer = (value) => ({
    ok: true,
    status: 200,
    headers: { get: () => null },
    json: async () => value,
    text: async () => JSON.stringify(value),
  });
  const asked = [];
  const warned = [];
  const consoleWarn = console.warn;
  console.warn = (message) => warned.push(String(message));
  const { container, handle } = await mountOn(page, body, "guided", () => "now", {
    ensureAsset: async () => {
      window.MetabrowserInertHtml = {
        sanitizeHtml: (html) => html,
        kpressProse(html) {
          const node = document.createElement("p");
          node.textContent = html;
          return node;
        },
      };
    },
    loadKpressAssets: async () => {},
    plugins: {
      load: async () => {
        throw new Error("no diff plugin here");
      },
    },
    fetchFirst: (route) => {
      asked.push(route.split("?")[0].split("/").at(-1));
      if (route.startsWith("/api/plugin/github/pull-markdown")) {
        return markdown.then(() =>
          answer({
            number: 7,
            fetched_at: body.fetched_at,
            record_revision: body.record_revision,
            part: "body",
            html: `${said.slice(0, -1)}, rendered.`,
            assets: {},
          }),
        );
      }
      if (route.startsWith("/api/plugin/github/guided-review")) {
        return Promise.resolve(answer({ state: "absent", record_revision: body.record_revision }));
      }
      return null;
    },
    setTimeout(callback, delay) {
      if (delay === GUIDE_INTRODUCTION_HOLD_MS) {
        bounds.push(callback);
      }
      return Symbol();
    },
  });
  const guide = () =>
    [...container.descendants()].find((node) => node.classes.has("github-pull-guided-review"));
  const shownState = () => {
    const host = guide();
    const notice = host?.children.find(
      (child) =>
        typeof child !== "string" && child.tag === "p" && child.classes.has("github-pull-quiet"),
    );
    const introduction = host?.children.find(
      (child) =>
        typeof child !== "string" &&
        child.tag === "div" &&
        child.querySelector?.(".github-pull-guide-introduction") !== null,
    );
    const waiting = host?.children.some(
      (child) => typeof child !== "string" && child.classes.has("github-pull-guide-incoming"),
    );
    const text = introduction?.querySelector(".github-pull-guide-introduction");
    // A placeholder keeps the source's box out of sight (`showPending`), so it says nothing.
    const shows = text?.querySelector(".github-pull-plain-pending")
      ? "its placeholder"
      : (text?.textContent ?? "");
    return `the notice ${notice === undefined || notice.hidden ? "hidden" : `says ${notice.textContent}`}; the description ${introduction === undefined || introduction.hidden ? "hidden" : `shows ${shows}`}; a step waits out of sight ${waiting === true}`;
  };
  const steps = [];
  await settle();
  steps.push(`asked: ${[...new Set(asked)].join(", ")}`);
  steps.push(`the guide answered, its description's Markdown not yet: ${shownState()}`);
  if (bounded) {
    for (const bound of bounds.splice(0)) {
      bound();
    }
    await settle();
    steps.push(`its Markdown never comes, and the bound runs out: ${shownState()}`);
  } else {
    releaseMarkdown();
    await settle();
    steps.push(`the Markdown is inserted: ${shownState()}`);
  }
  console.warn = consoleWarn;
  handle.dispose();
  steps.push(`warned: ${warned.length}`);
  return steps;
}

// Browse code switches the pin through the diff plugin's view, whose switch is in a module
// the plugin loads on demand (builtin_plugins/diff/index.js awaits its import). The
// plugin's assets failing to load, or that module failing to, as when the server is
// restarting, is said as a failed request is, and never left as a rejection nothing
// handles, which would end this process (A3 of review A on #511).
async function switchUnavailable(page) {
  const said = [];
  for (const failure of ["the diff plugin's assets", "the switch module"]) {
    globalThis.document = {
      visibilityState: "visible",
      addEventListener() {},
      removeEventListener() {},
      createElement: (tag) => new Element(tag),
      importNode: () => new Element("svg"),
    };
    globalThis.window = {
      location: { pathname: "/pull/7" },
      setTimeout: () => Symbol(),
      clearTimeout() {},
    };
    const asked = [];
    globalThis.fetch = async (route, init = {}) => {
      if (init.method === "POST") {
        asked.push(`POST ${route.split("?")[0]}`);
      }
      return { status: 304, headers: { get: () => null } };
    };
    const container = new Element("main");
    const handle = page.mountPullPage(
      container,
      {
        number: 7,
        tab: "",
        reader: { initial: { etag: null, body: recorded.current.body }, fetchAfterMs: 60_000 },
      },
      {
        perf,
        ensureAsset: async () => {},
        whenIdle: require("./sdk-idle-fixture.js").whenIdle,
        ensureKindAssets: async () => {
          if (failure === "the diff plugin's assets") {
            throw new Error("asset failed");
          }
        },
        // As index.js's switchPin rejects when `import("./diff-view-file.js")` does.
        getRegisteredView: () => ({
          switchPin: async () => {
            throw new TypeError("Failed to fetch dynamically imported module");
          },
        }),
        ...require("./sdk-ref-fixture.js").refHelpers(document),
        ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
          label: "now",
          className: "age",
        })),
        formatTimestamp: () => "now",
        navigation: { href: () => "/view/" },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
      },
    );
    await settle();
    const browse = [...container.descendants()].find(
      (node) => node.tag === "button" && node.textContent === "Browse code",
    );
    assert.ok(browse, "Browse code is the switch: the page's pin is not the head");
    browse.events.get("click")({ preventDefault() {} });
    await settle();
    const live = [...container.descendants()].find(
      (node) => node.getAttribute("aria-live") === "polite",
    );
    said.push(
      `${failure} not loading: ${live.textContent}; asked ${asked.join(", ") || "nothing"}`,
    );
    handle.dispose();
  }
  return said;
}

// The page's tabs answer to C, G, D, and E through the SDK's shortcut surface, and its header's
// links and actions to the numbers of their places, through the same surface. The production
// shortcut registry and plugin shortcut facade (static/keyboard-shortcuts.js and
// static/plugin-shortcuts.js) load whole into a realm of their own, as `shell-tools` loads
// them, and the page's `mb.shortcuts.attach` is the facade's, as the SDK's is once it has
// loaded. Each key runs the page handle's setTab: a tab the address does not show goes
// through the route, as a click on its link does. The header keeps its tab column unless
// its first read fails (headerShape): while the record is on its way, and for an absent
// record nothing is fetching, such as a server with no GitHub repository. So the keys are
// live from first paint, as the links are. They wait while the column is out of the page,
// after a first read that failed, and return when paintHeader puts it back, badged at once
// while Shift is held; the inert stage of a retained navigation holds them; and disposal
// ends them.
async function tabKeys(page) {
  const vm = require("node:vm");
  // What the registry reads of a target: connected, enabled, not inert, and visible.
  class LiveElement extends Element {
    get isConnected() {
      let node = this;
      while (node.parentNode) {
        node = node.parentNode;
      }
      return node.connected === true;
    }
    get parentElement() {
      return this.parentNode;
    }
    get inert() {
      return this.attributes.has("inert");
    }
    hasAttribute(name) {
      return this.attributes.has(name);
    }
    checkVisibility() {
      for (let node = this; node; node = node.parentNode) {
        if (node.attributes.has("hidden")) {
          return false;
        }
      }
      return true;
    }
  }
  const listeners = [];
  const body = new LiveElement("body");
  body.connected = true;
  globalThis.document = {
    visibilityState: "visible",
    addEventListener: (type, listener) => listeners.push({ type, listener }),
    removeEventListener(type, listener) {
      const at = listeners.findIndex((entry) => entry.type === type && entry.listener === listener);
      if (at >= 0) {
        listeners.splice(at, 1);
      }
    },
    createElement: (tag) => new LiveElement(tag),
    importNode: () => new LiveElement("svg"),
    body,
  };
  const timers = new Map();
  globalThis.window = {
    location: { pathname: "/pull/7" },
    setTimeout(callback) {
      const id = Symbol();
      timers.set(id, callback);
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
  };
  let answer = recorded.pending.body;
  // A read of the record fails while this is set, as a server that cannot answer does.
  let failing = false;
  /** What a header number asked for: a request the page sent, a tab it opened, a page it
   * navigated to. Read and emptied by `numberResult`. */
  const asked = [];
  // Served with no `probe_every_s`, a current page asks for nothing by itself, so what a
  // number asked for is the number's alone; the session pins the probe asks (`probing`).
  const unprobed = () => ({ ...answer, probe_every_s: null });
  globalThis.fetch = async (route, init = {}) => {
    if (init.method === "POST") {
      asked.push(`POST ${route.split("?")[0]} ${init.body}`);
    }
    if (route.startsWith("/api/plugin/github/pull-refresh")) {
      // The refresh answers with the envelope it started from, as the route does.
      return {
        status: 202,
        headers: { get: () => null },
        json: async () => ({ refresh: "started", pull: unprobed() }),
      };
    }
    if (!route.startsWith("/api/plugin/github/pull?")) {
      return { status: 304, headers: { get: () => null } };
    }
    return failing
      ? { status: 503, headers: { get: () => null } }
      : { status: 200, headers: { get: () => null }, json: async () => unprobed() };
  };
  globalThis.window.open = (url, target, features) => {
    asked.push(`window.open ${url} ${target} ${features}`);
    return null;
  };
  const shell = {
    console,
    document: globalThis.document,
    HTMLElement: LiveElement,
    // `serialize_reserved_shell_keys()` in src/metabrowser/keymap.py, as the shell serves it.
    METABROWSER_SETTINGS: {
      RESERVED_SHELL_KEYS: Object.fromEntries([..."fphtjkuw123456789"].map((key) => [key, null])),
    },
  };
  shell.window = shell;
  vm.createContext(shell);
  for (const name of ["keyboard-shortcuts.js", "plugin-shortcuts.js"]) {
    const file = path.join(root, "src/metabrowser/static", name);
    vm.runInContext(fs.readFileSync(file, "utf8"), shell, { filename: file });
  }
  const facade = shell.MetabrowserPluginShortcuts;
  const registry = shell.MetabrowserKeyboardShortcuts.create({ document: globalThis.document });
  const detachRegistry = facade.attachShortcutRegistry(registry);
  const opened = [];
  // The diff plugin's view, whose pin switch the page's Browse code shares: the production
  // switch (diff-view-file.js), posting as builtin_plugins/diff/index.js posts.
  const { createPinSwitch } = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/diff/diff-view-file.js")).href
  );
  const pinSwitch = createPinSwitch({
    async post(selection) {
      const response = await fetch("/api/source/pin", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(selection),
      });
      return { status: response.status, body: null };
    },
    onRestored: () => () => {},
  });
  /** Mount #7 into a new container in the page; `reader` is the Pulls tab's, if any. */
  const mountPage = (reader) => {
    const target = new LiveElement("main");
    body.append(target);
    const mounted = page.mountPullPage(
      target,
      {
        number: 7,
        tab: "",
        open(route) {
          opened.push(route.tab);
        },
        reader,
      },
      {
        perf,
        ensureAsset: async () => {},
        whenIdle: require("./sdk-idle-fixture.js").whenIdle,
        ensureKindAssets: async () => {},
        getRegisteredView: () => ({ switchPin: pinSwitch.switchTo }),
        ...require("./sdk-ref-fixture.js").refHelpers(globalThis.document),
        ...require("./sdk-ref-fixture.js").agesFrom(globalThis.document, () => ({
          label: "now",
          className: "age",
        })),
        formatTimestamp: () => "now",
        navigation: {
          href: () => "/view/",
          async open(target) {
            asked.push(`navigation.open /view/${target.path}`);
          },
        },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
        shortcuts: { attach: facade.attachShortcut },
      },
    );
    return { container: target, handle: mounted };
  };
  /** Let every timer the page set run, as the time they wait for passing does. */
  const elapse = async () => {
    for (const callback of [...timers.values()]) {
      callback();
    }
    timers.clear();
    await settle();
  };
  let { container, handle } = mountPage({
    initial: { etag: null, body: answer },
    fetchAfterMs: 0,
  });
  await settle();
  const press = (key, init = {}) => {
    const event = {
      type: "keydown",
      key,
      code: "",
      altKey: false,
      ctrlKey: false,
      metaKey: false,
      shiftKey: false,
      repeat: false,
      isComposing: false,
      target: body,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...init,
    };
    for (const entry of listeners.filter((candidate) => candidate.type === "keydown")) {
      entry.listener(event);
    }
    return event.defaultPrevented;
  };
  const shown = () =>
    container
      .querySelectorAll(".tab-btn")
      .find((tab) => tab.getAttribute("aria-selected") === "true")?.textContent ?? "none";
  const keyed = () =>
    container
      .querySelectorAll(".tab-btn")
      .map((tab) => `${tab.textContent} ${tab.getAttribute("aria-keyshortcuts") ?? "none"}`);
  /** Each tab that carries a Shift badge now, as its label and its badge's key. */
  const badged = () =>
    container.querySelectorAll(".tab-btn").flatMap((tab) => {
      const badge = tab.children.find((node) => String(node.className).includes("kbd-badge"));
      const label = tab.children.filter((node) => node !== badge).join("");
      return badge ? [`${label} ${badge.textContent}`] : [];
    });
  const attached = () =>
    registry
      .snapshot("help", { includeInactive: true })
      .flatMap((group) => group.commands)
      .map((command) => command.bindings.visible.join(""))
      .join(" ");
  const live = () =>
    ["conversation", "docs", "files", "guided", "checks"].filter((id) =>
      registry.isLive(`plugin.github.pull.tab.${id}`),
    );
  /** Press `key`, and say what the page did: the route it opened, or the tab now shown. */
  const result = (key, init = {}) => {
    opened.length = 0;
    const handled = press(key, init);
    const name = `${init.ctrlKey ? "Ctrl+" : ""}${init.shiftKey ? "Shift+" : ""}${key.toUpperCase()}`;
    if (!handled) {
      return `${name}: not handled`;
    }
    return opened.length > 0
      ? `${name}: opened the ${opened[0] || "conversation"} route`
      : `${name}: showed ${shown()}`;
  };
  /** The header's numbered controls now, in order, by their text. */
  const numbered = () =>
    registry
      .liveNumbers()
      .map((control, at) => `${at + 1} ${control.textContent.trim()}`)
      .join(", ") || "none";
  /** Press a number, let the page act, and say what it asked for, or that nothing took it. */
  const numberResult = async (digit) => {
    asked.length = 0;
    const handled = press(digit);
    for (const callback of [...timers.values()]) {
      callback();
    }
    timers.clear();
    await settle();
    return handled ? `${digit}: ${asked.join("; ") || "nothing asked"}` : `${digit}: not handled`;
  };
  /** The route answers an opened tab as pull-route.js does: the address moves, and setTab. */
  const arrive = (tab) => {
    window.location.pathname = tab ? `/pull/7/${tab}` : "/pull/7";
    handle.setTab(tab);
  };

  const steps = [];
  assert.ok(container.querySelector(".tab-bar"), "the tab column is in from first paint");
  steps.push(
    `before the record, the tab column in the page: ${keyed().join(", ")}; ` +
      `live ${live().join(" ") || "none"}`,
  );
  steps.push(result("c"));
  steps.push(result("g"));
  // A click on Changes asks for the same route G does. The host shows the page there once
  // it is ready (static/pull-route.js), for the click and the key alike.
  opened.length = 0;
  globalThis.MouseEvent = class MouseEvent {};
  container
    .querySelectorAll(".tab-btn")
    .find((tab) => tab.textContent === "Changes")
    .events.get("click")({ preventDefault() {} });
  delete globalThis.MouseEvent;
  assert.deepEqual(opened, ["files"], "a click on Changes asks for the route G asks for");
  answer = recorded.current.body;
  await elapse();
  assert.ok(container.querySelector(".tab-bar"), "the record kept the tab column in");
  steps.push(`the record arrives and paintHeader keeps the column: ${keyed().join(", ")}`);
  steps.push(`live: ${live().join(" ")}`);
  // The header's links and actions are situational: numbered by their place, 1 to 9. View
  // on GitHub is the header's corner's button, which is not numbered (mb-4wqh), so Browse
  // code is 1.
  steps.push(`numbered: ${numbered()}`);
  steps.push(await numberResult("1"));
  steps.push(result("c"));
  steps.push(result("g"));
  arrive("files");
  steps.push(`the route arrives: ${shown()}`);
  // Changes numbers Browse code alone: the page has no Refresh of its own, and the
  // navigation's Refresh runs the page's `refresh` as its part (static/refresh-plan.js),
  // which names the comparison on screen.
  steps.push(`numbered on Changes: ${numbered()}`);
  /** Press the navigation's Refresh as it runs the page's, and say what the page asked for. */
  const pullsRefresh = async () => {
    asked.length = 0;
    const offered = handle.canRefresh();
    void handle.refresh();
    for (const callback of [...timers.values()]) {
      callback();
    }
    timers.clear();
    await settle();
    return `the navigation's Refresh, the page ${offered ? "offering" : "not offering"} one: ${asked.join("; ") || "nothing asked"}`;
  };
  // A refresh whose answer serves the pull request's head repaints Browse code as a link:
  // 1 now opens the code in the page, the action of this paint, where it asked the server
  // to serve the head before.
  const atHead = structuredClone(recorded.current.body);
  atHead.pin = atHead.record.pull.head.sha;
  atHead.pin_ref = "refs/pull/7/head";
  answer = atHead;
  steps.push(await pullsRefresh());
  steps.push(`numbered after a refresh serves the head: ${numbered()}`);
  steps.push(await numberResult("1"));
  // A refresh whose answer has no pin repaints the header without Browse code, and 1 then
  // reaches nothing.
  const unpinned = structuredClone(recorded.current.body);
  unpinned.pin = null;
  unpinned.pin_ref = null;
  answer = unpinned;
  steps.push(await pullsRefresh());
  steps.push(`numbered after a refresh with no pin: ${numbered()}`);
  steps.push(await numberResult("1"));
  // While a refresh runs the page offers none, so the navigation's Refresh asks it for
  // nothing. Code on the pull request's own head offers nothing more: the server follows
  // that head, so no switch to it is numbered.
  answer = atHead;
  steps.push(await pullsRefresh());
  steps.push(`numbered with the code on the head: ${numbered()}`);
  answer = { ...structuredClone(atHead), refreshing: true };
  steps.push(await pullsRefresh());
  steps.push(`while that refresh runs, the page can refresh: ${handle.canRefresh()}`);
  steps.push(await pullsRefresh());
  // The refresh ends. On Changes the page offers a refresh again; on Conversation nothing is
  // left to refresh.
  answer = atHead;
  for (const callback of [...timers.values()]) {
    callback();
  }
  timers.clear();
  await settle();
  steps.push(`once the refresh ends, the page can refresh: ${handle.canRefresh()}`);
  arrive("");
  await settle();
  steps.push(`on Conversation once the refresh ends, the page can refresh: ${handle.canRefresh()}`);
  steps.push(`numbered on Conversation once the refresh ends: ${numbered()}`);
  arrive("files");
  await settle();
  steps.push(await numberResult("2"));
  // H is the Commits tab's, so Checks is E.
  steps.push(result("h", { shiftKey: true }));
  steps.push(result("e", { shiftKey: true }));
  arrive("checks");
  steps.push(result("C", { shiftKey: true }));
  arrive("");
  steps.push(result("g", { ctrlKey: true }));
  const stage = new LiveElement("div");
  stage.setAttribute("inert", "");
  body.append(stage);
  stage.append(container);
  steps.push(`staged inert: ${result("g")}`);
  body.append(container);
  stage.remove();
  steps.push(`committed: ${result("g")}`);
  handle.dispose();
  steps.push(`disposed: ${keyed().join(", ")}; keys ${attached() || "none"}; ${result("g")}`);
  container.remove();
  // A page whose first read fails has nothing to show, and takes the column out; the read
  // that answers puts the same links back, keys and all. The reader has gone to Changes
  // meanwhile, so the record lands with no held first paint, and paintHeader's own retarget
  // of the returning links is what badges them at once while Shift is held.
  failing = true;
  ({ container, handle } = mountPage(undefined));
  await settle();
  assert.equal(container.querySelector(".tab-bar"), null, "a failed read, no tab column");
  steps.push(`a failed first read takes the column out: live ${live().join(" ") || "none"}`);
  steps.push(result("g"));
  arrive("files");
  registry.setRevealed(true);
  steps.push(`on Changes, Shift held while it is out: badges ${badged().join(", ") || "none"}`);
  failing = false;
  await elapse();
  assert.ok(container.querySelector(".tab-bar"), "the record put the tab column back");
  steps.push(`the next read answers, and the returning tabs are badged: ${badged().join(", ")}`);
  registry.setRevealed(false);
  steps.push(`the next read answers and paintHeader puts the column back: ${keyed().join(", ")}`);
  steps.push(`live: ${live().join(" ")}`);
  steps.push(result("g"));
  // Guided Review is a tab only where the description opens a `guided-review` fence, and R is its
  // key (Docs holds D): the link leads the bar when a record brings the fence,
  // and leaves it when a record no longer has one, unless it is the tab shown. The key
  // waits while the link is out of the page, and the link's return retargets it, which is
  // what badges it at once while Shift is held. The page cannot tell a block from an example
  // of one inside another fence (the server's parse can), so the example shows the tab too.
  const described = (generation, description) => {
    const next = structuredClone(recorded.current.body);
    next.record_revision = String(generation).padStart(64, "0");
    next.record.pull.body = description;
    return next;
  };
  const GUIDE = "Counts to two.\n\n```guided-review\nsoftschema: {}\n```\n";
  const EXAMPLE =
    "How to write one:\n\n````markdown\n```guided-review\nsoftschema: {}\n```\n````\n";
  // The guide asks for what draws its steps as it mounts, which this SDK lacks: what it
  // says of each is kept, so it does not read as a fault.
  const warned = [];
  const consoleWarn = console.warn;
  console.warn = (message) => warned.push(String(message));
  arrive("");
  answer = described(1, "Counts to two.");
  await elapse();
  steps.push(`no block in the description: ${keyed().join(", ")}; live ${live().join(" ")}`);
  steps.push(result("r"));
  answer = described(2, GUIDE);
  await elapse();
  steps.push(`a block in the description: ${keyed().join(", ")}; live ${live().join(" ")}`);
  steps.push(result("r"));
  arrive("guided");
  steps.push(`the route arrives: ${shown()}`);
  answer = described(3, "Counts to two.");
  await elapse();
  steps.push(`the block leaves while its tab is shown: ${keyed().join(", ")}; ${shown()}`);
  arrive("");
  await settle();
  steps.push(`back on Conversation: ${keyed().join(", ")}; ${result("r")}`);
  registry.setRevealed(true);
  answer = described(4, GUIDE);
  await elapse();
  steps.push(`the block returns while Shift is held: badges ${badged().join(", ")}`);
  registry.setRevealed(false);
  steps.push(result("r"));
  arrive("");
  answer = described(5, EXAMPLE);
  await elapse();
  steps.push(`an example of the block inside another fence: ${keyed().join(", ")}`);
  console.warn = consoleWarn;
  steps.push(
    `the guide, with no diff plugin or allowlist here, said: ${[...new Set(warned)].join("; ")}`,
  );
  handle.dispose();
  steps.push(`disposed: keys ${attached() || "none"}`);
  assert.equal(
    registry.snapshot("help", { includeInactive: true }).flatMap((group) => group.commands).length,
    0,
    "disposal leaves no plugin key in Help",
  );
  detachRegistry();
  registry.dispose();
  return steps;
}

// A check row is its badge, its plain name, its action, and its description: the action
// says where it opens, is the quiet GitHub action with a leading mark only for a GitHub
// destination, names its check for a list of links, and is absent for an address a page
// may not follow. Only an Actions link stands in for the "GitHub Actions" app.
async function checkRows(page) {
  const body = structuredClone(recorded.current.body);
  const passed = { kind: "run", bucket: "pass", status: "COMPLETED", conclusion: "SUCCESS" };
  body.checks.items.push(
    {
      ...passed,
      name: "coverage",
      details_url: "https://github.com/octo/demo/runs/123",
      app: "Codecov",
    },
    { ...passed, name: "lint", details_url: "https://ci.example/runs/2", app: "GitHub Actions" },
    { ...passed, name: "gist", details_url: "https://gist.github.com/octo/abc", app: "Gist bot" },
    {
      ...passed,
      name: "proxied",
      details_url: "https://github.com:8443/octo/demo/actions/runs/9",
      app: "Proxy",
    },
    {
      ...passed,
      name: "credentialed",
      details_url: "https://bot@github.com/octo/demo/runs/5",
      app: "Bot",
    },
    {
      kind: "status",
      bucket: "pass",
      conclusion: "SUCCESS",
      name: "legacy-ci",
      description: "Passed",
      details_url: "ftp://ci.example/7",
    },
  );
  const { container, handle } = await mountOn(page, body, "checks", () => "now");
  const list = container.querySelector(".github-pull-checks");
  assert.ok(list, "the Checks tab lists its checks");
  const rows = list.children.map((row) => {
    const [badge, space, name, ...rest] = row.children;
    assert.ok(badge.classes.has("file-header-badge"), "a row leads with its status badge");
    assert.equal(space, " ");
    assert.equal(name.tag, "span");
    assert.equal(name.getAttribute("class"), null, "the name is plain text, not a link");
    const link = rest.find((node) => node.tag === "a") ?? null;
    const detail = rest.find((node) => node.classes.has("github-pull-quiet")) ?? null;
    // A check a rule requires carries the compact Required tag right after its name.
    const required = rest.find((node) => node.classes.has("github-pull-required")) ?? null;
    assert.equal(
      rest.length,
      Number(link !== null) + Number(detail !== null) + Number(required !== null),
    );
    if (required !== null) {
      assert.equal(rest.indexOf(required), 0, "the tag follows the name it qualifies");
      assert.equal(required.textContent, "Required");
    }
    if (link !== null && detail !== null) {
      assert.equal(rest.indexOf(link), 0, "the action comes before the description");
    }
    const mark = link?.children.find(
      (node) => typeof node !== "string" && node.getAttribute("data-external-kind") !== null,
    );
    return {
      name: name.textContent,
      required: required !== null,
      action:
        link === null
          ? null
          : {
              text: link.textContent,
              href: link.getAttribute("href"),
              accessibleName: link.getAttribute("aria-label"),
              quiet: link.classes.has("github-pull-external-action"),
              mark:
                mark === undefined
                  ? null
                  : `${mark.getAttribute("data-external-kind")} ${link.children.indexOf(mark) === 0 ? "before" : "after"}`,
            },
      detail: detail?.textContent ?? null,
    };
  });
  const actions = (kind, href) => ({
    text: { actions: "View action on GitHub", github: "View on GitHub", external: "View details" }[
      kind
    ],
    href,
    quiet: kind !== "external",
    mark: kind === "external" ? null : "github before",
  });
  const job = "https://github.com/octo/demo/actions/runs/18062895276/job/";
  // `gh pr checks`'s order: the pending docs build first, then the rest as the server kept
  // them, its runs and then its commit status, then the ones added here.
  assert.deepEqual(rows, [
    {
      name: "docs",
      required: true,
      action: {
        ...actions("actions", `${job}51401654788`),
        accessibleName: "View action on GitHub: docs",
      },
      detail: null,
    },
    {
      name: "tests (3.13)",
      required: true,
      action: {
        ...actions("actions", `${job}51401654787`),
        accessibleName: "View action on GitHub: tests (3.13)",
      },
      detail: null,
    },
    {
      name: "docs/readthedocs.org:demo",
      required: false,
      action: {
        ...actions("external", "https://demo--7.org.readthedocs.build/en/7/"),
        accessibleName: "View details: docs/readthedocs.org:demo",
      },
      detail: "Read the Docs build succeeded!",
    },
    {
      name: "coverage",
      required: false,
      action: {
        ...actions("github", "https://github.com/octo/demo/runs/123"),
        accessibleName: "View on GitHub: coverage",
      },
      detail: "Codecov",
    },
    {
      name: "lint",
      required: false,
      action: {
        ...actions("external", "https://ci.example/runs/2"),
        accessibleName: "View details: lint",
      },
      detail: "GitHub Actions",
    },
    {
      name: "gist",
      required: false,
      action: {
        ...actions("github", "https://gist.github.com/octo/abc"),
        accessibleName: "View on GitHub: gist",
      },
      detail: "Gist bot",
    },
    {
      name: "proxied",
      required: false,
      action: {
        ...actions("external", "https://github.com:8443/octo/demo/actions/runs/9"),
        accessibleName: "View details: proxied",
      },
      detail: "Proxy",
    },
    {
      name: "credentialed",
      required: false,
      action: {
        ...actions("external", "https://bot@github.com/octo/demo/runs/5"),
        accessibleName: "View details: credentialed",
      },
      detail: "Bot",
    },
    { name: "legacy-ci", required: false, action: null, detail: "Passed" },
  ]);
  const names = rows.flatMap((row) => (row.action === null ? [] : [row.action.accessibleName]));
  assert.equal(new Set(names).size, names.length, "every action has its own accessible name");
  handle.dispose();
}

// The Merge status section opens the Checks tab (mb-io36): the verdict's badge and the
// requirement that heads it, then a row for each requirement, its status's badge in the tone
// its status gives a verdict, the server's sentence, and its link, then auto-merge's. The
// Checks row's link brings the first running check into view and focuses it, and only while
// the page is mounted; a merged pull request, which has no readiness, has no section. The
// section is built only when the tab shows, and kept while what it says is the same.
async function mergeStatusSection(page) {
  const body = structuredClone(recorded.current.body);
  const { container, handle } = await mountOn(page, body, "", () => "now");
  assert.equal(
    container.querySelector(".github-pull-merge-status"),
    null,
    "Conversation builds no Merge status",
  );
  handle.dispose();
  const checks = await mountOn(page, body, "checks", () => "now");
  const pane = checks.container.querySelector(".github-pull-body");
  const section = pane.children[0];
  assert.ok(section.classes.has("github-pull-merge-status"), "Merge status opens the tab");
  assert.equal(section.children[0].textContent, "Merge status");
  const verdict = section.querySelector(".github-pull-verdict");
  const [badge, sentence] = verdict.children;
  const readiness = body.readiness;
  assert.deepEqual(
    [badge.dataset.verdict, badge.dataset.tone, badge.textContent],
    [readiness.verdict, readiness.tone, readiness.label],
  );
  // The worst status among the requirements, and the first requirement at it.
  const order = ["unmet", "waiting", "unknown", "met"];
  const worst = order.find((status) =>
    readiness.requirements.some((requirement) => requirement.status === status),
  );
  assert.equal(
    sentence.textContent,
    readiness.requirements.find((requirement) => requirement.status === worst).summary,
  );
  const rows = section.querySelector(".github-pull-requirements").children;
  assert.equal(rows.length, readiness.requirements.length + 1, "and auto-merge's row");
  readiness.requirements.forEach((requirement, at) => {
    const [status, said] = rows[at].children;
    assert.equal(rows[at].getAttribute("data-kind"), requirement.kind);
    assert.equal(status.dataset.status, requirement.status);
    assert.equal(status.dataset.tone, requirement.status === "met" ? "success" : readiness.tone);
    assert.ok(said.classes.has("github-pull-requirement-said"));
    assert.equal(said.children[0].textContent, requirement.summary);
  });
  assert.equal(rows.at(-1).textContent, readiness.auto_merge_summary);
  const checksRow = rows.find((row) => row.getAttribute("data-kind") === "checks");
  const toCheck = checksRow.children[1].children.find((node) => node.tag === "a");
  assert.equal(toCheck.getAttribute("aria-label"), "View check: docs");
  const listed = pane.querySelector(".github-pull-checks").children;
  const running = listed.find((row) => row.children[2].textContent === "docs");
  assert.equal(running.getAttribute("tabindex"), "-1", "the row the link names takes focus");
  const moves = [];
  running.scrollIntoView = (options) => moves.push(`scrolled ${options.block}`);
  running.focus = (options) => moves.push(`focused, preventScroll ${options.preventScroll}`);
  let prevented = 0;
  // A plain click, as isPlainClick reads one in a browser.
  globalThis.MouseEvent = class MouseEvent {};
  const click = { button: 0, preventDefault: () => (prevented += 1) };
  toCheck.events.get("click")(click);
  assert.deepEqual(moves, ["scrolled nearest", "focused, preventScroll true"]);
  assert.equal(prevented, 1);
  // Landing on the tab again with the same readiness keeps the section it built.
  checks.handle.land({ tab: "checks" });
  assert.equal(pane.children[0], section, "the same readiness keeps its section");
  checks.handle.dispose();
  toCheck.events.get("click")(click);
  assert.equal(prevented, 1, "a link of a page that is gone does nothing");
  assert.equal(moves.length, 2);
  delete globalThis.MouseEvent;
  const merged = await mountOn(page, structuredClone(recorded.merged.body), "checks", () => "now");
  assert.equal(merged.container.querySelector(".github-pull-merge-status"), null);
  assert.equal(merged.container.querySelector(".github-pull-readiness-slot"), null);
  merged.handle.dispose();
}

// The header leaves out an updated age that reads the same as the merged or closed age
// beside it, or else the opened age, and keeps its exact time in that age's tooltip.
async function headerAges(page) {
  const said = async (name, ageLabel) => {
    const { container, handle } = await mountOn(page, recorded[name].body, "", ageLabel);
    // The ages follow the state's badge on their row (mb-4ydo).
    const line = container
      .querySelector(".github-pull-opened")
      .children.find((node) => node.classes?.has("github-pull-quiet"));
    // The ages, cut short before the link after them, Browse code where there is code to
    // browse (B4 of review B on #506). View on GitHub is not among them: it is the header's
    // corner's (mb-4wqh).
    const [agesText, links] = line.children;
    assert.ok(agesText.classes.has("github-pull-ages"));
    assert.ok(links === undefined || links.classes.has("github-pull-ages-links"));
    assert.ok(!line.textContent.includes("View on GitHub"), "no View on GitHub in the ages");
    const ages = agesText.children.filter((node) => node.classes?.has("github-pull-age"));
    handle.dispose();
    return {
      text: agesText.textContent,
      tips: ages.map((node) => node.getAttribute("data-tip-text")),
    };
  };
  const at = (iso) => Date.parse(iso) / 1000;
  const hour = (seconds) => new Date(seconds * 1000).toISOString().slice(0, 13);
  const day = (seconds) => new Date(seconds * 1000).toISOString().slice(0, 10);
  // Opened 10:57, updated 17:39; merged 18:00; closed 19:00, all on 2026-09-16.
  assert.deepEqual(await said("current", hour), {
    text: "Opened 2026-09-16T10 · updated 2026-09-16T17",
    tips: ["2026-09-16T10:57:23.000Z", "2026-09-16T17:39:01.000Z"],
  });
  assert.deepEqual(await said("current", day), {
    text: "Opened 2026-09-16",
    tips: ["2026-09-16T10:57:23.000Z · updated 2026-09-16T17:39:01.000Z"],
  });
  const late = (seconds) => (seconds >= at("2026-09-16T17:00:00Z") ? "late" : "early");
  assert.deepEqual(await said("merged", late), {
    text: "Opened early · merged late",
    tips: [
      "2026-09-16T10:57:23.000Z",
      "2026-09-16T18:00:00.000Z · updated 2026-09-16T17:39:01.000Z",
    ],
  });
  assert.deepEqual(await said("merged", day), {
    text: "Opened 2026-09-16 · merged 2026-09-16",
    tips: [
      "2026-09-16T10:57:23.000Z",
      "2026-09-16T18:00:00.000Z · updated 2026-09-16T17:39:01.000Z",
    ],
  });
  assert.deepEqual(await said("closed", hour), {
    text: "Opened 2026-09-16T10 · updated 2026-09-16T17 · closed 2026-09-16T19",
    tips: ["2026-09-16T10:57:23.000Z", "2026-09-16T17:39:01.000Z", "2026-09-16T19:00:00.000Z"],
  });
}

// The header's box is decided at first paint: the same rows, in the same order, whatever
// the pull request carries and whichever tab shows, and while its record is on its way,
// but for two. The labels row is not there for a pull request with no labels (mb-2u08); it
// is held while the record is on its way, since the record may bring labels. The status
// line is there only for a failure, a message, or an offer, and a rate limit's hold is
// said in the freshness note's place, so it adds none (mb-ne91). Each row's height is its
// stylesheet's (tests/test_reserved_chrome.py); here, that every row it shows is there, a
// hidden row left out. A stack's chip has its slot at the row of ages' end, which it ends on
// every tab (mb-646g, mb-ablv); the slot is held by a strut until a chip arrives, which holds
// the row at a chip's height, and the author's row is its lead alone. The page has no Refresh
// of its own: a status line that says what to retry or fetch ends in its remedy (mb-ablv).
// tests/dom/github-pull-header-chrome.mjs measures that a late chip moves nothing.
async function headerShape(page) {
  // The header's corner, the View on GitHub button's, is no row: it is placed in the page's
  // upper right, out of the rows' flow (mb-4wqh).
  const rows = (container) =>
    container
      .querySelector(".github-pull-header")
      .children.filter((node) => node.hidden !== true && !node.classes.has("view-header-end"))
      .map((node) =>
        node.tag === "h1"
          ? "title"
          : [...node.classes].find((name) => name.startsWith("github-pull-")).slice(12),
      );
  const age = () => "now";
  const shapes = {};
  const variants = {
    "one label": recorded.current.body,
    "no labels, a title of three lines": (() => {
      const body = structuredClone(recorded.current.body);
      body.record.pull.labels = [];
      body.record.pull.title = "A title long enough to need three lines ".repeat(6).trim();
      return body;
    })(),
    "three labels": (() => {
      const body = structuredClone(recorded.current.body);
      body.record.pull.labels = [
        { name: "bug", color: "d73a4a", description: "Something isn't working" },
        { name: "enhancement", color: "a2eeef", description: null },
        { name: "needs review", color: null, description: null },
      ];
      return body;
    })(),
    // A record cached before label colors names its labels alone; the envelope carries the
    // repository's set's entry for the one it holds (`mb-varu`).
    "labels named alone": (() => {
      const body = structuredClone(recorded.current.body);
      body.record.pull.labels = [
        { name: "bug", color: null, description: null },
        { name: "needs review", color: null, description: null },
      ];
      body.repository_labels = [
        { name: "bug", color: "d73a4a", description: "Something isn't working" },
      ];
      return body;
    })(),
    merged: recorded.merged.body,
    stale: recorded.stale.body,
    "on its way": recorded.absent.body,
    // Something to say: the last refresh failed, or the checkout is at the pull request's
    // head. Code served on that head followed it there, and says nothing. A rate limit's hold, and a server with no
    // GitHub repository, are said in the note's place.
    failed: recorded.failed.body,
    // A record still current whose last refresh failed: nothing will ask again by itself, so
    // the failure ends in Retry (mb-ablv). A stale one is asked for again, and offers none.
    "failed, still current": { ...structuredClone(recorded.failed.body), state: "current" },
    "held by a rate limit": (() => {
      const body = structuredClone(recorded.current.body);
      body.state = "stale";
      body.last_refresh = {
        outcome: "rate_limited",
        message: null,
        reset_at: "2099-01-01T00:00:00Z",
        at: "2026-09-17T12:30:00Z",
      };
      return body;
    })(),
    "followed to the head": recorded.followed_head.body,
    "a checkout at the head": (() => {
      const body = structuredClone(recorded.on_head.body);
      body.pin = null;
      body.pin_ref = null;
      return body;
    })(),
    "no GitHub repository": recorded.not_github.body,
    // No record, and its last refresh failed: the page's word goes to the status line beside
    // the failure, and the note is not there (A10 of review A, B6 of review B on #506).
    "on its way, its last refresh failed": {
      ...structuredClone(recorded.absent.body),
      last_refresh: {
        outcome: "network_error",
        message: "gh could not reach api.github.com",
        reset_at: null,
        at: "2026-09-17T12:30:00Z",
      },
    },
  };
  /** What each variant's status line says, on every tab, or null where it is not there. */
  // A failure ends in its Details, the event log's records for it (mb-9zp5).
  const STATUS = {
    failed: "Could not reach GitHub.Details",
    "failed, still current": "Could not reach GitHub.DetailsRetry",
    "a checkout at the head":
      "This checkout’s HEAD is this pull request’s head. Browse the checkout",
    "on its way, its last refresh failed":
      "Fetching the pull request…Could not reach GitHub.Details",
  };
  /** What each variant's status line offers as its remedy, or none (mb-ablv). */
  const REMEDY = {
    "failed, still current": "Retry",
  };
  /** What each variant's note says where it is not the record's fetch, null where none. */
  const NOTE = {
    "on its way, its last refresh failed": null,
    "held by a rate limit": /^GitHub rate limit reached\. Next attempt after /,
    "on its way": /^(Fetching the pull request…|This pull request has not been fetched yet\.)$/,
    "no GitHub repository": /^This server serves no GitHub repository\.$/,
  };
  const more = {
    "a checkout at the head": {
      repository: { revision: variants["a checkout at the head"].record.pull.head.sha },
    },
  };
  for (const [name, body] of Object.entries(variants)) {
    const labelled = body.record === null || body.record.pull.labels.length > 0;
    for (const tab of ["", "files", "checks"]) {
      const { container, handle } = await mountOn(page, body, tab, age, more[name]);
      const header = container.querySelector(".github-pull-header");
      const meta = container.querySelector(".github-pull-meta");
      const labels = container.querySelector(".github-pull-labels");
      const stacks = container.querySelector(".github-pull-stacks");
      const status = container.querySelector(".github-pull-status");
      const end = status.children.at(-1);
      const remedy = container.querySelector(".github-pull-remedy");
      assert.ok(end.classes.has("github-pull-status-end"), `${name} ${tab}: offers end the row`);
      const opened = container.querySelector(".github-pull-opened");
      assert.equal(
        opened.children.at(-1),
        stacks,
        `${name} ${tab}: the stack slot ends the row of ages, with no Refresh after it`,
      );
      assert.equal(
        container.querySelector(".github-pull-refresh"),
        null,
        `${name} ${tab}: the page has no Refresh of its own`,
      );
      assert.deepEqual(
        meta.children.map((node) => node.getAttribute("class")),
        ["github-pull-meta-lead"],
        `${name} ${tab}: the author's row is its lead alone`,
      );
      if (!labelled) {
        assert.equal(labels, null, `${name} ${tab}: no labels, no labels row`);
      } else {
        assert.equal(labels.children.length, 1, `${name} ${tab}: the labels row is its labels`);
      }
      if (name === "three labels") {
        // A label with GitHub's color carries it and the properties github/styles.css
        // paints it from; one with a description has it as its tooltip; one without a
        // color is the neutral chip, and one without a description has no tooltip.
        assert.deepEqual(
          container
            .querySelectorAll(".github-pull-label")
            .map((chip) => [
              chip.textContent,
              chip.getAttribute("data-color"),
              chip.getAttribute("style"),
              chip.getAttribute("data-tip-text"),
            ]),
          [
            [
              "bug",
              "d73a4a",
              "--github-label-r:215;--github-label-g:58;--github-label-b:74;--github-label-h:354;--github-label-s:66;--github-label-l:54",
              "Something isn't working",
            ],
            [
              "enhancement",
              "a2eeef",
              "--github-label-r:162;--github-label-g:238;--github-label-b:239;--github-label-h:181;--github-label-s:71;--github-label-l:79",
              null,
            ],
            ["needs review", null, null, null],
          ],
          `${tab}: each chip's color, properties, and tooltip`,
        );
      }
      if (name === "labels named alone") {
        // The one the repository's set holds is colored and titled from it on first paint.
        assert.deepEqual(
          container
            .querySelectorAll(".github-pull-label")
            .map((chip) => [
              chip.textContent,
              chip.getAttribute("data-color"),
              chip.getAttribute("data-tip-text"),
            ]),
          [
            ["bug", "d73a4a", "Something isn't working"],
            ["needs review", null, null],
          ],
          `${tab}: a label named alone takes the repository's color and description`,
        );
      }
      assert.ok(
        stacks.children.length !== 1 || stacks.children[0].classes.has("github-pull-stack-strut"),
        `${name} ${tab}: a strut holds the row of ages at a chip's height`,
      );
      assert.ok(
        stacks.children.length > 0 && !stacks.hidden,
        `${name} ${tab}: the stack slot is held while no stack is known`,
      );
      // The note ends the author's row's lead: the record's one time, or what is said in its
      // place (mb-ne91).
      const note = container.querySelector(".github-pull-note");
      const noteText = container.querySelector(".github-pull-freshness").textContent;
      assert.equal(
        note.parentNode.parentNode,
        meta,
        `${name} ${tab}: the note is on the author's row`,
      );
      if (NOTE[name] === null) {
        assert.equal(note.hidden, true, `${name} ${tab}: no note`);
      } else {
        assert.ok(note.hidden !== true, `${name} ${tab}: the note says something`);
        assert.match(
          noteText,
          NOTE[name] ?? /^Fetched .+ via GitHub CLI$/,
          `${name} ${tab}: the note`,
        );
      }
      // The status line is there exactly while it has something to say, and says it.
      assert.equal(
        status.hidden === true ? null : status.textContent,
        STATUS[name] ?? null,
        `${name} ${tab}: the status line`,
      );
      // A status line that says what to retry or fetch ends in its remedy, first among the
      // offers at its end (mb-ablv): a text action, a line tall, so the status line is a
      // metadata line (mb-2u08).
      assert.equal(
        remedy === null ? null : remedy.textContent,
        REMEDY[name] ?? null,
        `${name} ${tab}: the status line's remedy`,
      );
      if (remedy !== null) {
        assert.ok(
          remedy.classes.has("github-pull-text-action") &&
            !remedy.classes.has("btn") &&
            remedy.parentNode === end &&
            end.children[0] === remedy,
          `${name} ${tab}: the remedy is a text action, first at the status line's end`,
        );
      }
      assert.ok(
        container.querySelector(".tab-bar"),
        `${name} ${tab}: the tab bar is under the header from first paint`,
      );
      assert.equal(header.parentNode.children.indexOf(header), 0);
      shapes[`${name} ${tab || "conversation"}`] = rows(container).join(" ");
      assert.equal(
        rows(container).join(" "),
        [
          "title opened meta branches",
          ...(labelled ? ["labels"] : []),
          ...(name in STATUS ? ["status"] : []),
          // The size line, then the Diff summary under it (docs/design-system.md, "Change
          // Size Line").
          "size",
          "summary",
        ].join(" "),
        `${name} ${tab}: the header's rows`,
      );
      handle.dispose();
    }
  }
  assert.deepEqual(
    new Set(Object.values(shapes)),
    new Set([
      "title opened meta branches labels size summary",
      "title opened meta branches size summary",
      "title opened meta branches labels status size summary",
      "title opened meta branches status size summary",
    ]),
    JSON.stringify(shapes, null, 2),
  );
  // A title cut short at two lines carries the whole of it in its tooltip, and only then.
  const { container, handle } = await mountOn(page, variants["three labels"], "", age);
  const title = container.querySelector(".github-pull-title");
  const text = title.children[1];
  text.scrollHeight = 60;
  text.clientHeight = 40;
  title.events.get("pointerenter")();
  assert.equal(title.dataset.tipText, "Count to two in the app #7");
  text.scrollHeight = 40;
  title.events.get("pointerenter")();
  assert.equal(title.dataset.tipText, undefined);
  // Two lines that fit overhang their box by a descender's pixels, and are not cut short.
  text.scrollHeight = 62;
  text.clientHeight = 60;
  title.events.get("pointerenter")();
  assert.equal(title.dataset.tipText, undefined, "a whole two-line title has no tooltip");
  handle.dispose();
}

// The recorded comparison's read, one object for every mount, so a revisit drawn from the
// document's keep is told apart from another comparison's read.
const SCRIPTED_RAW = { comparison: "read" };

/**
 * The production page mounted on a scripted diff view, its pull route answering what
 * `serve` gives it, and every timer and idle callback a task that `idle` runs.
 * *read* says whether the prefetch's read of a comparison answers or fails, and *summary*
 * whether the diff view's summary draws or declines. *diff* says what the Changes diff does
 * with each comparison it is asked to draw, by its head and the how-manyth render it is:
 * reads it, reads nothing, throws, which offers the page's Retry, or is still reading.
 * *body* is the record in hand, and *cold* mounts it with none, as a direct load does.
 * *markdown* "waits" holds the description's Markdown unanswered. *revisit* mounts it again
 * in the same document, keeping what earlier mounts read; any other mount is a fresh load,
 * with an empty keep (`importPage`). *hidden* opens it out of sight, which `show` brings
 * into view. With *routes*, the page opens its routes as pull-route.js's `open` answers.
 *
 * @param {Record<string, any>} page
 * @param {string} tab
 * @param {{read?: "answers" | "fails", summary?: "draws" | "declines", diff?: "reads" | "fails" | ((right: string, attempt: number) => "reads" | "fails" | "throws" | "waits"), body?: unknown, cold?: boolean, markdown?: "waits", revisit?: boolean, hidden?: boolean, routes?: boolean}} [options]
 */
async function mountScripted(page, tab, options = {}) {
  const tasks = [];
  const listeners = [];
  globalThis.document = {
    // A page opened out of sight, which `show` brings into view.
    visibilityState: options.hidden ? "hidden" : "visible",
    addEventListener(type, callback) {
      listeners.push({ type, callback });
    },
    removeEventListener() {},
    createElement: (tag) => new Element(tag),
    importNode: () => new Element("svg"),
  };
  globalThis.window = {
    location: { pathname: `/pull/7${tab ? `/${tab}` : ""}` },
    setTimeout: (callback) => {
      tasks.push(callback);
      return Symbol();
    },
    clearTimeout() {},
  };
  // The pull route answers what `serve` last gave it, or `poll`'s answer once, and nothing
  // new before that.
  let served = null;
  let polled = null;
  // A description's Markdown never answers when *markdown* waits, so a held first paint
  // runs to its bound, which `idle` runs too.
  globalThis.fetch = async (route) => {
    if (options.markdown === "waits" && route.startsWith("/api/plugin/github/pull-markdown")) {
      return new Promise(() => {});
    }
    if (route.startsWith("/api/plugin/github/pull-files-summary?")) {
      // The cached list's sums, which *brief* names, for the brief line (mb-z8ea).
      steps.briefReads.push(route);
      const rows = options.brief === undefined ? [] : [options.brief];
      if (options.briefGate !== undefined) {
        await options.briefGate;
      }
      return {
        ok: true,
        status: 200,
        headers: { get: () => null },
        json: async () => ({ source: recorded.current.body.source, rows }),
      };
    }
    const body = route.startsWith("/api/plugin/github/pull?") ? (polled ?? served) : null;
    if (body === polled) {
      polled = null;
    }
    return body !== null
      ? { status: 200, headers: { get: () => null }, json: async () => body }
      : { status: 304, headers: { get: () => null } };
  };
  // The recorded comparison's read is `raw`; another's says its head's first seven digits.
  const raw = SCRIPTED_RAW;
  const shown = recorded.current.body.record.comparison.head;
  // The heads whose read the server refuses.
  const refused = new Set();
  const steps = {
    summaries: [],
    renders: [],
    reads: 0,
    opened: [],
    jumps: [],
    openFile: null,
    markdown: [],
    briefReads: [],
  };
  const diffDoes =
    typeof options.diff === "function" ? options.diff : () => options.diff ?? "reads";
  const diffView = {
    prefetch: async (comparison) => {
      steps.reads += 1;
      if (options.read === "fails" || refused.has(comparison.right)) {
        throw new Error("refused");
      }
      return comparison.right === shown ? raw : { comparison: comparison.right.slice(0, 7) };
    },
    // The first screen's rendered Markdown, which the page asks for itself (mb-neg9).
    prefetchMarkdown: async (comparison, read, signal) => {
      steps.markdown.push({
        rendered: typeof comparison.rendered_route,
        read: read === raw,
        signal,
      });
    },
    summary: async (slot, ctx) => {
      const said = ctx.raw === raw ? "the comparison read" : ctx.raw.comparison;
      steps.summaries.push(said);
      steps.openFile = ctx.openFile;
      if (options.summary === "declines") {
        return null;
      }
      const header = new Element("button");
      header.className = "diff-summary diff-summary-toggle";
      header.classes.add("diff-summary");
      header.textContent = said;
      slot.append(header);
      return { dispose: () => steps.summaries.push(`disposed ${said}`) };
    },
    render: async (_host, ctx) => {
      const does = diffDoes(ctx.comparison.right, steps.renders.length);
      steps.renders.push({ summary: ctx.summary, onDocument: typeof ctx.onDocument });
      if (does === "throws") {
        throw new Error("the diff could not load");
      }
      if (does === "waits") {
        return new Promise(() => {});
      }
      if (does === "reads") {
        ctx.onDocument?.(raw);
      }
      return {
        dispose() {},
        scrollToFile(path) {
          steps.jumps.push(path);
          return { kind: "jumped", path };
        },
      };
    },
  };
  const container = new Element("main");
  let handle = null;
  const mountPage = options.revisit === true ? page.revisitPullPage : page.mountPullPage;
  handle = mountPage(
    container,
    {
      number: 7,
      tab,
      reader: options.cold
        ? null
        : {
            initial: { etag: null, body: options.body ?? recorded.current.body },
            fetchAfterMs: 60_000,
          },
      // With *routes*, the route opener as pull-route.js's `open` answers: a route whose file
      // it cannot spell, as one with a backslash, is refused, and a tab of the page shown is
      // set.
      ...(options.routes
        ? {
            open: (route) => {
              steps.opened.push(route);
              if (route.file?.includes("\\")) {
                return Promise.reject(new Error("the route cannot spell this path"));
              }
              window.location.pathname = `/pull/7/${route.tab}`;
              handle.setTab(route.tab);
              return Promise.resolve({ status: "opened" });
            },
          }
        : {}),
    },
    {
      perf,
      ensureAsset: async () => {},
      whenIdle: require("./sdk-idle-fixture.js").whenIdle,
      ensureKindAssets: async () => {},
      loadChangedFilesTree: async () => {},
      getRegisteredView: () => diffView,
      ...require("./sdk-ref-fixture.js").refHelpers(document),
      ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
        label: "now",
        className: "age",
      })),
      formatTimestamp: () => "now",
      navigation: { href: () => "/view/", async open() {} },
      sourceKind: () => "filesystem",
      icons: { toggle: "" },
      // With *mountCounterpart*, the SDK's View on GitHub button (plugin-sdk-views.js);
      // without, an SDK that has none.
      ...(options.mountCounterpart === undefined
        ? {}
        : { mountCounterpart: options.mountCounterpart }),
      // With *sdk*, more of the SDK, or a part of it replaced: the event log's reporter.
      ...(options.sdk ?? {}),
      // With *brief*, the change line's builder, the shell's own, so the line says what the
      // page's does (mb-ox6a), its painter, as text, and the tree's breakdown, so the page
      // draws the cached list's brief line (mb-z8ea).
      ...(options.brief === undefined && options.briefPainters !== true
        ? {}
        : {
            formatInteger: (value) => value.toLocaleString("en-US"),
            countPartsNodes: (parts) =>
              parts.map((part) =>
                typeof part === "string"
                  ? part
                  : part.separator === undefined
                    ? part.number
                    : ` ${part.separator} `,
              ),
            changeLine: require("./changed-files-tree-fixture.js").shellPainters().changeLine,
            changeLineNodes: (line) => [line.text],
            loadChangedFilesTree: async () => ({
              statusBreakdown: (statuses) => {
                const counts = new Map();
                for (const status of statuses) {
                  counts.set(status, (counts.get(status) ?? 0) + 1);
                }
                return [...counts].map(([status, count]) => ({
                  status,
                  count,
                  word: status,
                  letter: status[0].toUpperCase(),
                }));
              },
            }),
          }),
    },
  );
  await settle();
  const row = () => container.querySelector(".github-pull-summary");
  // The timers run at once; awaited, so do the answers they started.
  const idle = async () => {
    for (const task of tasks.splice(0)) {
      task();
    }
    await settle();
  };
  /** The pull route answers *body* from the next poll on, which `idle` runs. */
  const serve = (body) => {
    served = body;
  };
  /** The next poll answers with *body*, once, and the timers run until it has. */
  const poll = async (body) => {
    polled = body;
    await idle();
  };
  /** A page opened out of sight is shown. */
  const show = async () => {
    document.visibilityState = "visible";
    for (const { type, callback } of listeners) {
      if (type === "visibilitychange") {
        callback();
      }
    }
    await idle();
  };
  return { handle, row, steps, idle, serve, poll, show, refused, container };
}

// The page has no Refresh of its own (mb-ablv): a status line that says what to retry or
// fetch ends in its remedy, Retry or Fetch, which runs what the navigation's Refresh runs of
// the page. A pressed Retry waits, muted, until the refresh it asked for runs, and its failure
// and it then go. Each step says the status line, its remedy, whether the note shows, what
// the page asked the server, and whether the page offers the navigation's Refresh one.
async function statusRemedies(page) {
  const steps = [];
  const posts = [];
  /** @type {((answer: unknown) => void) | null} */
  let reply = null;
  const mount = async (body, reader) => {
    globalThis.document = {
      visibilityState: "visible",
      addEventListener() {},
      removeEventListener() {},
      createElement: (tag) => new Element(tag),
      importNode: () => new Element("svg"),
    };
    globalThis.window = {
      location: { pathname: `/pull/${body.number}` },
      setTimeout: () => Symbol(),
      clearTimeout() {},
    };
    globalThis.fetch = async (route, options = {}) => {
      if (options.method === "POST") {
        posts.push(`POST ${route} ${options.body}`);
        return new Promise((resolve) => {
          reply = resolve;
        });
      }
      return route.startsWith("/api/plugin/github/pull?")
        ? { status: 200, headers: { get: () => null }, json: async () => body }
        : { status: 304, headers: { get: () => null } };
    };
    const container = new Element("main");
    const handle = page.mountPullPage(
      container,
      {
        number: body.number,
        tab: "",
        ...(reader ? { reader: { initial: { etag: null, body }, fetchAfterMs: 60_000 } } : {}),
      },
      {
        perf,
        ensureAsset: async () => {},
        whenIdle: require("./sdk-idle-fixture.js").whenIdle,
        ensureKindAssets: async () => {},
        ...require("./sdk-ref-fixture.js").refHelpers(document),
        ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
          label: "now",
          className: "age",
        })),
        formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
        navigation: { href: () => "/view/", async open() {} },
        sourceKind: () => "filesystem",
        icons: { toggle: "" },
      },
    );
    await settle();
    return { container, handle };
  };
  const say = ({ container, handle }, what) => {
    const status = container.querySelector(".github-pull-status");
    const remedy = container.querySelector(".github-pull-remedy");
    const note = container.querySelector(".github-pull-note");
    const waiting = remedy?.getAttribute("aria-disabled") === "true" ? " (waiting)" : "";
    steps.push(
      `${what}: status ${status.hidden ? "none" : `"${status.textContent}"`}; ` +
        `remedy ${remedy === null ? "none" : `${remedy.textContent}${waiting}`}; ` +
        `note ${note.hidden ? "none" : "shown"}; ` +
        `asked ${posts.splice(0).join(", ") || "nothing"}; ` +
        `Refresh ${handle.canRefresh() ? "may refresh it" : "has nothing to refresh"}`,
    );
  };
  // A record still current whose last refresh failed: nothing will ask again by itself, so
  // the failure ends in Retry.
  const failed = { ...structuredClone(recorded.failed.body), state: "current" };
  const current = await mount(failed, true);
  say(current, "a current record whose last refresh failed");
  const retry = current.container.querySelector(".github-pull-remedy");
  retry.events.get("click")();
  await settle();
  say(current, "Retry pressed, its refresh not yet started");
  retry.events.get("click")();
  await settle();
  say(current, "Retry pressed again while it waits");
  reply({
    status: 202,
    headers: { get: () => null },
    json: async () => ({ pull: { ...structuredClone(failed), refreshing: true } }),
  });
  await settle();
  say(current, "the refresh runs");
  current.handle.dispose();
  // A pull request not fetched yet, opened by a direct link after its last fetch failed: the
  // page's word goes to the status line with the failure, and ends in Fetch.
  const unfetched = {
    ...structuredClone(recorded.absent.body),
    last_refresh: {
      outcome: "network_error",
      message: "gh could not reach api.github.com",
      reset_at: null,
      at: "2026-09-17T12:30:00Z",
    },
  };
  const direct = await mount(unfetched, false);
  say(direct, "a direct link to a pull request whose fetch failed");
  direct.container.querySelector(".github-pull-remedy").events.get("click")();
  await settle();
  say(direct, "Fetch pressed");
  direct.handle.dispose();
  // A saved copy from another version: nothing fails, and the page's word ends in Fetch.
  const other = {
    ...structuredClone(recorded.absent.body),
    reason: "schema_mismatch",
  };
  const otherVersion = await mount(other, false);
  say(otherVersion, "a direct link to a copy saved by another version");
  otherVersion.handle.dispose();
  return steps;
}

// A Diff summary that has not arrived at the event log's late threshold, and a refresh that
// failed, each offer the event log's Details (mb-9zp5): the owner saw a summary still loading
// after many seconds and had no way to tell slow from stuck, nor a record of it. The reporter
// (static/event-reports.js, run by tests/dom/event-reports-session.js) is stood in for: the
// waits the page names, how each ends, and the records it asks the Details for are told, in
// order, for the golden.
async function eventLogDetails(page) {
  const told = [];
  const waits = [];
  const assets = [];
  const reports = {
    page: "k3v9q2zx",
    lateMs: 10_000,
    failureWindowS: 3600,
    wait(name, options) {
      const wait = { name, options, ended: [] };
      waits.push(wait);
      return { end: (outcome) => wait.ended.push(outcome) };
    },
    async showDetails(panel, query, options) {
      told.push(
        `Details asked for ${JSON.stringify(query)}, abortable ${options.signal !== undefined}`,
      );
      panel.replaceChildren("Still running: checkout._pull_job for 61.0 s");
    },
  };
  const sdk = {
    eventReports: reports,
    ensureAsset: async (name) => {
      assets.push(name);
    },
  };
  const waited = () =>
    waits
      .map(({ name, options, ended }) =>
        [
          name,
          JSON.stringify(options.detail),
          typeof options.startedAt === "number" ? "timed from its start" : "untimed",
          ended.length === 0 ? "running" : `ended ${ended.join(", ")}`,
        ].join(" "),
      )
      .join("; ");
  const holds = (row) =>
    row.children.length === 1
      ? row.children[0].classes.has("github-pull-summary-pending")
        ? "the pending placeholder"
        : row.children[0].classes.has("github-pull-summary-late")
          ? `the late line "${row.children[0].textContent}"`
          : row.children[0].classes.has("diff-summary")
            ? "the summary"
            : "another node"
      : `${row.children.length} nodes`;
  const tell = (step, mounted) => told.push(`${step}: ${holds(mounted.row())}; ${waited()}`);

  // A wait that runs late, its Details opened and closed, and the page left before it ends.
  const stuck = await mountScripted(page, "", { sdk });
  const header = stuck.row().parentNode;
  tell("mounted, the comparison not yet read", stuck);
  assert.deepEqual(
    assets.filter((name) => name === "event-reports"),
    ["event-reports"],
    "the reporter is asked for once, on demand",
  );
  waits[0].options.onLate(10_000);
  tell("still waiting at the late threshold", stuck);
  const late = stuck.row().children[0];
  assert.equal(late.getAttribute("role"), "status", "the late line is announced");
  const toggle = late.querySelector(".github-pull-details-toggle");
  assert.equal(toggle.tag, "button", "Details is a button, so it takes focus and Enter");
  assert.equal(toggle.getAttribute("type"), "button");
  assert.equal(toggle.getAttribute("aria-controls"), "github-pull-details-7");
  const expanded = () => toggle.getAttribute("aria-expanded");
  assert.equal(expanded(), "false");
  toggle.events.get("click")();
  await settle();
  const panel = header.querySelector(".event-log-details");
  assert.equal(header.children.at(-1), panel, "the panel is the header's last row while open");
  assert.equal(panel.getAttribute("role"), "region");
  assert.equal(panel.getAttribute("id"), "github-pull-details-7");
  told.push(`Details opened: expanded ${expanded()}; the panel says "${panel.textContent}"`);
  toggle.events.get("click")();
  told.push(
    `Details closed: expanded ${expanded()}; panel in the header ${panel.parentNode === header}`,
  );
  toggle.events.get("click")();
  await settle();
  stuck.handle.dispose();
  told.push(
    `the page left: panel in the header ${panel.parentNode === header}; expanded ${expanded()}; ${waited()}`,
  );

  // A wait that runs late and then ends: the summary takes the late line's place, and the
  // Details it offered close with it.
  waits.length = 0;
  const slow = await mountScripted(page, "", { sdk });
  waits[0].options.onLate(10_000);
  tell("another page, late", slow);
  const slowToggle = slow.row().querySelector(".github-pull-details-toggle");
  slowToggle.events.get("click")();
  await settle();
  const slowPanel = slow.container.querySelector(".event-log-details");
  await slow.idle();
  tell("its comparison read, its Details open", slow);
  told.push(
    `the late line's Details: expanded ${slowToggle.getAttribute("aria-expanded")}; panel in the header ${slowPanel.parentNode !== null}`,
  );
  slow.handle.dispose();

  // A wait that ends before its threshold is ended, and never late.
  waits.length = 0;
  const quick = await mountScripted(page, "", { sdk });
  await quick.idle();
  tell("a page whose comparison is read at once", quick);
  quick.handle.dispose();

  // A failed refresh's Details read the window before it ended, to a minute after.
  const failed = await mountOn(page, recorded.failed.body, "", () => "now", sdk);
  const status = failed.container.querySelector(".github-pull-status");
  const failureToggle = status.querySelector(".github-pull-details-toggle");
  assert.equal(failureToggle.getAttribute("data-details"), "failure");
  told.push(
    `a failed refresh, ended ${recorded.failed.body.last_refresh.at}: "${status.textContent}"`,
  );
  failureToggle.events.get("click")();
  await settle();
  assert.equal(failureToggle.getAttribute("aria-expanded"), "true");
  failed.handle.dispose();

  // With no reporter, as on a page that cannot load it, Details says so.
  const bare = await mountOn(page, recorded.failed.body, "", () => "now");
  const bareToggle = bare.container.querySelector(".github-pull-details-toggle");
  bareToggle.events.get("click")();
  await settle();
  told.push(`no reporter: "${bare.container.querySelector(".event-log-details").textContent}"`);
  bare.handle.dispose();
  return told;
}

// The pull request's Diff summary is the header's last row, on every tab (mb-pb35). Its row
// is held, empty, from first paint; the page draws the summary in it from the comparison the
// prefetch reads, through the diff view's `summary`, once per comparison; the Changes diff
// draws none of its own (`summary: false`) and hands the page what it read
// (`onDocument`), which draws nothing more for the same comparison; on Checks the
// comparison is read for it too; and the page's disposal disposes it. The summary's own
// header and tree are the diff plugin's, pinned in tests/dom/diff-summary-session.js.
// The header's Diff summary row (mb-pb35), and what it holds while it waits (mb-onr2): the
// shell's pending placeholder while a comparison is on its way, from the first paint of a
// page whose read will bring one (mb-30dz), a core preview whose selected read prepares it,
// or a record whose comparison the page asked to prepare, through the read of the
// comparison the record names, on Changes the mounted diff's; the summary
// in its place once read; and nothing once a read draws none, until a read of the same
// comparison starts again, so a placeholder never outlives its wait and every wait has one.
// Each state the row passes through is told, in order, for the golden.
async function headerSummary(page) {
  const mount = (tab, options) => mountScripted(page, tab, options);
  /** What the row holds: the placeholder, a summary, or nothing. */
  const holds = (row) => {
    if (row.children.length === 0) {
      return "nothing";
    }
    const [only] = row.children;
    if (row.children.length === 1 && only.classes.has("github-pull-summary-pending")) {
      // The shell's primitives: the quiet period's reveal, and in it the tally's block.
      assert.ok(only.classes.has("mb-delayed-loading"), "shown after the quiet period");
      assert.equal(only.getAttribute("role"), "status");
      assert.equal(only.getAttribute("aria-label"), "Loading the summary of changes");
      assert.equal(only.children.length, 1);
      assert.ok(only.children[0].classes.has("tally-pending"), "the navigation tally's block");
      assert.equal(only.children[0].getAttribute("aria-hidden"), "true");
      return "the pending placeholder";
    }
    if (row.children.length === 1 && only.classes.has("diff-summary")) {
      return "the summary";
    }
    return `${row.children.length} other nodes`;
  };
  const told = [];
  const tell = (step, row) => told.push(`${step}: ${holds(row)}`);

  const conversation = await mount("");
  const header = conversation.row().parentNode;
  assert.equal(header.children.at(-1), conversation.row(), "the summary ends the header");
  assert.ok(conversation.row().classes.has("metabrowser-diff-host"), "with the diff's styles");
  tell("Conversation, the comparison not yet read", conversation.row());
  const placeholder = conversation.row().children[0];
  // A repaint while the comparison is on its way keeps the placeholder, so its quiet period
  // and pulse run once. Landing again on the tab shown repaints nothing, as the controller
  // skips a model it has painted; a switch of tab repaints the page and runs no timer, so
  // the comparison is still unread (B9 of review B on #478).
  const paints = () => perfEntries.filter((label) => label === "githubPull:render").length;
  const paintsBefore = paints();
  window.location.pathname = "/pull/7/checks";
  conversation.handle.land({ tab: "checks" });
  await settle();
  window.location.pathname = "/pull/7";
  conversation.handle.land({ tab: "" });
  await settle();
  assert.equal(paints(), paintsBefore + 2, "each switch of tab repaints the page");
  assert.equal(conversation.steps.reads, 0, "the comparison is still on its way");
  assert.equal(conversation.row().children[0], placeholder, "a repaint keeps the placeholder");
  conversation.idle();
  await settle();
  assert.deepEqual(conversation.steps.summaries, ["the comparison read"]);
  tell("the comparison read", conversation.row());
  // Once idle again, the page asks for the first screen's Markdown itself, apart from the
  // comparison the document keeps, under a signal of its own that its leaving aborts.
  assert.equal(conversation.steps.markdown.length, 0, "Markdown asked for before idle");
  conversation.idle();
  await settle();
  const [markdownAsk] = conversation.steps.markdown;
  assert.equal(conversation.steps.markdown.length, 1, "the first screen's Markdown asked once");
  assert.deepEqual(
    [markdownAsk.rendered, markdownAsk.read, markdownAsk.signal.aborted],
    ["string", true, false],
  );
  window.location.pathname = "/pull/7/files";
  conversation.handle.land({ tab: "files" });
  await settle();
  assert.deepEqual(conversation.steps.renders, [{ summary: false, onDocument: "function" }]);
  assert.deepEqual(conversation.steps.summaries, ["the comparison read"], "drawn once");
  tell("Changes", conversation.row());
  conversation.handle.dispose();
  assert.deepEqual(conversation.steps.summaries, [
    "the comparison read",
    "disposed the comparison read",
  ]);
  assert.equal(markdownAsk.signal.aborted, true, "a page that went left its Markdown asked for");

  const checks = await mount("checks");
  tell("Checks, the comparison not yet read", checks.row());
  checks.idle();
  await settle();
  assert.deepEqual(checks.steps.summaries, ["the comparison read"], "read for it on Checks too");
  tell("Checks, the comparison read", checks.row());
  checks.handle.dispose();

  const revisit = await mount("", { revisit: true });
  assert.deepEqual(revisit.steps.summaries, ["the comparison read"], "drawn from the keep");
  assert.equal(revisit.steps.reads, 0, "a revisit read its comparison again");
  tell("the same pull request again in this document, before any idle", revisit.row());
  revisit.handle.dispose();

  // A poll that brings a new comparison draws its summary in place of the old one. A read of
  // it that is refused empties the row, at its held height, rather than leave the old
  // comparison's counts there as the new one's, and the next paint asks again (A1 of review A
  // on #470).
  const shownHead = recorded.current.body.record.comparison.head;
  const polledBody = structuredClone(recorded.current.body);
  const polledHead = "e".repeat(40);
  polledBody.record.comparison.head = polledHead;
  polledBody.record.pull.head.sha = polledHead;
  polledBody.comparison_route = polledBody.comparison_route.replace(
    `right=${shownHead}`,
    `right=${polledHead}`,
  );
  const polling = await mount("");
  await polling.idle();
  assert.equal(polling.row().textContent, "the comparison read");
  polling.refused.add(polledHead);
  await polling.poll(polledBody);
  await polling.idle();
  assert.equal(polling.row().children.length, 0, "a refused read of the new comparison empties it");
  assert.deepEqual(polling.steps.summaries, [
    "the comparison read",
    "disposed the comparison read",
  ]);
  polling.refused.delete(polledHead);
  window.location.pathname = "/pull/7/checks";
  polling.handle.land({ tab: "checks" });
  await polling.idle();
  assert.equal(polling.row().textContent, "eeeeeee", "the next paint reads it again, and draws it");
  const switched = await mount("");
  await switched.idle();
  await switched.poll(polledBody);
  await switched.idle();
  assert.equal(switched.row().textContent, "eeeeeee", "an accepted read replaces the old summary");
  assert.deepEqual(switched.steps.summaries, [
    "the comparison read",
    "eeeeeee",
    "disposed the comparison read",
  ]);
  polling.handle.dispose();
  switched.handle.dispose();

  // A page opened out of sight reads nothing until it is shown, and then draws its summary on
  // Checks as on Conversation (A2 of review A on #470).
  for (const tab of ["", "checks"]) {
    const behind = await mount(tab, { hidden: true });
    await behind.idle();
    assert.deepEqual(behind.steps.summaries, [], "a hidden page reads nothing");
    await behind.show();
    assert.deepEqual(behind.steps.summaries, ["the comparison read"], `shown on "${tab}"`);
    assert.equal(behind.row().children.length, 1);
    behind.handle.dispose();
  }

  // A press on a file in the summary opens Changes at the file's address; a file with no
  // address, pressed on Conversation, where no diff is mounted, opens Changes and goes to the
  // file once its diff mounts (A8 of review A on #470).
  const pressed = await mount("", { routes: true });
  await pressed.idle();
  pressed.steps.openFile("docs/notes.md");
  assert.deepEqual(pressed.steps.opened.at(-1), {
    number: 7,
    tab: "files",
    file: "docs/notes.md",
    replace: false,
    jumped: false,
  });
  window.location.pathname = "/pull/7";
  pressed.handle.land({ tab: "" });
  await settle();
  pressed.steps.openFile("docs\\notes.md");
  await settle();
  assert.deepEqual(pressed.steps.opened.slice(-2), [
    { number: 7, tab: "files", file: "docs\\notes.md", replace: false, jumped: false },
    { number: 7, tab: "files", replace: false, jumped: false },
  ]);
  assert.deepEqual(pressed.steps.jumps, ["docs\\notes.md"], "the diff goes to it once mounted");
  pressed.handle.dispose();
  const changes = await mount("files");
  await settle();
  assert.deepEqual(changes.steps.renders, [{ summary: false, onDocument: "function" }]);
  assert.deepEqual(changes.steps.summaries, ["the comparison read"], "from what Changes read");
  tell("opened on Changes, from what its diff read", changes.row());
  changes.handle.dispose();

  // Changes read its comparison through the document's keep, so Conversation draws it next.
  const afterChanges = await mount("", { revisit: true });
  assert.deepEqual(afterChanges.steps.summaries, ["the comparison read"], "drawn from the keep");
  assert.equal(afterChanges.steps.reads, 0, "a visit after Changes read its comparison again");
  tell("opened again on Conversation after Changes, before any idle", afterChanges.row());
  afterChanges.handle.dispose();

  const refused = await mount("", { read: "fails" });
  tell("a read that will fail, not yet answered", refused.row());
  refused.idle();
  await settle();
  assert.deepEqual(refused.steps.summaries, []);
  tell("the read fails", refused.row());
  assert.equal(refused.steps.reads, 1);
  // A failed read is asked for again at the page's next paint, which a poll that retitles
  // the record is, and waited for again: landing on the tab shown is no paint (B9 of review B
  // on #478).
  const retitled = structuredClone(recorded.current.body);
  retitled.record.pull.title = "Count to two in the app, retitled";
  await refused.poll(retitled);
  assert.equal(
    refused.container.querySelector(".github-pull-title").children[1].textContent,
    "Count to two in the app, retitled",
    "the poll repainted the page",
  );
  tell("a repaint after it failed, its read asked again", refused.row());
  await refused.idle();
  assert.equal(refused.steps.reads, 2, "the repaint read the comparison again");
  tell("that read fails too", refused.row());
  refused.handle.dispose();

  const declined = await mount("", { summary: "declines" });
  declined.idle();
  await settle();
  assert.deepEqual(declined.steps.summaries, ["the comparison read"]);
  tell("a comparison the summary draws nothing for", declined.row());
  declined.handle.dispose();

  const unread = await mount("files", { diff: "fails" });
  await settle();
  assert.deepEqual(unread.steps.summaries, []);
  tell("opened on Changes, whose diff reads no comparison", unread.row());
  unread.handle.dispose();

  const loading = await mount("", { body: recorded.absent.body });
  tell("the record on its way", loading.row());
  loading.handle.dispose();

  // A direct link's cold page waits from its first paint (mb-30dz): before its first answer,
  // through the absence its own fetch fills, the core, and the record, in one placeholder, so
  // the row is never empty while the comparison is on its way and has one quiet period.
  const coldCore = (state, refreshing) => ({
    ...structuredClone(recorded.current.body),
    state: refreshing ? "pending" : "absent",
    reason: refreshing ? null : "not_cached",
    refreshing,
    record: null,
    record_revision: null,
    fetched_at: null,
    core_preview: {
      source: recorded.current.body.source,
      number: 7,
      reader: recorded.current.body.record.reader,
      observed_at: recorded.current.body.record.fetched_at,
      revision: "a".repeat(64),
      pull: structuredClone(recorded.current.body.record.pull),
      comparison_state: state,
    },
  });
  const cold = await mount("", { cold: true });
  tell("a direct link's page before its first answer", cold.row());
  const coldWait = cold.row().children[0];
  await cold.poll(recorded.absent.body);
  tell("its first answer: not cached, its own fetch to be sent", cold.row());
  await cold.poll(coldCore("pending", true));
  tell("its fetch's core preview", cold.row());
  cold.serve(recorded.current.body);
  await cold.idle();
  tell("its record lands, the comparison not yet read", cold.row());
  assert.equal(cold.row().children[0], coldWait, "one placeholder from the first paint on");
  await cold.idle();
  await cold.idle();
  assert.deepEqual(cold.steps.summaries, ["the comparison read"]);
  tell("the comparison read", cold.row());
  cold.handle.dispose();
  // What no read will bring has no wait: a pull request that is not GitHub's, a server with
  // no store to compare in, as a checkout is until Changes asks for one, and a refresh that
  // failed with nothing running.
  const failedRefresh = {
    outcome: "network",
    message: "GitHub could not be reached.",
    reset_at: null,
    at: recorded.current.body.record.fetched_at,
  };
  for (const [said, body] of [
    [
      "a direct link's first answer: not GitHub's",
      { ...structuredClone(recorded.absent.body), reason: "not_github" },
    ],
    [
      "a direct link's first answer: a server with no store, its own fetch to be sent",
      { ...structuredClone(recorded.absent.body), no_store: true },
    ],
    [
      "a direct link's first answer: its refresh failed, nothing running",
      { ...structuredClone(recorded.absent.body), last_refresh: failedRefresh },
    ],
    [
      "a direct link's first answer: a core, its refresh failed, nothing running",
      { ...coldCore("not_started", false), last_refresh: failedRefresh },
    ],
  ]) {
    const answered = await mount("", { cold: true });
    await answered.poll(body);
    tell(said, answered.row());
    answered.handle.dispose();
  }

  const none = structuredClone(recorded.current.body);
  delete none.record.comparison;
  const nameless = await mount("", { body: none });
  nameless.idle();
  await settle();
  tell("a record that names no comparison", nameless.row());
  nameless.handle.dispose();

  // A core preview, the description the selected refresh's core read staged while it reads
  // the record (served_pull.py): "pending" when that read prepares the comparison too, as a
  // server with a store does; "no_store" when it does not, which only Changes asks for; and
  // "not_started" for a prepared core no read is running for. A reader's absent record has
  // the page's own fetch still to send, which brings the record and its comparison
  // (mb-30dz); a refresh that failed with nothing running is told above.
  const full = recorded.current.body;
  const core = (state, refreshing) => ({
    ...structuredClone(full),
    state: refreshing ? "pending" : "absent",
    reason: refreshing ? null : "not_cached",
    refreshing,
    record: null,
    record_revision: null,
    fetched_at: null,
    core_preview: {
      source: full.source,
      number: 7,
      reader: full.record.reader,
      observed_at: full.record.fetched_at,
      revision: "a".repeat(64),
      pull: structuredClone(full.record.pull),
      comparison_state: state,
    },
  });
  const preparing = await mount("", { body: core("pending", true) });
  tell("a core preview whose read prepares its comparison", preparing.row());
  const waited = preparing.row().children[0];
  preparing.serve(full);
  preparing.idle();
  await settle();
  assert.equal(
    preparing.row().children[0],
    waited,
    "the record keeps the core's placeholder: one quiet period and one pulse",
  );
  tell("its record lands, the comparison not yet read", preparing.row());
  preparing.idle();
  await settle();
  assert.deepEqual(preparing.steps.summaries, ["the comparison read"]);
  tell("the comparison read", preparing.row());
  preparing.handle.dispose();
  for (const [said, body] of [
    ["a core preview whose read prepares no comparison", core("no_store", true)],
    ["a prepared core, the page's own fetch still to be sent", core("not_started", false)],
    ["a core whose read ended, the page's own fetch still to be sent", core("pending", false)],
  ]) {
    const cored = await mount("", { body });
    tell(said, cored.row());
    cored.handle.dispose();
  }

  // A stale record whose comparison is not in the store, which the page asked the server to
  // prepare (`prepare_comparison`), as the idle work of Conversation does.
  const unstored = structuredClone(recorded.stale.body);
  unstored.record.comparison = null;
  unstored.record.unavailable = { comparison: "no_store" };
  const asked = await mount("", {
    body: { ...structuredClone(unstored), refreshing: true, preparing_comparison: true },
  });
  tell("a record whose comparison the page asked to prepare", asked.row());
  asked.serve(unstored);
  asked.idle();
  await settle();
  tell("the preparation ends with no comparison", asked.row());
  asked.handle.dispose();
  const unasked = await mount("", { body: unstored });
  tell("a record whose comparison nothing prepares", unasked.row());
  unasked.handle.dispose();

  // On Changes the row waits on the mounted diff's read, not the record's comparison: a
  // diff that read nothing leaves it empty, and a record that names a newer comparison is
  // followed, which starts that one's read. The way back shows the earlier diff again, and
  // offers the newer one.
  const moved = structuredClone(full);
  const newer = "9".repeat(40);
  moved.record.comparison.head = newer;
  moved.record.pull.head.sha = newer;
  moved.comparison_route = moved.comparison_route.replace(/right=[0-9a-f]+/, `right=${newer}`);
  const offered = await mount("files", {
    diff: (right) => (right === newer ? "reads" : "fails"),
  });
  tell("Changes, its diff reads no comparison", offered.row());
  offered.serve(moved);
  offered.idle();
  await settle();
  assert.equal(offered.container.querySelector(".github-pull-newer"), null);
  const followedNote = offered.container.querySelector(".github-pull-followed");
  assert.ok(followedNote, "a record with a moved head is followed, and Changes says so");
  assert.equal(
    followedNote.textContent,
    "Changes now show this pull request’s newer commits. Show the earlier changes",
  );
  tell("a record with a moved head is followed: its diff reads the comparison", offered.row());
  offered.container.querySelector(".github-pull-earlier").events.get("click")();
  await settle();
  assert.equal(offered.container.querySelector(".github-pull-followed"), null);
  const offer = offered.container.querySelector(".github-pull-newer");
  assert.ok(offer, "the earlier diff offers the newer changes");
  tell("the reader goes back: the earlier diff reads none again", offered.row());
  offer.events.get("click")();
  tell("the reader takes the newer changes, their diff not yet read", offered.row());
  await settle();
  assert.ok(offered.container.querySelector(".github-pull-followed"));
  tell("their diff reads the comparison", offered.row());
  offered.handle.dispose();

  // A Retry starts the read of the comparison that failed again: the row waits for it.
  const retried = await mount("files", {
    diff: (_right, attempt) => (attempt === 0 ? "throws" : "reads"),
  });
  tell("Changes, its diff throws", retried.row());
  const retry = retried.container.querySelectorAll(".btn").find((button) => {
    return button.textContent === "Retry";
  });
  assert.ok(retry, "a diff that threw offers Retry");
  retry.events.get("click")();
  tell("Retry, the diff not yet read", retried.row());
  await settle();
  tell("the diff reads the comparison", retried.row());
  retried.handle.dispose();

  // A record that names no comparison takes Changes' diff away, and the wait on its read.
  const reading = await mount("files", { diff: () => "waits" });
  tell("Changes, its diff still reading", reading.row());
  reading.serve(none);
  reading.idle();
  await settle();
  tell("the record then names no comparison", reading.row());
  reading.handle.dispose();
  return told;
}

// The cached changed-files list's brief line in the Diff summary's row (mb-z8ea): drawn while
// the comparison is on its way or read, for the head the page knows or any while it knows
// none, from the document's memory of the Pulls rows' lines with no request, else one read
// at mount; the Diff summary replaces it in one step; it stays when a read draws no
// summary; and another head's line is never shown, the placeholder holding the row instead.
async function summaryBrief(page) {
  const rowLines = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/row-lines.js")).href
  );
  const full = recorded.current.body;
  const head = full.record.comparison.head;
  const base = full.record.comparison.base;
  const baseRef = full.record.pull.base.ref;
  // A list as the route answers it: GitHub's, read for a head and a base branch, or the
  // local comparison's, of a head and a base commit.
  const listed = (listedHead, from = { listed_from: "github", base: null, base_ref: baseRef }) => ({
    number: 7,
    state: "listed",
    reason: null,
    listing: false,
    generation: `g-${listedHead.slice(0, 4)}`,
    head: listedHead,
    files: 3,
    additions: 12,
    deletions: 4,
    exact: true,
    statuses: [
      { status: "added", count: 1 },
      { status: "modified", count: 2 },
    ],
    ...from,
  });
  const compared = (listedBase) => ({
    listed_from: "comparison",
    base: listedBase,
    base_ref: null,
  });
  const told = [];
  const holds = (row) => {
    const [only] = row.children;
    if (row.children.length === 0) {
      return "nothing";
    }
    if (only.classes.has("github-pull-summary-brief")) {
      assert.equal(only.getAttribute("role"), "status", "still a wait to a screen reader");
      assert.match(only.getAttribute("aria-label"), /; loading the summary of changes$/);
      return `the brief line "${only.textContent}"`;
    }
    if (only.classes.has("github-pull-summary-pending")) {
      return "the pending placeholder";
    }
    return only.classes.has("diff-summary") ? "the summary" : "other";
  };
  const tell = (step, mounted) =>
    told.push(`${step}: ${holds(mounted.row())}; ${mounted.steps.briefReads.length} reads`);
  const core = structuredClone(full);
  Object.assign(core, {
    state: "pending",
    reason: null,
    refreshing: true,
    record: null,
    record_revision: null,
    fetched_at: null,
    core_preview: {
      source: full.source,
      number: 7,
      reader: full.record.reader,
      observed_at: full.record.fetched_at,
      revision: "a".repeat(64),
      pull: structuredClone(full.record.pull),
      comparison_state: "pending",
    },
  });

  const cold = await mountScripted(page, "", { cold: true, brief: listed(head) });
  tell("a direct link's page before its first answer, its head unknown", cold);
  await cold.poll(core);
  tell("its core preview, of the list's head and base branch", cold);
  const line = cold.row().children[0];
  cold.serve(full);
  await cold.idle();
  tell("its record lands, the comparison not yet read", cold);
  assert.equal(cold.row().children[0], line, "one line, kept across paints");
  await cold.idle();
  await cold.idle();
  tell("the comparison read", cold);
  cold.handle.dispose();

  const older = await mountScripted(page, "", { cold: true, brief: listed("9".repeat(40)) });
  tell("a direct link's page, the list of an older head", older);
  await older.poll(core);
  tell("its core preview, of a newer head", older);
  older.handle.dispose();

  const retargeted = await mountScripted(page, "", {
    brief: listed(head, { listed_from: "github", base: null, base_ref: "an-earlier-base" }),
  });
  tell("a record whose list was read for another base branch", retargeted);
  retargeted.handle.dispose();

  const local = await mountScripted(page, "", { cold: true, brief: listed(head, compared(base)) });
  await local.poll(core);
  tell("a core preview, the local comparison's list, whose base the core cannot say", local);
  local.serve(full);
  await local.idle();
  tell("its record lands, naming the same comparison", local);
  local.handle.dispose();

  const rebased = await mountScripted(page, "", { brief: listed(head, compared("8".repeat(40))) });
  tell("a record whose comparison has another base than the local list's", rebased);
  rebased.handle.dispose();

  const failing = await mountScripted(page, "", { brief: listed(head), read: "fails" });
  tell("a record of the list's head, its comparison not yet read", failing);
  await failing.idle();
  tell("the comparison's read fails", failing);
  failing.handle.dispose();

  const absent = await mountScripted(page, "", {
    brief: { ...listed(head), state: "absent", reason: "not_cached", files: null },
  });
  tell("no list cached", absent);
  absent.handle.dispose();

  // A list that only adds lines leaves its zero total out, as every lines summary does
  // (mb-ox6a): "+3,893", never "+3,893 −0".
  const addsOnly = await mountScripted(page, "", {
    brief: { ...listed(head), additions: 3893, deletions: 0 },
  });
  tell("a record of a list that only adds lines", addsOnly);
  addsOnly.handle.dispose();

  // A page opened from a Pulls row: the row's line is in the document's memory.
  const remember = (due) =>
    rowLines.documentRowLines.set(rowLines.rowLineKey(full.source, 7), {
      head,
      generation: "g-row",
      summary: {
        ...listed(head),
        generation: "g-row",
        files: 1,
        statuses: [{ status: "modified", count: 1 }],
      },
      due,
      listing: false,
      failedAt: null,
      at: 0,
    });
  remember(false);
  const fromRow = await mountScripted(page, "", { briefPainters: true });
  tell("opened from a Pulls row that drew its line", fromRow);
  fromRow.handle.dispose();
  remember(true);
  const dueRow = await mountScripted(page, "", { brief: listed(head) });
  tell("opened from a Pulls row whose line the lane marked out of date, read again", dueRow);
  dueRow.handle.dispose();
  rowLines.documentRowLines.clear();

  // A page that goes before its read answers draws nothing more (B3 of review on #536).
  let release = () => {};
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const gone = await mountScripted(page, "", { brief: listed(head), briefGate: gate });
  await gone.idle();
  await gone.idle();
  assert.equal(holds(gone.row()), "the summary");
  gone.handle.dispose();
  release();
  await settle();
  tell("a page that went before its read answered, its summary drawn", gone);
  return told;
}

// A page mounted with no record in hand holds its cold header and tab column for the shell's
// quiet period (`github-pull-cold`), and the first header that has a record lifts the hold,
// also while the conversation's first paint still waits for its Markdown: the header does
// not wait for the body (exp-099). A page with its record in hand holds nothing.
// tests/dom/github-pull-header-chrome.mjs (`cold-landing`) measures what each looks like
// and that a landing in the quiet period moves nothing; here, which the page carries in
// each state, told in order for the golden.
async function coldHold(page) {
  const told = [];
  const tell = (step, container) => {
    const header = container.querySelector(".github-pull-header");
    const column = container.querySelector(".tab-bar")?.parentNode ?? null;
    const of = (node) =>
      node === null ? "out" : node.classes.has("github-pull-cold") ? "github-pull-cold" : "shown";
    told.push(`${step}: header ${of(header)}, tab column ${of(column)}`);
  };
  const conversation = await mountScripted(page, "", { cold: true, markdown: "waits" });
  tell("mounted with no record in hand", conversation.container);
  conversation.serve(recorded.current.body);
  conversation.idle();
  await settle();
  assert.equal(
    conversation.container.querySelector(".github-pull-title").children[1].textContent,
    "Count to two in the app",
    "the header paints its record while the conversation's first paint waits",
  );
  tell("its record lands, the conversation waiting for its Markdown", conversation.container);
  conversation.idle();
  await settle();
  tell("the conversation's first paint, at its bound", conversation.container);
  conversation.handle.dispose();
  const changes = await mountScripted(page, "files", { cold: true });
  tell("on Changes, mounted with no record in hand", changes.container);
  changes.serve(recorded.current.body);
  changes.idle();
  await settle();
  tell("its record lands", changes.container);
  changes.handle.dispose();
  const opened = await mountScripted(page, "");
  tell("mounted with its record in hand", opened.container);
  opened.handle.dispose();
  // The cold header's title: "Pull request #7", held at two lines, or, with the Pulls tab's
  // row for it in hand as the list notes it, the record's shape with the row's state and
  // title, so the record lands on the same lines (review A on #608). A page does not know its
  // repository before its record, so a number two repositories' lists both name titles no
  // cold header. The rows are older than any record, so no later step's state is the list's.
  const states = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-state.js")).href
  );
  const titled = (step, container) => {
    const title = container.querySelector(".github-pull-title");
    const shape = title.classes.has("github-pull-title-with-state")
      ? "the record's shape"
      : "plain";
    told.push(`${step}: title "${title.textContent}", ${shape}`);
  };
  const plain = await mountScripted(page, "", { cold: true });
  titled("no Pulls row in hand, mounted with no record in hand", plain.container);
  plain.handle.dispose();
  const listedAt = "2000-01-01T00:00:00Z";
  states.noteListed("https://github.com/octo/listed", "open", [
    { number: 7, state: "open", updatedAt: listedAt, title: "Count to two in the app" },
  ]);
  const seeded = await mountScripted(page, "", { cold: true });
  titled("its Pulls row in hand, mounted with no record in hand", seeded.container);
  tell("its Pulls row in hand, mounted with no record in hand", seeded.container);
  seeded.handle.dispose();
  states.noteListed("https://github.com/octo/also-listed", "closed", [
    { number: 7, state: "merged", updatedAt: listedAt, title: "Another seven" },
  ]);
  const ambiguous = await mountScripted(page, "", { cold: true });
  titled(
    "two repositories' rows for its number, mounted with no record in hand",
    ambiguous.container,
  );
  ambiguous.handle.dispose();
  return told;
}

// The View on GitHub button on a pull request's page (mb-4wqh): the header's corner, a
// `.view-header-end` marked `data-counterpart`, right after the title, so the reading order is
// the title and then the button, from the cold header on. The page asks the SDK's
// `mountCounterpart` for the button of the address it is at after each header paint, the SDK
// asking the server once per address (plugin-sdk-views.js): the tab's own address, and the
// changed file's once the shell moves the address to it. It is one corner for the page's
// life, so a repaint moves nothing. An SDK with no button leaves the corner empty. Where the
// corner is drawn is paint, measured by tests/dom/github-pull-header-chrome.mjs (`corner`).
// Told in order for the golden.
async function counterpartSteps(page) {
  const told = [];
  const asked = [];
  let corner = null;
  const mountCounterpart = async (_element, address) => {
    asked.push(address);
    return null;
  };
  const tell = (step, container) => {
    const header = container.querySelector(".github-pull-header");
    const corners = header === null ? [] : header.querySelectorAll(":scope > .view-header-end");
    const asks = `asked ${asked.length === 0 ? "for none" : asked.join(", ")}`;
    asked.length = 0;
    if (corners.length === 0) {
      told.push(`${step}: no corner; ${asks}`);
      return;
    }
    assert.equal(corners.length, 1, "the header has one corner");
    const [shown] = corners;
    assert.equal(shown.getAttribute("data-counterpart"), "", "the corner leaves the button room");
    const before = header.children[header.children.indexOf(shown) - 1];
    const after = before.classes.has("github-pull-title")
      ? `the title "${before.children[1]?.textContent ?? before.textContent}"`
      : before.className;
    const kept = corner === null ? "" : shown === corner ? ", the same corner" : ", a new corner";
    corner = shown;
    told.push(`${step}: the corner after ${after}${kept}; ${asks}`);
  };
  const cold = await mountScripted(page, "", { cold: true, mountCounterpart, routes: true });
  tell("mounted with no record in hand", cold.container);
  await cold.poll(recorded.current.body);
  tell("its record lands", cold.container);
  const retitled = structuredClone(recorded.current.body);
  retitled.record.pull.title = "Count to three in the app";
  await cold.poll(retitled);
  tell("a poll brings a new title", cold.container);
  window.location.pathname = "/pull/7/checks";
  cold.handle.setTab("checks");
  await settle();
  tell("the route shows Checks", cold.container);
  cold.handle.dispose();
  corner = null;
  const none = await mountScripted(page, "");
  tell("an SDK with no button", none.container);
  assert.equal(corner.children.length, 0, "an SDK with no button leaves the corner empty");
  none.handle.dispose();
  return told;
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
  const page = await importPage(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href,
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
        whenIdle: require("./sdk-idle-fixture.js").whenIdle,
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
        ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
          label: "now",
          className: "age",
        })),
        formatTimestamp: () => "now",
        navigation: {
          href: () => "/view/",
          async open(target) {
            asked.push(`navigation.open /view/${target.path}`);
          },
        },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
      },
    );
    await settle();
    await handle.whenFilesReady();
    const title = container.querySelector(".github-pull-title-with-state");
    assert.equal(title.tag, "h1");
    assert.ok(title.classes.has("page-heading"));
    assert.ok(title.parentNode.classes.has("page-reading-column"));
    assert.ok(container.querySelector(".tab-bar").parentNode.classes.has("page-reading-column"));
    assert.ok(!container.querySelector(".github-pull-body").classes.has("page-reading-column"));
    const [icon, titleText, , number] = title.children;
    assert.equal(icon.className, "github-pull-state-icon");
    assert.equal(icon.dataset.state, "open");
    assert.equal(icon.children[0].tag, "svg");
    assert.equal(icon.getAttribute("aria-hidden"), "true");
    assert.equal(icon.getAttribute("aria-label"), null);
    // The number is outside the text a long title is clamped in, so it is never cut off.
    assert.equal(titleText.textContent, "Count to two in the app");
    assert.ok(number.classes.has("github-pull-number"));
    assert.equal(title.textContent.endsWith("Count to two in the app #7"), true);
    const meta = container.querySelector(".github-pull-meta");
    // The corner stays out of the rows' flow. State and ages lead the metadata.
    const opened = container.querySelector(".github-pull-opened");
    const titleIndex = title.parentNode.children.indexOf(title);
    const corner = title.parentNode.children[titleIndex + 1];
    assert.ok(corner.classes.has("view-header-end"));
    assert.equal(title.parentNode.children[titleIndex + 2], opened);
    assert.equal(title.parentNode.children[titleIndex + 3], meta);
    // The author's row is its lead alone, the details then the freshness note (mb-ne91).
    const [lead] = meta.children;
    assert.ok(lead.classes.has("github-pull-meta-lead"));
    const [details, note] = lead.children;
    assert.ok(details.classes.has("github-pull-meta-details"));
    assert.ok(note.classes.has("github-pull-note"));
    assert.equal(lead.children.length, 2);
    assert.equal(meta.children.length, 1);
    // The state's badge leads the first metadata row, and the stack's slot ends it (mb-646g):
    // the slot holds a strut while no stack is known, so a late chip lands in the row's empty
    // end. Nothing follows it: the page has no Refresh of its own (mb-ablv).
    // The readiness's slot follows the state's (mb-io36): a link to the Checks tab, its badge
    // the server's label in the server's tone, named with auto-merge's sentence while it is
    // on, its tooltip the requirements not met, then a sizer of every label the slot is as
    // wide as, hidden from assistive technology.
    const [stateBadgeSlot, readinessSlot, ages, stackSlot] = opened.children;
    assert.ok(stateBadgeSlot.classes.has("github-pull-state-slot"));
    assert.ok(readinessSlot.classes.has("github-pull-readiness-slot"));
    const [readinessLink, ...readinessSizers] = readinessSlot.children;
    const shownReadiness = recorded.current.body.readiness;
    assert.equal(readinessLink.tag, "a");
    assert.equal(readinessLink.getAttribute("href"), "/pull/7/checks");
    assert.equal(
      readinessLink.getAttribute("aria-label"),
      `${shownReadiness.label}. ${shownReadiness.auto_merge_summary}`,
    );
    const notMet = shownReadiness.requirements
      .filter((requirement) => requirement.status !== "met")
      .map((requirement) => requirement.summary)
      .join(" ");
    assert.equal(readinessLink.dataset.tipText, notMet);
    assert.equal(readinessLink.getAttribute("aria-description"), notMet);
    const [verdictBadge] = readinessLink.children;
    assert.deepEqual(
      [verdictBadge.dataset.verdict, verdictBadge.dataset.tone, verdictBadge.textContent],
      [shownReadiness.verdict, shownReadiness.tone, shownReadiness.label],
    );
    assert.ok(readinessSizers.length > 0);
    assert.ok(
      readinessSizers.every(
        (sizer) =>
          sizer.classes.has("github-pull-badge-sizer") &&
          sizer.getAttribute("aria-hidden") === "true",
      ),
    );
    assert.ok(readinessSizers.some((sizer) => sizer.textContent === shownReadiness.label));
    assert.ok(ages.classes.has("github-pull-quiet") && ages.textContent.startsWith("Opened "));
    assert.ok(stackSlot.classes.has("github-pull-stacks"));
    assert.ok(stackSlot.children[0].classes.has("github-pull-stack-strut"));
    assert.equal(opened.children.length, 4);
    const stateBadge = stateBadgeSlot.children[0];
    assert.equal(opened.children.at(-1), container.querySelector(".github-pull-stacks"));
    assert.equal(stateBadge.getAttribute("data-state"), "open");
    assert.deepEqual(stateBadge.children, ["Open"]);
    // The author's sentence is the row; the branches have the line below to themselves.
    assert.ok(details.children.at(-1).classes.has("github-pull-action"));
    assert.equal(details.textContent, "forker wants to merge 2 commits");
    // Merge Direction: the header names the branches head → base, through the shared group,
    // on a line of their own under the sentence.
    const branches = container.querySelector(".github-pull-branches");
    assert.equal(
      title.parentNode.children.indexOf(branches),
      title.parentNode.children.indexOf(meta) + 1,
    );
    assert.equal(branches.textContent, "forker:count-to-two → octo:topic");
    const merge = branches.children.find((node) => node.className === "merge-refs");
    assert.equal(merge.getAttribute("dir"), "ltr");
    const [source, arrow, target] = merge.children;
    assert.equal(source.dataset.tipText, "forker:count-to-two");
    assert.equal(target.dataset.tipText, "octo:topic");
    assert.equal(arrow.getAttribute("aria-label"), "merges into");
    // View on GitHub is the corner's button, which this SDK does not draw, and no link in
    // the header's rows (mb-4wqh).
    assert.ok(
      ![...container.descendants()].some(
        (node) => node.tag === "a" && node.textContent === "View on GitHub",
      ),
    );

    assert.equal(stateBadge.getAttribute("aria-hidden"), null);
    assert.deepEqual(
      container
        .querySelectorAll(".tab-btn")
        .filter((tab) => tab.getAttribute("role") === "tab")
        .map((tab) => [tab.textContent, tab.getAttribute("href")]),
      [
        ["Conversation", "/pull/7"],
        ["Docs", "/pull/7/docs"],
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
    // Without `probe_every_s` the current page asks nothing, so each `tick` fires the poll.
    const unprobed = { ...initial, body: { ...initial.body, probe_every_s: null } };
    let current = structuredClone(unprobed.body);
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
        reader: { initial: unprobed, fetchAfterMs: 0 },
      },
      {
        perf,
        ensureAsset: async () => {},
        whenIdle: require("./sdk-idle-fixture.js").whenIdle,
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
        ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
          label: "now",
          className: "age",
        })),
        formatTimestamp: () => "now",
        navigation: {
          href: () => "/view/",
          async open(target) {
            asked.push(`navigation.open /view/${target.path}`);
          },
        },
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
    const moved = /Changes now show this pull request’s newer commits\. Show the earlier changes/;
    if (outcome === "moved") {
      current = structuredClone(current);
      current.record.comparison.head = "e".repeat(40);
      current.record.pull.head.sha = "e".repeat(40);
      // Timers fire in the order they were set: the stacks reader's, then the poll.
      await tick();
      assert.equal(mounted.length, 1, "nothing but a read of the record moves Changes");
      await tick();
      await handle.whenFilesReady();
      assert.equal(mounted.length, 2, "Changes follows a head that advanced");
      assert.equal(mounted[1].right, "e".repeat(40));
      assert.match(container.textContent, moved);
    }
    const opened = mounted.length;
    const onScreen = mounted.at(-1);
    const displayed = { base: onScreen.left, head: onScreen.right };
    // The page has no Refresh of its own: the navigation's Refresh runs the page's `refresh`,
    // which names the comparison on screen (mb-ablv).
    assert.ok(handle.canRefresh(), "fresh Files offers explicit repair");
    handle.refresh();
    await settle();
    handle.refresh();
    await settle();
    assert.deepEqual(requests, [{ number: 7, retry: true, recovery: displayed }]);
    assert.equal(mounted.length, opened, "a pending POST cannot remount");
    current = { ...current, refreshing: true };
    reply({ status: 202, headers: { get: () => null }, json: async () => ({ pull: current }) });
    await settle();
    await tick();
    assert.equal(mounted.length, opened, "waiting for a job cannot remount");
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
    const repaired = outcome === "failed" ? opened : opened + 1;
    assert.equal(mounted.length, repaired);
    assert.equal(disposed, repaired - 1);
    assert.deepEqual(mounted.at(-1), onScreen, "repair remounts the comparison on screen");
    if (outcome === "moved") {
      assert.match(container.textContent, moved, "a repaired diff keeps its note");
    }
    await tick();
    assert.equal(mounted.length, repaired, "only one remount per repair");
    handle.dispose();
    handle.refresh();
    await settle();
    assert.equal(requests.length, 1, "a disposed page's refresh is inert");
    assert.equal(handle.canRefresh(), false, "a disposed page has nothing to refresh");
  }
  const checkout = JSON.parse(
    fs.readFileSync(
      path.join(root, "tests/fixtures/github-checkout-comparison-responses.json"),
      "utf8",
    ),
  );
  const posts = [];
  const comparisonAsk = { number: 10, retry: true, comparison: true };
  let resolveComparison;
  globalThis.fetch = async (_route, options = {}) => {
    if (options.method === "POST") {
      posts.push(JSON.parse(options.body));
      if (posts.length === 1) {
        return new Promise((resolve) => {
          resolveComparison = resolve;
        });
      }
    }
    const answer = options.method === "POST" ? checkout.started : checkout.before;
    return { status: answer.status, headers: { get: () => null }, json: async () => answer.body };
  };
  window.location.pathname = "/pull/10";
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
      whenIdle: require("./sdk-idle-fixture.js").whenIdle,
      ensureKindAssets: async () => {},
      getRegisteredView: () => {
        throw new Error("no comparison exists before acquisition");
      },
      ...require("./sdk-ref-fixture.js").refHelpers(document),
      ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
        label: "now",
        className: "age",
      })),
      formatTimestamp: () => "now",
      navigation: {
        href: () => "/view/",
        async open(target) {
          asked.push(`navigation.open /view/${target.path}`);
        },
      },
      sourceKind: () => "filesystem",
      icons: { toggle: "" },
    },
  );
  await settle();
  assert.deepEqual(posts, [], "a staged Changes mount cannot fetch after the route moved away");
  const stagedBody = checkoutContainer.querySelector(".github-pull-body");
  assert.match(stagedBody.textContent, /Changes have not been fetched/);
  assert.equal(stagedBody.querySelector(".spinner"), null, "nothing is on its way to spin for");
  assert.equal(
    stagedBody.querySelector(".github-pull-fetch-changes")?.textContent,
    "Fetch",
    "the reader can still fetch what the address does not ask for",
  );
  window.location.pathname = "/pull/10/files/src/app.txt";
  checkoutHandle.land({ tab: "files", file: "src/app.txt" });
  await settle();
  const checkoutBody = checkoutContainer.querySelector(".github-pull-body");
  assert.deepEqual(posts, [comparisonAsk]);
  const acquiring = checkoutBody.querySelector(".github-pull-changes-pending");
  assert.match(acquiring?.getAttribute("aria-label") ?? "", /Fetching changes/);
  assert.ok(acquiring.classes.has("mb-delayed-loading"), "after the quiet period");
  assert.ok(checkoutBody.querySelector(".spinner"));
  assert.equal(checkoutBody.querySelector(".github-pull-retry-changes"), null);
  resolveComparison({
    status: 429,
    headers: { get: () => null },
    json: async () => ({ error: "server busy", code: "too_many" }),
  });
  await settle();
  const [checkoutPollId, checkoutPoll] = timers.entries().next().value;
  timers.delete(checkoutPollId);
  checkoutPoll();
  await settle();
  assert.deepEqual(posts, [comparisonAsk], "polling does not retry a refused acquisition");
  assert.match(checkoutBody.textContent, /Changes could not be fetched/);
  // The refusal is said in the Changes body, where its Retry is, not on the header's status
  // line, so the header has the same rows on every tab (B5 of review B on #506).
  assert.match(
    checkoutBody.textContent,
    /The refresh could not start while other pull requests are being fetched\./,
    "the refusal's reason outlasts the read that cleared its error",
  );
  assert.doesNotMatch(checkoutBody.textContent, /server busy/, "said by its code, not its text");
  assert.equal(checkoutContainer.querySelector(".github-pull-message"), null);
  const shownRows = () =>
    checkoutContainer
      .querySelector(".github-pull-header")
      .children.filter((node) => node.hidden !== true)
      .map((node) => (node.tag === "h1" ? "title" : [...node.classes][0]))
      .join(" ");
  const refusedRows = {};
  for (const [tab, at] of [
    ["files", "/pull/10/files"],
    ["", "/pull/10"],
    ["checks", "/pull/10/checks"],
    ["files", "/pull/10/files"],
  ]) {
    window.location.pathname = at;
    checkoutHandle.setTab(tab);
    await settle();
    refusedRows[tab || "conversation"] = shownRows();
  }
  assert.equal(
    new Set(Object.values(refusedRows)).size,
    1,
    `a refused comparison leaves the header's rows the same on every tab: ${JSON.stringify(refusedRows)}`,
  );
  assert.match(
    checkoutBody.textContent,
    /other pull requests are being fetched/,
    "the body says it again back on Changes",
  );
  assert.equal(checkoutBody.querySelector(".spinner"), null);
  const retryChanges = checkoutBody.querySelector(".github-pull-retry-changes");
  assert.equal(retryChanges?.textContent, "Retry");
  retryChanges.events.get("click")();
  retryChanges.events.get("click")();
  await settle();
  assert.deepEqual(posts, [comparisonAsk, comparisonAsk], "only one explicit retry is admitted");
  assert.equal(checkoutBody.querySelector(".github-pull-retry-changes"), null);
  checkoutHandle.dispose();
  retryChanges.events.get("click")();
  await settle();
  assert.equal(posts.length, 2, "a disposed Retry button starts nothing");
  window.location.pathname = "/pull/7/files";
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
    // The shared changed-files tree, which the SDK loads from the shell's bundle.
    loadChangedFilesTree: async () => require("./changed-files-tree-fixture.js").changedFilesTree(),
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
          whenIdle: require("./sdk-idle-fixture.js").whenIdle,
          ensureKindAssets: async () => {},
          getRegisteredView: () => diffView,
          ...require("./sdk-ref-fixture.js").refHelpers(document),
          ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
            label: "now",
            className: "age",
          })),
          formatTimestamp: () => "now",
          navigation: {
            href: () => "/view/",
            async open(target) {
              asked.push(`navigation.open /view/${target.path}`);
            },
          },
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
    whenIdle: require("./sdk-idle-fixture.js").whenIdle,
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
    ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
      label: "now",
      className: "age",
    })),
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
  await markdownOwnership();
  await checkRows(page);
  await mergeStatusSection(page);
  await headerAges(page);
  await headerShape(page);
  // The freshness note's slot is as wide as its widest age: each age the page says is put at
  // "59 min ago", the widest `relativeAge` says, for the hidden copy that sizes the slot, and
  // a note wider still, as an unknown age is, sizes its own (mb-ne91).
  const widestNotes = Object.fromEntries(
    [
      "Fetched just now via GitHub CLI",
      "Fetched 3 h ago via GitHub CLI",
      "Offline · fetched 12 d ago via GitHub CLI",
      "Description fetched 7 min ago via GitHub CLI",
      "Fetched at an unknown time via GitHub CLI",
    ].map((note) => [note, page.widestNote(note)]),
  );
  // A rate limit's hold says when it lifts in the reader's short form: a time of day when it
  // lifts today, a short date and time when not (B3 of review B on #506). In en-US and UTC
  // here, so the golden is the same on every machine.
  const nine = Date.UTC(2026, 8, 17, 9, 0);
  const holdLifts = Object.fromEntries(
    [
      ["today", Date.UTC(2026, 8, 17, 14, 5)],
      ["tomorrow", Date.UTC(2026, 8, 18, 0, 30)],
      ["next year", Date.UTC(2027, 0, 2, 8, 0)],
    ].map(([when, lift]) => [when, page.holdLiftText(lift, nine, "en-US", "UTC")]),
  );
  const headerSummarySteps = await headerSummary(page);
  const summaryBriefSteps = await summaryBrief(page);
  const coldHoldSteps = await coldHold(page);
  const counterpartStepsTold = await counterpartSteps(page);
  const tabKeySteps = await tabKeys(page);
  const guideIntroductionSteps = await guideIntroduction(page);
  const guideIntroductionBoundSteps = await guideIntroduction(page, true);
  const textRefusalSteps = await textRefusal();
  const textLinkSteps = await textLinks();
  const textDiagramSteps = await textDiagrams();
  const switchUnavailableSteps = await switchUnavailable(page);
  const eventLogDetailsSteps = await eventLogDetails(page);
  const statusRemedySteps = await statusRemedies(page);
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
    checkoutFetchIsAutomatic: true,
    displayedComparisonRepair: true,
    bridgeAfterPaint: true,
    bridgeFramesOwned: true,
    hiddenReadiness: true,
    markdownOwnership: true,
    checkRows: true,
    mergeStatus: true,
    headerAges: true,
    headerShape: true,
    widestNotes,
    holdLifts,
    headerSummary: headerSummarySteps,
    summaryBrief: summaryBriefSteps,
    coldHold: coldHoldSteps,
    counterpart: counterpartStepsTold,
    tabKeys: tabKeySteps,
    guideIntroduction: guideIntroductionSteps,
    guideIntroductionBound: guideIntroductionBoundSteps,
    textRefusal: textRefusalSteps,
    textLinks: textLinkSteps,
    textDiagrams: textDiagramSteps,
    switchUnavailable: switchUnavailableSteps,
    eventLogDetails: eventLogDetailsSteps,
    statusRemedies: statusRemedySteps,
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
