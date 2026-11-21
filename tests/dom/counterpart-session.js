// The View on GitHub button (docs/design-system.md, "View on GitHub"): the production
// `counterpartButton` and `mountCounterpart` from static/plugin-sdk-views.js, loaded with the
// SDK into a context of their own, over a stand-in DOM that keeps what the button reads of
// one: attributes, focus, `hidden`, listeners, and containment.
//
//   node tests/dom/counterpart-session.js
//
// It tells, as one JSON object for tests/golden/cli-ui-counterpart.tryscript.md:
//
// - `markup`: the button's tree, with the hooks the macOS app reads (mb-4wqh);
// - `menu`: the menu button's states through a click, the arrow keys, Home, End, Escape,
//   Tab, a second click, a press outside and inside, and chords held with Command,
//   Control, or Option, which are the browser's, and focus that leaves the button for
//   another element or for none, with where focus is, whether the menu is open, whether a
//   key's default was prevented or its propagation stopped, and how many listeners the
//   button holds on the document;
// - `copy`: Copy Link with a clipboard that takes the link, one that refuses it, and none,
//   and a second copy before the first one's confirmation ends, with the status line, a
//   polite live region, and the chevron's tooltip before and after its confirmation's time;
// - `mount`: what `mountCounterpart` asks the server and leaves in a corner, for an answer
//   with a counterpart, the same page again, a page with none, an answer that lands after
//   the corner was asked for another page, an address that is not https, a failed request,
//   a refused one, and another provider's answer; then a new corner for a page answered
//   before, drawn before any answer, an answer that changed since, and a page
//   `prefetchCounterpart` asked for first, asked once.
//
// The session asserts what it tells, so a change that breaks the contract fails here before
// the golden is read.

const assert = require("node:assert/strict");
const { createSdkSandbox } = require("./sdk-sandbox.js");

class Node {
  constructor() {
    this.parentNode = null;
    this.childNodes = [];
  }
  append(...nodes) {
    for (const node of nodes) {
      const child = typeof node === "string" ? new Text(node) : node;
      child.parentNode?.childNodes.splice(child.parentNode.childNodes.indexOf(child), 1);
      child.parentNode = this;
      this.childNodes.push(child);
    }
  }
  replaceChildren(...nodes) {
    for (const child of this.childNodes) {
      child.parentNode = null;
    }
    this.childNodes = [];
    this.append(...nodes);
  }
  contains(node) {
    for (let at = node; at !== null; at = at.parentNode) {
      if (at === this) {
        return true;
      }
    }
    return false;
  }
  get textContent() {
    return this.childNodes.map((child) => child.textContent).join("");
  }
  set textContent(value) {
    this.replaceChildren(String(value));
  }
}

class Text extends Node {
  constructor(data) {
    super();
    this.data = data;
  }
  get textContent() {
    return this.data;
  }
}

class Element extends Node {
  constructor(document, tag) {
    super();
    this.ownerDocument = document;
    this.tagName = tag.toUpperCase();
    this.attributes = new Map();
    this.dataset = {};
    this.listeners = new Map();
    this.hidden = false;
    this.html = "";
  }
  get className() {
    return this.attributes.get("class") ?? "";
  }
  set className(value) {
    this.attributes.set("class", value);
  }
  get type() {
    return this.attributes.get("type") ?? "";
  }
  set type(value) {
    this.attributes.set("type", value);
  }
  set innerHTML(value) {
    this.html = value;
  }
  get innerHTML() {
    return this.html;
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  hasAttribute(name) {
    return this.attributes.has(name);
  }
  addEventListener(type, listener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }
  removeEventListener(type, listener) {
    this.listeners.set(
      type,
      (this.listeners.get(type) ?? []).filter((held) => held !== listener),
    );
  }
  focus() {
    this.ownerDocument.activeElement = this;
  }
  get isConnected() {
    let at = this;
    while (at.parentNode !== null) {
      at = at.parentNode;
    }
    return at === this.ownerDocument.body;
  }
  /** The first descendant whose class list holds *selector*'s one class. */
  querySelector(selector) {
    assert.match(selector, /^\.[\w-]+$/, "the stand-in reads one class");
    const name = selector.slice(1);
    for (const child of this.childNodes) {
      if (child instanceof Element) {
        if (child.className.split(/\s+/).includes(name)) {
          return child;
        }
        const found = child.querySelector(selector);
        if (found !== null) {
          return found;
        }
      }
    }
    return null;
  }
  /** Dispatch *type* here and on each ancestor, as a bubbling event does. */
  dispatch(type, init = {}) {
    let stopped = false;
    let prevented = false;
    const event = {
      type,
      target: this,
      ...init,
      preventDefault() {
        prevented = true;
      },
      stopPropagation() {
        stopped = true;
      },
    };
    for (let at = this; at !== null && !stopped; at = at.parentNode) {
      for (const listener of at.listeners?.get(type) ?? []) {
        listener(event);
      }
    }
    return { prevented, stopped };
  }
}

function makeDocument() {
  const document = {
    activeElement: null,
    cookie: "",
    capturing: new Map(),
    createElement(tag) {
      return new Element(document, tag);
    },
    addEventListener(type, listener, capture) {
      if (capture === true) {
        document.capturing.set(type, [...(document.capturing.get(type) ?? []), listener]);
      }
    },
    removeEventListener(type, listener, capture) {
      if (capture === true) {
        document.capturing.set(
          type,
          (document.capturing.get(type) ?? []).filter((held) => held !== listener),
        );
      }
    },
    documentElement: { getAttribute: () => null },
    head: { append() {} },
  };
  document.body = new Element(document, "body");
  return document;
}

const URL_OF_PAGE =
  "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md";
const document = makeDocument();
const timers = [];
const clipboard = { written: [], answer: "takes" };
const sandbox = createSdkSandbox({
  document,
  MetabrowserIcons: {
    toggle: '<svg data-icon="toggle"></svg>',
    copy: '<svg data-icon="copy"></svg>',
  },
  navigator: {
    clipboard: {
      writeText(text) {
        clipboard.written.push(text);
        return clipboard.answer === "takes" ? Promise.resolve() : Promise.reject(new Error("no"));
      },
    },
  },
  setTimeout: (callback, ms) => {
    timers.push({ callback, ms });
    return timers.length;
  },
});
const mb = sandbox.metabrowser;
const settle = () => new Promise((resolve) => setImmediate(resolve));

/** An element as the transcript tells it: its tag, class, the attributes that matter. */
function describe(element) {
  const said = { tag: element.tagName.toLowerCase(), class: element.className };
  for (const [name, value] of element.attributes) {
    if (name !== "class") {
      said[name] = name === "data-mb-owner" ? "(page owner)" : value;
    }
  }
  for (const [name, value] of Object.entries(element.dataset)) {
    said[`dataset.${name}`] = value;
  }
  if (element.hidden) {
    said.hidden = true;
  }
  if (element.html) {
    // A glyph's drawing is the icon catalog's; its opening says which it is.
    said.html = element.html.length > 48 ? `${element.html.slice(0, 48)}…` : element.html;
  }
  const children = element.childNodes.map((child) =>
    child instanceof Element ? describe(child) : child.textContent,
  );
  if (children.length > 0) {
    said.children = children;
  }
  return said;
}

const button = mb.counterpartButton({
  provider: "github",
  label: "View on GitHub",
  url: URL_OF_PAGE,
});
document.body.append(button);
const open = button.querySelector(".counterpart-open");
const more = button.querySelector(".counterpart-more");
const menu = button.querySelector(".counterpart-menu");
const status = button.querySelector(".counterpart-status");
const [copy, external] = menu.childNodes;
const markup = describe(button);
for (const item of [copy, external]) {
  assert.equal(sandbox.MetabrowserPluginHost.ownsElement(item), true);
  assert.equal(item.querySelector(".menu-item-icon").getAttribute("aria-hidden"), "true");
}
assert.equal(copy.querySelector(".menu-item-icon").html, sandbox.MetabrowserIcons.copy);
assert.match(external.querySelector(".menu-item-icon").html, /M7 17 17 7/);
assert.throws(() => mb.externalLinkMenuItems("javascript:alert(1)"), /needs an HTTP or HTTPS URL/);
// The status line is a polite live region from the start, and empty.
assert.equal(status.getAttribute("role"), "status");
assert.equal(status.textContent, "");
// The app's hooks (mb-4wqh), exactly.
assert.equal(button.getAttribute("data-view-on-github"), "");
assert.equal(open.getAttribute("data-web-view"), "open");
assert.equal(open.getAttribute("href"), URL_OF_PAGE);
assert.equal(external.getAttribute("data-web-view"), "external");
assert.equal(external.getAttribute("href"), URL_OF_PAGE);
assert.equal(external.getAttribute("target"), "_blank");
assert.equal(external.getAttribute("rel"), "noopener");

/** Where focus is, by the element's words. */
function focusName() {
  const active = document.activeElement;
  if (active === more) {
    return "the chevron";
  }
  if (active === null) {
    return "nothing";
  }
  if (active === document.body) {
    return "the page";
  }
  if (active.tagName === "IFRAME") {
    return "a frame";
  }
  return active.textContent || active.className;
}
/** The menu's state after *step*, with what the event's handling did. */
function state(step, handled = null) {
  return {
    step,
    menu: menu.hidden ? "closed" : "open",
    expanded: more.getAttribute("aria-expanded"),
    focus: focusName(),
    outsideListeners: (document.capturing.get("pointerdown") ?? []).length,
    ...(handled === null ? {} : handled),
  };
}
const key = (element, name) => element.dispatch("keydown", { key: name });
const press = (target) => {
  for (const listener of document.capturing.get("pointerdown") ?? []) {
    listener({ type: "pointerdown", target });
  }
};

const steps = [];
steps.push(state("drawn"));
steps.push(state("a click on the chevron", more.dispatch("click")));
steps.push(state("ArrowDown", key(document.activeElement, "ArrowDown")));
steps.push(state("ArrowDown again, past the last item", key(document.activeElement, "ArrowDown")));
steps.push(state("ArrowUp, past the first item", key(document.activeElement, "ArrowUp")));
steps.push(state("Home", key(document.activeElement, "Home")));
steps.push(state("End", key(document.activeElement, "End")));
steps.push(state("a letter", key(document.activeElement, "a")));
steps.push(state("Escape", key(document.activeElement, "Escape")));
steps.push(state("ArrowDown on the chevron", key(more, "ArrowDown")));
steps.push(state("Escape", key(document.activeElement, "Escape")));
steps.push(state("ArrowUp on the chevron", key(more, "ArrowUp")));
steps.push(state("Tab", key(document.activeElement, "Tab")));
steps.push(state("a click on the chevron", more.dispatch("click")));
steps.push(state("a click on the chevron again", more.dispatch("click")));
more.dispatch("click");
// A press moves focus where it lands in a browser, which the stand-in leaves to the step.
press(copy);
steps.push(state("a press on an item, inside the button"));
press(document.body);
steps.push(state("a press outside the button"));
more.dispatch("click");
external.dispatch("click");
steps.push(state("a click on Open in Browser"));
// A chord is the browser's (mb-i1wy): it neither opens the menu nor moves in it, and
// Option-Tab, with which Safari moves focus, closes it as Tab does.
const chord = (element, name, held) => element.dispatch("keydown", { key: name, [held]: true });
steps.push(state("Command-ArrowDown on the chevron", chord(more, "ArrowDown", "metaKey")));
more.dispatch("click");
steps.push(state("Control-End", chord(document.activeElement, "End", "ctrlKey")));
steps.push(state("Command-Escape", chord(document.activeElement, "Escape", "metaKey")));
steps.push(state("Option-Tab", chord(document.activeElement, "Tab", "altKey")));
// Focus that leaves the button: for another element, such as a framed preview a click went
// into, which sends the document no press, the menu closes once focus has landed; for none,
// a press outside has closed it, and a press inside leaves it open.
const frame = document.createElement("iframe");
document.body.append(frame);
const leave = (to) => {
  timers.length = 0;
  document.activeElement.dispatch("focusout");
  to.focus();
  for (const timer of timers.splice(0)) {
    timer.callback();
  }
};
more.dispatch("click");
leave(frame);
steps.push(state("focus into a frame"));
more.dispatch("click");
leave(document.body);
steps.push(state("focus to nothing"));
press(document.body);
assert.deepEqual(steps.map(({ step, menu: shown, focus }) => [step, shown, focus]).slice(1, 13), [
  ["a click on the chevron", "open", "Copy Link"],
  ["ArrowDown", "open", "Open in Browser"],
  ["ArrowDown again, past the last item", "open", "Copy Link"],
  ["ArrowUp, past the first item", "open", "Open in Browser"],
  ["Home", "open", "Copy Link"],
  ["End", "open", "Open in Browser"],
  ["a letter", "open", "Open in Browser"],
  ["Escape", "closed", "the chevron"],
  ["ArrowDown on the chevron", "open", "Copy Link"],
  ["Escape", "closed", "the chevron"],
  ["ArrowUp on the chevron", "open", "Open in Browser"],
  ["Tab", "closed", "Open in Browser"],
]);
assert.deepEqual(
  steps.slice(13).map(({ step, menu: shown, focus }) => [step, shown, focus]),
  [
    ["a click on the chevron", "open", "Copy Link"],
    ["a click on the chevron again", "closed", "the chevron"],
    ["a press on an item, inside the button", "open", "Copy Link"],
    ["a press outside the button", "closed", "Copy Link"],
    ["a click on Open in Browser", "closed", "the chevron"],
    ["Command-ArrowDown on the chevron", "closed", "the chevron"],
    ["Control-End", "open", "Copy Link"],
    ["Command-Escape", "open", "Copy Link"],
    ["Option-Tab", "closed", "Copy Link"],
    ["focus into a frame", "closed", "a frame"],
    ["focus to nothing", "open", "the page"],
  ],
);
assert.ok(
  steps
    .filter(({ step }) => /^(Command|Control|Option)-/.test(step))
    .every(({ prevented, stopped }) => prevented === false && stopped === false),
  "a chord's default is the browser's",
);
assert.ok(steps.every((step) => step.outsideListeners === (step.menu === "open" ? 1 : 0)));

async function copySteps() {
  const told = [];
  const tip = () => more.dataset.tipText;
  const said = () => [status.textContent, status.dataset.result ?? null];
  for (const answer of ["takes", "refuses", "none"]) {
    clipboard.answer = answer;
    const held = sandbox.navigator.clipboard;
    if (answer === "none") {
      sandbox.navigator.clipboard = undefined;
    }
    timers.length = 0;
    more.dispatch("click");
    copy.dispatch("click");
    await settle();
    const after = state(
      `Copy Link, a clipboard that ${answer === "none" ? "is not there" : answer}`,
    );
    after.tip = tip();
    after.status = said();
    after.confirmedFor = timers.map((timer) => timer.ms);
    for (const timer of timers.splice(0)) {
      timer.callback();
    }
    after.tipAfter = tip();
    after.statusAfter = said();
    told.push(after);
    sandbox.navigator.clipboard = held;
  }
  // A second copy before the first one's confirmation ends keeps its own time.
  clipboard.answer = "takes";
  timers.length = 0;
  more.dispatch("click");
  copy.dispatch("click");
  await settle();
  more.dispatch("click");
  copy.dispatch("click");
  await settle();
  const twice = state("Copy Link twice, the first confirmation's time ending");
  timers.shift().callback();
  twice.statusBetween = said();
  timers.shift().callback();
  twice.statusAfter = said();
  told.push(twice);
  told.push({ written: clipboard.written });
  return told;
}

async function mountSteps() {
  const told = [];
  const asked = [];
  /** @type {Map<string, {status: number, body?: unknown, wait?: Promise<void>, throws?: boolean}>} */
  const answers = new Map();
  sandbox.fetch = async (url) => {
    asked.push(url);
    const page = decodeURIComponent(url.split("page=")[1]);
    const answer = answers.get(page);
    await answer.wait;
    if (answer.throws) {
      throw new TypeError("the server went away");
    }
    return {
      ok: answer.status >= 200 && answer.status < 300,
      status: answer.status,
      json: async () => answer.body,
    };
  };
  const counterpart = (url, provider = "github", label = "View on GitHub") => ({
    status: 200,
    body: { counterpart: { provider, label, url }, reason: null },
  });
  const corner = document.createElement("span");
  corner.className = "view-header-end";
  document.body.append(corner);
  const tell = async (step, page) => {
    asked.length = 0;
    const returned = await mb.mountCounterpart(corner, page);
    const shown = corner.querySelector(".counterpart");
    const link = shown?.querySelector(".counterpart-open") ?? null;
    told.push({
      step,
      asked: [...asked],
      returned:
        returned === null ? null : returned === shown ? "the button in the corner" : "another",
      corner: shown === null ? "empty" : link.getAttribute("href"),
      hook:
        shown === null
          ? null
          : [...shown.attributes.keys()].find((name) => name.startsWith("data-view-on-")),
      label: link?.textContent ?? null,
    });
  };
  answers.set("/view/README.md", counterpart(URL_OF_PAGE));
  await tell("a page with a counterpart", "/view/README.md");
  const drawn = corner.querySelector(".counterpart");
  await tell("the same page again", "/view/README.md");
  assert.equal(corner.querySelector(".counterpart"), drawn, "the same page keeps its button");
  answers.set("/view/notes.txt", { status: 200, body: { counterpart: null, reason: "untracked" } });
  await tell("a page with none", "/view/notes.txt");
  // A page asked for and then another before its answer lands: the late answer is dropped.
  let land = () => {};
  answers.set("/pull/7", {
    ...counterpart("https://github.com/octo/demo/pull/7"),
    wait: new Promise((resolve) => (land = resolve)),
  });
  answers.set("/pull/7/files", counterpart("https://github.com/octo/demo/pull/7/files"));
  asked.length = 0;
  const late = mb.mountCounterpart(corner, "/pull/7");
  await tell("another page asked before the first answers", "/pull/7/files");
  land();
  const dropped = await late;
  told.push({
    step: "the first answer lands late",
    returned: dropped,
    corner: corner.querySelector(".counterpart-open").getAttribute("href"),
  });
  answers.set("/view/http.md", counterpart("http://github.com/octo/demo/blob/0/http.md"));
  await tell("an answer whose address is not https", "/view/http.md");
  answers.set("/view/script.md", counterpart("javascript:alert(1)"));
  await tell("an answer whose address is a script", "/view/script.md");
  answers.set("/view/README.md", counterpart(URL_OF_PAGE));
  await tell("a page with a counterpart", "/view/README.md");
  answers.set("/view/gone.md", { status: 200, throws: true });
  await tell("a request that fails", "/view/gone.md");
  answers.set("/view/README.md", counterpart(URL_OF_PAGE));
  await tell("a page with a counterpart", "/view/README.md");
  answers.set("/view/refused.md", { status: 400, body: { error: "page must be a path" } });
  await tell("a request the server refuses", "/view/refused.md");
  answers.set(
    "/view/elsewhere.md",
    counterpart("https://gitlab.com/octo/demo/-/blob/0/elsewhere.md", "gitlab", "View on GitLab"),
  );
  await tell("another provider's answer", "/view/elsewhere.md");
  answers.set("/view/a b#c.md", { status: 200, body: { counterpart: null, reason: "missing" } });
  await tell("a page with a space and a hash", "/view/a b#c.md");
  // A new corner, as a repaint or a return to a page draws: a page answered before is
  // drawn before its promise is returned, and asked again; the same answer keeps the
  // button, and one that changed replaces it.
  const again = document.createElement("span");
  again.className = "view-header-end";
  document.body.append(again);
  const redraw = async (step, page) => {
    asked.length = 0;
    const promised = mb.mountCounterpart(again, page);
    const before = again.querySelector(".counterpart");
    const returned = await promised;
    const after = again.querySelector(".counterpart");
    told.push({
      step,
      drawnBeforeTheAnswer:
        before === null
          ? "nothing"
          : before.querySelector(".counterpart-open").getAttribute("href"),
      asked: [...asked],
      corner:
        after === null ? "empty" : after.querySelector(".counterpart-open").getAttribute("href"),
      sameButton: before !== null && before === after && returned === after,
    });
  };
  answers.set("/view/README.md", counterpart(URL_OF_PAGE));
  await redraw("a new corner for a page answered before", "/view/README.md");
  const moved =
    "https://github.com/octo/demo/blob/89abcdef0123456789abcdef0123456789abcdef/README.md";
  answers.set("/view/README.md", counterpart(moved));
  again.replaceChildren();
  const fresh = document.createElement("span");
  fresh.className = "view-header-end";
  document.body.append(fresh);
  asked.length = 0;
  const changing = mb.mountCounterpart(fresh, "/view/README.md");
  const stale = fresh.querySelector(".counterpart-open")?.getAttribute("href");
  await changing;
  told.push({
    step: "a page whose answer changed since",
    drawnBeforeTheAnswer: stale ?? "nothing",
    asked: [...asked],
    corner: fresh.querySelector(".counterpart-open").getAttribute("href"),
  });
  answers.set(
    "/view/docs/",
    counterpart("https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567/docs"),
  );
  // Asked for as the page starts loading: an answer that lands before the header is
  // drawn with it, and one still in flight is waited for; either is asked for once.
  for (const [step, page, lands] of [
    ["a page whose answer came before its header", "/view/docs/", true],
    ["a page whose answer is in flight when its header is drawn", "/view/src/", false],
  ]) {
    answers.set(
      page,
      counterpart(
        `https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567${page.slice(5, -1)}`,
      ),
    );
    asked.length = 0;
    mb.prefetchCounterpart(page);
    if (lands) {
      await settle();
    }
    const prefetched = [...asked];
    again.replaceChildren();
    const corner = document.createElement("span");
    corner.className = "view-header-end";
    document.body.append(corner);
    asked.length = 0;
    const promised = mb.mountCounterpart(corner, page);
    const before = corner.querySelector(".counterpart-open")?.getAttribute("href") ?? "nothing";
    await promised;
    told.push({
      step,
      drawnBeforeTheAnswer: before,
      asked: [...prefetched, ...asked],
      corner: corner.querySelector(".counterpart-open").getAttribute("href"),
    });
  }
  return told;
}

async function run() {
  const copyTold = await copySteps();
  assert.deepEqual(
    copyTold
      .slice(0, 3)
      .map(({ tip, tipAfter, focus, menu: shown }) => [tip, tipAfter, focus, shown]),
    [
      ["Link copied", "Copy Link or Open in Browser", "the chevron", "closed"],
      ["Copy failed", "Copy Link or Open in Browser", "the chevron", "closed"],
      ["Copy failed", "Copy Link or Open in Browser", "the chevron", "closed"],
    ],
  );
  assert.deepEqual(
    copyTold.slice(0, 3).map(({ status: shown, statusAfter }) => [shown, statusAfter]),
    [
      [
        ["Link copied", "copied"],
        ["", null],
      ],
      [
        ["Copy failed", "failed"],
        ["", null],
      ],
      [
        ["Copy failed", "failed"],
        ["", null],
      ],
    ],
  );
  assert.deepEqual(
    [copyTold[3].statusBetween, copyTold[3].statusAfter],
    [
      ["Link copied", "copied"],
      ["", null],
    ],
  );
  const mountTold = await mountSteps();
  const byStep = Object.fromEntries(mountTold.map((step) => [step.step, step]));
  const answered = byStep["a new corner for a page answered before"];
  assert.equal(answered.drawnBeforeTheAnswer, URL_OF_PAGE);
  assert.equal(answered.asked.length, 1);
  assert.equal(answered.sameButton, true);
  const changed = byStep["a page whose answer changed since"];
  assert.equal(changed.drawnBeforeTheAnswer, URL_OF_PAGE);
  assert.notEqual(changed.corner, URL_OF_PAGE);
  const came = byStep["a page whose answer came before its header"];
  assert.equal(came.drawnBeforeTheAnswer, came.corner, "an answer in hand comes with the header");
  assert.equal(came.asked.length, 1, "a prefetched page is asked once");
  const flying = byStep["a page whose answer is in flight when its header is drawn"];
  assert.equal(flying.asked.length, 1, "a request in flight is waited for, not repeated");
  process.stdout.write(
    `${JSON.stringify({ markup, menu: steps, copy: copyTold, mount: mountTold }, null, 2)}\n`,
  );
}

run().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
