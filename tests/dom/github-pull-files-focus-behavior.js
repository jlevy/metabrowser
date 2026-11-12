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
    this.listeners = new Map();
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
  get ownerDocument() {
    return globalThis.document;
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
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
    let active = document.activeElement;
    while (active !== null && active !== this) {
      active = active.parentNode;
    }
    if (active === this) {
      document.activeElement = document.body;
    }
    if (this.parentNode !== null) {
      this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1);
      this.parentNode = null;
    }
  }
  addEventListener(name, callback) {
    this.listeners.set(name, callback);
  }
  getBoundingClientRect() {
    return { top: 0, bottom: 700 };
  }
  focus() {
    document.activeElement = this;
  }
  scrollIntoView() {
    scrolled.push(this);
  }
  // A browser blurs an element that is hidden while it has focus.
  get hidden() {
    return this._hidden === true;
  }
  set hidden(value) {
    this._hidden = value === true || value === "";
    if (this._hidden && document.activeElement === this) {
      document.activeElement = document.body;
    }
  }
}
/** The elements scrolled into view, in order. @type {Element[]} */
const scrolled = [];
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
    "retry",
    "retry other focus",
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
    let reads = 0;
    let releaseRetry = null;
    const view = mountFileTree({
      decorateExternalLink:
        require("./sdk-ref-fixture.js").refHelpers(document).decorateExternalLink,
      number: 7,
      autoExpandFiles: 3000,
      current: null,
      shown: true,
      scrollRoot: document.body,
      chevron: () => null,
      href: (file) => `/${file}`,
      request: async (_method, route) => {
        if (scenario.startsWith("retry")) {
          if (reads++ === 0) {
            throw Error("initial read failed");
          }
          await new Promise((resolve) => {
            releaseRetry = resolve;
          });
        }
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
            source: "https://github.com/octo/demo",
            generation: generation.toString(16).padStart(32, "0"),
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
              status: generation === 0 && /^a(?:000)?\.py$/.test(file) ? "unchanged" : "modified",
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
    if (scenario.startsWith("retry")) {
      const notice = view.group.children.find(
        (element) => element.getAttribute("class") === "github-pull-files-notice-host",
      );
      const button = notice.children[0].children.find((element) => element.tagName === "BUTTON");
      (scenario.endsWith("other focus") ? elsewhere : button).focus();
      button.listeners.get("click")();
      await settle();
      const expected = scenario.endsWith("other focus") ? elsewhere : owner;
      assert.equal(document.activeElement, expected, "Retry removal has a stable focus fallback");
      releaseRetry();
      await settle();
      assert.equal(
        document.activeElement,
        expected,
        "arriving files never steal the fallback focus",
      );
      view.dispose();
      continue;
    }
    const list = view.group.children.find(
      (element) => element.getAttribute("class") === "github-pull-files-rows",
    );
    const survivorId = scenario.startsWith("windowed") ? "a000.py" : "a.py";
    const survivor = list.children.find((element) => element.dataset.id === survivorId);
    assert.equal(survivor.children[0].attributes.get("data-file-status"), "unchanged");
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
    if (scenario !== "empty") {
      const kept = list.children.find((element) => element.dataset.id === survivorId);
      assert.equal(kept, survivor, "status repaint retains the row element");
      assert.equal(
        kept.children[0].attributes.get("data-file-status"),
        "modified",
        "same M glyph must repaint its semantic status",
      );
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
  await walkClaims(mountFileTree);
  results.push({ scenario: "refreshing", paints: await refreshingPaint(mountFileTree) });
  results.push({ scenario: "offer pressed", ...(await offerFocus(mountFileTree, 0)) });
  results.push({ scenario: "offer clicked", ...(await offerFocus(mountFileTree, 1)) });
  return results;
}

/**
 * Rows that came late are offered on the tree's line; pressing the offer draws them and leaves
 * focus on the tree's anchor, never on the document body. Only a press from the keyboard, a
 * click whose `detail` is 0, scrolls to the anchor: a pointer pressed the offer where it is.
 *
 * @param {Function} mountFileTree
 * @param {number} detail The click's count of pointer presses.
 */
async function offerFocus(mountFileTree, detail) {
  const realNow = Date.now;
  let now = 0;
  Date.now = () => now;
  const timers = new Map();
  try {
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
    const parent = new Element("li");
    const owner = new Element("a");
    owner.dataset.id = "owner";
    document.body.append(parent);
    parent.append(owner);
    let answer;
    const view = mountFileTree({
      decorateExternalLink:
        require("./sdk-ref-fixture.js").refHelpers(document).decorateExternalLink,
      number: 7,
      autoExpandFiles: 3000,
      current: null,
      shown: true,
      scrollRoot: document.body,
      chevron: () => null,
      href: (file) => `/${file}`,
      request: () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
      formatTime: (value) => value,
      page: () => null,
      open() {},
      leave: () => owner.focus(),
      focusedIn() {},
      lastInput: () => 0,
    });
    view.attach(parent, owner);
    view.controller.expand();
    await settle();
    // The opening's bound passes: the tree opens on its loading line, and the list comes late.
    now = 150;
    for (const [id, timer] of [...timers]) {
      timers.delete(id);
      timer.callback();
    }
    now = 2000;
    answer({
      status: 200,
      etag: null,
      body: {
        state: "current",
        reason: null,
        number: 7,
        listed_from: "github",
        source: "https://github.com/octo/demo",
        generation: "0".repeat(32),
        fetched_at: "2026-11-03T00:00:00Z",
        reader: "gh:test",
        head: null,
        base: null,
        fresh_for_s: 60,
        refreshing: false,
        last_refresh: null,
        fetched: 2,
        pages: 1,
        last_page: null,
        complete: true,
        capped: false,
        truncated: false,
        offset: 0,
        limit: 3000,
        rows: ["a.py", "b.py"].map((file) => ({
          path: file,
          display: file,
          previous_path: null,
          previous_display: null,
          status: "modified",
          additions: 1,
          deletions: 0,
        })),
      },
    });
    await settle();
    const line = view.group.children.find(
      (element) => element.getAttribute("class") === "github-pull-files-line",
    );
    const offer = line.children.find((element) => element.tagName === "BUTTON");
    assert.equal(offer.hidden, false, "late rows are offered");
    offer.focus();
    scrolled.length = 0;
    offer.listeners.get("click")({ detail });
    await settle();
    assert.notEqual(document.activeElement, document.body, "focus stays in the tree");
    const focused = document.activeElement.dataset.id;
    const scrolls = scrolled.length;
    view.dispose();
    return { focus: focused, scrolls };
  } finally {
    Date.now = realNow;
  }
}

/**
 * A stale list whose rows are shown: while its refresh is asked for and while it runs, the
 * names breathe in one group marked busy, and nothing spins or says the list is stale; the
 * spinner is only for a list with no rows. The paint is the production view's.
 *
 * @param {Function} mountFileTree
 */
async function refreshingPaint(mountFileTree) {
  class Painted extends Element {
    constructor(tag) {
      super(tag);
      const classes = new Set();
      this.classes = classes;
      this.classList = {
        toggle(name, on) {
          const want = on ?? !classes.has(name);
          if (want) {
            classes.add(name);
          } else {
            classes.delete(name);
          }
          return want;
        },
        contains: (name) => classes.has(name),
      };
    }
    setAttribute(name, value) {
      super.setAttribute(name, value);
      if (name === "class") {
        for (const each of String(value).split(" ").filter(Boolean)) {
          this.classes.add(each);
        }
      }
    }
  }
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
  globalThis.document = {
    visibilityState: "visible",
    createElement: (tag) => new Painted(tag),
  };
  document.body = new Painted("body");
  document.activeElement = document.body;
  const parent = new Painted("li");
  const owner = new Painted("a");
  document.body.append(parent);
  parent.append(owner);
  const listing = (state, refreshing, rows) => ({
    state,
    reason: null,
    number: 7,
    listed_from: "github",
    source: "https://github.com/octo/demo",
    generation: "0".repeat(32),
    fetched_at: "2026-11-03T00:00:00Z",
    reader: "gh:test",
    head: null,
    base: null,
    fresh_for_s: 60,
    refreshing,
    last_refresh: null,
    fetched: 2,
    pages: 1,
    last_page: null,
    complete: true,
    capped: false,
    truncated: false,
    offset: 0,
    limit: 3000,
    rows: rows
      ? ["src/a.py", "src/b.py"].map((file) => ({
          path: file,
          display: file,
          previous_path: null,
          previous_display: null,
          status: "modified",
          additions: 1,
          deletions: 0,
        }))
      : [],
  });
  const reads = [listing("stale", false, true)];
  /** @type {(value: unknown) => void} */
  let answerAsk = () => {};
  const view = mountFileTree({
    decorateExternalLink: require("./sdk-ref-fixture.js").refHelpers(document).decorateExternalLink,
    number: 7,
    autoExpandFiles: 3000,
    current: null,
    shown: true,
    scrollRoot: document.body,
    chevron: () => null,
    href: (file) => `/${file}`,
    request: (method) =>
      method === "POST"
        ? new Promise((resolve) => {
            answerAsk = resolve;
          })
        : Promise.resolve({ status: 200, etag: null, body: reads.shift() }),
    formatTime: (value) => value,
    page: () => null,
    open() {},
    leave() {},
    focusedIn() {},
  });
  view.attach(parent, owner);
  view.controller.expand();
  await settle();
  const [line, , list] = view.group.children;
  const [spinner] = line.children;
  const painted = () => {
    const names = list.children.flatMap((row) =>
      row.children.filter((part) => part.classes.has("github-pull-file-name")),
    );
    return {
      breathing: view.group.classes.has("mb-refreshing-group"),
      // The rows stay usable, so the group is never marked busy.
      busy: view.group.getAttribute("aria-busy"),
      spinner: !spinner.hidden,
      line: line.hidden ? null : line.textContent,
      names: names.map((name) => name.children.map((text) => text.textContent).join("")),
      namesBreathe: names.every((name) => name.classes.has("mb-refreshing-text")),
    };
  };
  const asked = painted();
  answerAsk({ status: 202, etag: null, body: { files: listing("stale", true, false) } });
  await settle();
  const running = painted();
  reads.push(listing("current", false, true));
  const poll = [...timers].find(([, timer]) => timer.delay === 1000);
  assert.ok(poll, "a running refresh is read again in a second");
  timers.delete(poll[0]);
  poll[1].callback();
  await settle();
  const settled = painted();
  view.dispose();
  return { asked, running, settled };
}

/**
 * The view tells the tree which files the route can address, so a walk claims it will settle
 * on Changes only where an address will confirm it.
 *
 * @param {Function} mountFileTree
 */
async function walkClaims(mountFileTree) {
  globalThis.window = {
    setTimeout: () => Symbol(),
    clearTimeout() {},
    requestAnimationFrame: () => 1,
    cancelAnimationFrame() {},
  };
  document.body = new Element("body");
  document.activeElement = document.body;
  const parent = new Element("li");
  const owner = new Element("a");
  document.body.append(parent);
  parent.append(owner);
  const files = ["a.py", "b.py", "c\\d.py"];
  const claims = [];
  const view = mountFileTree({
    decorateExternalLink: require("./sdk-ref-fixture.js").refHelpers(document).decorateExternalLink,
    number: 7,
    autoExpandFiles: 3000,
    current: null,
    shown: true,
    scrollRoot: document.body,
    chevron: () => null,
    // As the route's encoder answers: no address for a segment with a backslash.
    href: (file) => (file.includes("\\") ? null : `/${file}`),
    request: async () => ({
      status: 200,
      etag: null,
      body: {
        state: "current",
        reason: null,
        number: 7,
        listed_from: "github",
        source: "https://github.com/octo/demo",
        generation: "0".repeat(32),
        fetched_at: "2026-11-03T00:00:00Z",
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
        offset: 0,
        limit: 3000,
        rows: files.map((file) => ({
          path: file,
          display: file,
          previous_path: null,
          previous_display: null,
          status: "modified",
          additions: 1,
          deletions: 0,
        })),
      },
    }),
    formatTime: (value) => value,
    page: () => ({
      fileForPath: () => ({ kind: "file" }),
      showFile: (file, how) => {
        claims.push([file, how?.settling === true]);
        return { kind: "jumped" };
      },
    }),
    open() {},
    leave() {},
    focusedIn() {},
  });
  view.attach(parent, owner);
  view.controller.expand();
  await settle();
  view.controller.focused("a.py");
  view.controller.move(1, { repeat: true });
  view.controller.move(1, { repeat: true });
  assert.deepEqual(claims, [
    ["b.py", true],
    ["c\\d.py", false],
  ]);
  view.dispose();
}
run()
  .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });
