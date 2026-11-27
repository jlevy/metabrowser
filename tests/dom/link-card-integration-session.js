// Browserless session for the link card across its boundaries: the exact shell tooltip, the
// exact registry, the exact providers, and the exact resolver, on one page.
//
// tests/dom/link-previews-session.js holds the card's rules on the module alone, and
// tests/dom/link-preview-providers-session.js the providers' on a stand-in registry. Every
// boundary there is a stand-in, which is how a card that came back after focus moved, an
// answer of nothing kept for the page's life, and an image's tooltip fighting its link's
// card each passed. Here one realm, as one page is, runs:
//
// - app.js's tooltip and its delegated listeners, lifted verbatim from its section comment
//   through the listener that ends a focus repair: `show`, `hide`, the short-tip listeners on
//   `mouseenter` and `mouseleave`, and the `focusin` listener that puts a tooltip away, with
//   the helpers they call (`esc`, `eventTargetElement`, `isPageElement`), lifted by name as
//   tests/dom/nav-reveal-session.js lifts them;
// - static/repository-links.js's `enhance` over a pull request's text in a KPress host, which
//   registers each link for its card;
// - static/link-previews.js and static/link-preview-providers.js, the card and its data, whose
//   every read replays the server's own answer (tests/fixtures/
//   link-preview-providers-responses.json, recorded by tests/test_link_preview_providers_session.py),
//   answered 40 ms later on this file's clock.
//
// The DOM is stand-ins that know their parent, their attributes, their text, the few
// selectors these modules ask, and the events the browser sends: a pointer that leaves one
// element and enters another sends `pointerout`, `mouseleave` for each element it left,
// `pointerover`, and `mouseenter` for each it entered, and focus sends `focusin`, each
// through the document's capture listeners first. The SDK is the shell's own surface where
// it draws the card (`mb.tooltip` is app.js's tooltip) and stand-ins elsewhere.
//
// It prints, for each step, what the reader would see; tests/test_link_card_integration_session.py
// holds its invariants, and this file exits 1 on a failed one, naming each session that
// failed. Name sessions on the command line to run only those.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticRoot = path.join(repoRoot, "src/metabrowser/static");
const appSource = fs.readFileSync(path.join(staticRoot, "app.js"), "utf8");
const recorded = JSON.parse(
  fs.readFileSync(
    path.join(repoRoot, "tests/fixtures/link-preview-providers-responses.json"),
    "utf8",
  ),
);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/** app.js's tooltip, from its section comment through its delegated listeners. */
const TOOLTIP_AND_LISTENERS =
  /\n\/\/ ── Custom tooltip[\s\S]*?\ndocument\.addEventListener\("pointerdown", endTooltipFocusRepair, true\);\n/;
const tooltipSource = appSource.match(TOOLTIP_AND_LISTENERS)?.[0];
assert(tooltipSource, "app.js's tooltip and its listeners were not found");

/** One top-level function of app.js, by name, as tests/dom/nav-reveal-session.js lifts one. */
function appFunction(name) {
  const match = new RegExp(`\\n(async )?function ${name}\\(`).exec(appSource);
  assert(match, `app.js ${name} is not extractable`);
  const start = match.index + 1;
  const end = appSource.indexOf("\n}\n", start);
  return appSource.slice(start, end + 2);
}

// ── The stand-in DOM ───────────────────────────────────────────────

class FakeText {
  constructor(text) {
    this.nodeType = 3;
    this.nodeValue = text;
    this.parentNode = null;
  }
  get textContent() {
    return this.nodeValue;
  }
}

/** Whether *element* matches one compound selector: `tag`, `.class`, `[attr]`, or `*`. */
function matches(element, selector) {
  if (selector === "*") {
    return true;
  }
  const parts = selector.match(/^([a-z]+)?((?:\.[\w-]+)*)((?:\[[\w-]+\])*)$/);
  assert(parts, `the stand-in DOM does not read ${selector}`);
  const [, tag, classes, attributes] = parts;
  if (tag && element.tagName !== tag.toUpperCase()) {
    return false;
  }
  const own = String(element.attributes.get("class") ?? "").split(/\s+/);
  for (const name of classes.split(".").filter(Boolean)) {
    if (!own.includes(name)) {
      return false;
    }
  }
  for (const [, name] of attributes.matchAll(/\[([\w-]+)\]/g)) {
    if (!element.attributes.has(name)) {
      return false;
    }
  }
  return true;
}

class FakeElement {
  constructor(tag, name = tag, attributes = {}) {
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.name = name;
    this.parentNode = null;
    this.childNodes = [];
    this.listeners = [];
    this.attributes = new Map(Object.entries(attributes));
    this.isDocument = false;
    this.style = {};
    this.innerHTML = "";
    this.classList = {
      contains: (value) =>
        String(this.attributes.get("class") ?? "")
          .split(/\s+/)
          .includes(value),
      add: (value) => {
        const own = new Set(String(this.attributes.get("class") ?? "").split(/\s+/));
        own.add(value);
        this.attributes.set("class", [...own].filter(Boolean).join(" "));
      },
      remove: (value) => {
        const own = String(this.attributes.get("class") ?? "")
          .split(/\s+/)
          .filter((each) => each && each !== value);
        this.attributes.set("class", own.join(" "));
      },
    };
    this.dataset = new Proxy(
      {},
      {
        get: (_target, key) =>
          this.attributes.get(
            `data-${String(key).replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`,
          ),
      },
    );
  }
  append(...nodes) {
    for (const item of nodes) {
      const node = typeof item === "string" ? new FakeText(item) : item;
      node.parentNode = this;
      this.childNodes.push(node);
    }
    return this;
  }
  appendChild(node) {
    this.append(node);
    return node;
  }
  get className() {
    return this.attributes.get("class") ?? "";
  }
  set className(value) {
    this.attributes.set("class", String(value));
  }
  get textContent() {
    return this.childNodes.map((node) => node.textContent).join("");
  }
  set textContent(text) {
    this.childNodes = [];
    this.append(String(text));
  }
  get lastElementChild() {
    return this.childNodes.findLast((node) => node.nodeType === 1) ?? null;
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  hasAttribute(name) {
    return this.attributes.has(name);
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  contains(other) {
    for (let at = other; at; at = at.parentNode) {
      if (at === this) {
        return true;
      }
    }
    return false;
  }
  get isConnected() {
    for (let at = this; at; at = at.parentNode) {
      if (at.isDocument) {
        return true;
      }
    }
    return false;
  }
  closest(selector) {
    for (let at = this; at && at.nodeType === 1; at = at.parentNode) {
      if (!at.isDocument && matches(at, selector)) {
        return at;
      }
    }
    return null;
  }
  /** Descendants matching one selector or a comma's list of them, in document order. */
  querySelectorAll(selector) {
    const selectors = selector.split(",").map((each) => each.trim());
    const found = [];
    const walk = (node) => {
      for (const child of node.childNodes) {
        if (child.nodeType === 1) {
          if (selectors.some((each) => matches(child, each))) {
            found.push(child);
          }
          walk(child);
        }
      }
    };
    walk(this);
    return found;
  }
  querySelector(selector) {
    return selector.startsWith(":scope") ? null : (this.querySelectorAll(selector)[0] ?? null);
  }
  addEventListener(type, listener, capture = false) {
    this.listeners.push({ type, listener, capture: capture === true || capture?.capture === true });
  }
  removeEventListener(type, listener) {
    this.listeners = this.listeners.filter(
      (each) => each.type !== type || each.listener !== listener,
    );
  }
  getBoundingClientRect() {
    return { left: 100, top: 100, right: 180, bottom: 120, width: 80, height: 20 };
  }
  get clientWidth() {
    return 0;
  }
  get scrollWidth() {
    return 0;
  }
  get clientHeight() {
    return 0;
  }
  get scrollHeight() {
    return 0;
  }
}

// ── The clock ──────────────────────────────────────────────────────

const settle = () => new Promise((resolve) => setImmediate(resolve));

function createClock() {
  let now = 0;
  let nextId = 1;
  const timers = new Map();
  return {
    get now() {
      return now;
    },
    setTimeout(callback, delay = 0) {
      const id = nextId++;
      timers.set(id, { at: now + Math.max(0, delay), callback });
      return id;
    },
    clearTimeout(id) {
      timers.delete(id);
    },
    /** Run every timer due by *end*, settling promises after each, as the event loop does. */
    async to(end) {
      await settle();
      for (;;) {
        const due = [...timers.entries()]
          .filter(([, timer]) => timer.at <= end)
          .sort((left, right) => left[1].at - right[1].at || left[0] - right[0])[0];
        if (!due) {
          break;
        }
        timers.delete(due[0]);
        now = due[1].at;
        due[1].callback();
        await settle();
      }
      now = Math.max(now, end);
    },
  };
}

// ── A page ─────────────────────────────────────────────────────────

const CANONICAL = "https://github.com/octo/demo";
const READ_MS = 40;
const BADGE = "https://img.example/badge.svg";

/** A card's lines as text: what a reader sees. */
function lines(html) {
  return html
    .split("</div>")
    .filter(Boolean)
    .map((line) =>
      line
        .replace(/<[^>]+>/g, "")
        .replaceAll("&lt;", "<")
        .replaceAll("&gt;", ">")
        .replaceAll("&quot;", '"')
        .replaceAll("&#39;", "'")
        .replaceAll("&amp;", "&"),
    )
    .join(" | ");
}

function createPage() {
  const clock = createClock();
  const log = [];
  const document = new FakeElement("html", "the page");
  document.isDocument = true;
  const body = new FakeElement("body", "the body");
  document.append(body);
  document.body = body;
  document.createElement = (tag) => new FakeElement(tag);

  // The served files, the catalog's snapshot of them, and the reads a provider makes.
  let files = ["README.md", "docs/guide.md"];
  const failing = new Set();
  const sdk = {
    repository: {
      host: "github.com",
      owner: "octo",
      name: "demo",
      branch: "main",
      revision: "a".repeat(40),
      served_prefix: "",
    },
    sourceKind: () => "filesystem",
    navigation: {
      href: (target) => `/view/${target.path}`,
      open: async () => {},
      openRoute: () => true,
    },
    fetchPluginData(plugin, route, params = {}) {
      const query = new URLSearchParams(
        Object.entries(params).map(([name, value]) => [name, String(value)]),
      ).toString();
      const name = `${route}${query ? `?${query}` : ""}`;
      log.push({ at: clock.now, read: `${plugin}/${name}` });
      return new Promise((resolve, reject) =>
        clock.setTimeout(() => {
          if (failing.delete(name)) {
            reject(new TypeError(`Failed to fetch ${name}`));
            return;
          }
          const answer = recorded[name];
          if (answer === undefined) {
            reject(new Error(`no recorded answer for ${name}`));
            return;
          }
          resolve(answer.body);
        }, READ_MS),
      );
    },
    ensureKindAssets: async () => {},
    prefetchCounterpart() {},
    fileCatalog: {
      snapshot: () => ({
        complete: true,
        truncated: false,
        files: [...files].sort().map((file) => ({ path: file })),
        observedCount: files.length,
        revision: 1,
        sourceSummary: {},
      }),
    },
    directoryTotals: { get: () => null },
    formatAge: () => ({ label: "" }),
    formatFileCount: (count) => `${count} files`,
    formatSize: (bytes) => `${bytes} B`,
    fileTypeIcon: () => ({ svg: "", className: "" }),
    decorateExternalLink: (anchor) => anchor,
    plugins: { load: () => new Promise(() => {}) },
  };

  const context = {
    AbortController,
    URL,
    URLSearchParams,
    TextEncoder,
    TextDecoder,
    btoa,
    atob,
    setTimeout: clock.setTimeout,
    clearTimeout: clock.clearTimeout,
    requestAnimationFrame: (callback) => clock.setTimeout(callback, 16),
    console: { warn: (message) => log.push({ at: clock.now, warned: String(message) }) },
    document,
    Element: FakeElement,
    HTMLElement: FakeElement,
    innerWidth: 1200,
    innerHeight: 800,
    metabrowser: sdk,
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(
    ["esc", "eventTargetElement", "isPageElement"].map(appFunction).join("\n") +
      tooltipSource +
      "\ninitTooltip();",
    context,
    { filename: "app.js (lifted)" },
  );
  // The shell's SDK draws a card on the shell's own tooltip (plugin-sdk.js, `tooltip`).
  sdk.tooltip = {
    show: (html, anchor) => context.MetabrowserTooltip.show(html, anchor),
    hide: (within) => context.MetabrowserTooltip.hide(within),
  };
  for (const name of [
    "formatters.js",
    "git-path.js",
    "repository-links.js",
    "link-previews.js",
    "link-preview-providers.js",
  ]) {
    const file = path.join(staticRoot, name);
    vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  }
  const tooltip = body.childNodes.find((node) => node.classList?.contains("custom-tooltip"));
  assert(tooltip, "app.js drew no tooltip");

  /**
   * A pull request's text as its page draws one: a KPress host holding the inert prose, each
   * link as the allowlist leaves it, then made what it opens by the exact resolver.
   */
  function text(...links) {
    const host = new FakeElement("div", "the KPress host", { class: "metabrowser-kpress-host" });
    const prose = new FakeElement("div", "the description", { class: "kpress-prose" });
    host.append(prose);
    body.append(host);
    const anchors = {};
    for (const [name, href, inner] of links) {
      const anchor = new FakeElement("a", name, {
        href,
        target: "_blank",
        rel: "noopener noreferrer",
      });
      anchor.append(...(inner ?? [`${name}`]));
      prose.append(anchor, " ");
      anchors[name] = anchor;
    }
    context.MetabrowserRepositoryLinks.enhance(prose, sdk);
    return { prose, anchors };
  }

  /** Dispatch *type* at *target*: the document's capture listeners, then up from *target*. */
  function dispatch(target, type, init = {}) {
    const event = {
      type,
      target,
      relatedTarget: null,
      pointerType: "mouse",
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...init,
    };
    for (const { type: listened, listener, capture } of document.listeners) {
      if (listened === type && capture) {
        listener(event);
      }
    }
    if (type === "mouseenter" || type === "mouseleave") {
      return;
    }
    for (let at = target; at; at = at.parentNode) {
      for (const { type: listened, listener, capture } of at.listeners) {
        if (listened === type && !(capture && at === document)) {
          listener(event);
        }
      }
    }
  }

  const chain = (node) => {
    const nodes = [];
    for (let at = node; at && !at.isDocument; at = at.parentNode) {
      nodes.push(at);
    }
    return nodes;
  };
  // The pointer, which leaves what it was on before it arrives, in the browser's order.
  let under = body;
  async function point(time, element) {
    await clock.to(time);
    if (under === element) {
      return;
    }
    const left = chain(under).filter((node) => !node.contains(element));
    const entered = chain(element).filter((node) => !node.contains(under));
    dispatch(under, "pointerout", { relatedTarget: element });
    for (const node of left) {
      dispatch(node, "mouseleave", { relatedTarget: element });
    }
    dispatch(element, "pointerover", { relatedTarget: under });
    for (const node of entered.reverse()) {
      dispatch(node, "mouseenter", { relatedTarget: under });
    }
    log.push({ at: clock.now, pointer: element.name });
    under = element;
  }
  /** Focus moves onto *element*, as a Tab or a click on it moves it. */
  async function focus(time, element) {
    await clock.to(time);
    log.push({ at: clock.now, focus: element.name });
    dispatch(element, "focusin");
  }
  /** What the reader sees now: the tooltip's lines, and the element it is placed on. */
  async function look(time) {
    await clock.to(time);
    const up = tooltip.style.display === "block" && tooltip.classList.contains("visible");
    const seen = up ? lines(tooltip.innerHTML) : null;
    log.push({ at: clock.now, sees: seen, ...(up ? { on: context.tooltipAnchor?.name } : {}) });
    return seen;
  }

  return {
    clock,
    log,
    body,
    sdk,
    text,
    point,
    focus,
    look,
    opens: context.MetabrowserLinkPreviews.OPENS,
    fail: (name) => failing.add(name),
    serve: (list) => {
      files = list;
    },
  };
}

// ── The sessions ───────────────────────────────────────────────────

const TITLES = Object.fromEntries(
  Object.entries(recorded)
    .filter(([name]) => name.startsWith("pulls?q="))
    .flatMap(([, answer]) => answer.body.rows.map((row) => [row.number, row.title])),
);
const pullLink = (number) => [`#${number}`, `${CANONICAL}/pull/${number}`];

/** A rest on a link to a pull request: its card, with the title its catalog row gives. */
async function rest() {
  const page = createPage();
  const { anchors } = page.text(pullLink(12));
  await page.point(0, anchors["#12"]);
  await page.look(299);
  const seen = await page.look(320);
  assert(
    seen?.includes(TITLES[12]) && page.log.at(-1).on === "#12",
    `a rest did not show the card with its title on time: ${seen}`,
  );
  await page.point(700, page.body);
  await page.look(900);
  assert(page.log.at(-1).sees === null, "the card stayed after the pointer left");
  return page.log;
}

/** Straight from one link's card onto the next: the next link's card, on the next link. */
async function handover() {
  const page = createPage();
  const { anchors } = page.text(pullLink(12), pullLink(13));
  await page.point(0, anchors["#12"]);
  await page.look(700);
  await page.point(720, anchors["#13"]);
  const seen = await page.look(1100);
  assert(
    seen?.includes(TITLES[13]) && page.log.at(-1).on === "#13",
    `straight from #12 onto #13, the card shown was not #13's: ${seen}`,
  );
  return page.log;
}

/** Focus moves onto the link while its read is out: the card does not come back. */
async function focusDuringRead() {
  const page = createPage();
  const { anchors } = page.text(pullLink(14));
  await page.point(0, anchors["#14"]);
  await page.focus(260, anchors["#14"]);
  await page.look(280);
  await page.look(700);
  const after = page.log.slice(page.log.findIndex((entry) => entry.focus));
  assert(
    page.log.some((entry) => entry.read?.startsWith("github/pulls?q=14")),
    "the rest asked for nothing before focus moved",
  );
  assert(!after.some((entry) => entry.sees), "a card came back after focus moved");
  return page.log;
}

/** A read that fails is read again at the next rest, which then says the title. */
async function retry() {
  const page = createPage();
  const { anchors } = page.text(pullLink(15));
  page.fail("pulls?q=15");
  await page.point(0, anchors["#15"]);
  const first = await page.look(700);
  await page.point(800, page.body);
  await page.point(1000, anchors["#15"]);
  const second = await page.look(1700);
  assert(first !== null && !first.includes(TITLES[15]), `a failed read gave a title: ${first}`);
  assert(second?.includes(TITLES[15]), `the next rest did not read again: ${second}`);
  return page.log;
}

/** A file the served tree gains after a rest that found it missing is not missing after. */
async function staleFile() {
  const page = createPage();
  const { anchors } = page.text(["the old guide", `${CANONICAL}/blob/main/docs/old-guide.md`]);
  await page.point(0, anchors["the old guide"]);
  const before = await page.look(700);
  await page.point(800, page.body);
  page.serve(["README.md", "docs/guide.md", "docs/old-guide.md"]);
  await page.point(1000, anchors["the old guide"]);
  const after = await page.look(1700);
  assert(before?.endsWith("Not in the served files"), `the missing file was not said: ${before}`);
  // A link to the served branch's file, which opens in the served working tree.
  assert(
    after?.endsWith(page.opens["working-tree"]) && !after.includes("Not in the served files"),
    `a file the tree gained was still called missing: ${after}`,
  );
  return page.log;
}

/**
 * An image the page did not load inside a link with a card: the pointer rests on the link's
 * words, crosses onto the image's chip and back, and the card, which says the image's
 * address, is the one tooltip the whole time. The chip's own tooltip is the shell's
 * (`tipTextAnchor` in app.js, which shows a chip's in rendered text).
 */
async function imageInLink() {
  const page = createPage();
  const chip = new FakeElement("span", "the badge's chip", {
    class: "mb-image-fallback",
    "data-tip-text": BADGE,
  });
  chip.append("build passing");
  const words = new FakeElement("span", "the link's words");
  words.append("the build ");
  const { anchors } = page.text(["#12", `${CANONICAL}/pull/12`, [words, chip]]);
  const link = anchors["#12"];
  await page.point(0, words);
  const seen = [await page.look(400)];
  await page.point(450, chip);
  seen.push(await page.look(800));
  await page.point(850, words);
  seen.push(await page.look(1200));
  assert(
    seen.every((card) => card?.includes(`Image from ${BADGE}`) && card.includes(TITLES[12])),
    `the card was not the one tooltip over the link and its image: ${JSON.stringify(seen)}`,
  );
  assert(
    page.log.filter((entry) => entry.sees).every((entry) => entry.on === link.name),
    "a tooltip was placed on something other than the link",
  );
  assert(chip.getAttribute("data-tip-text") === null, "the chip kept a tooltip of its own");
  return page.log;
}

/** A link to another site: one line saying where it goes, in a new tab as the text opens it. */
async function outside() {
  const page = createPage();
  const { anchors } = page.text(["elsewhere", "https://example.com/elsewhere"]);
  await page.point(0, anchors.elsewhere);
  const seen = await page.look(320);
  assert(seen === "Opens example.com in a new tab", `an outside link's card said ${seen}`);
  assert(!page.log.some((entry) => entry.read), "a rest on an outside link read something");
  return page.log;
}

const SESSIONS = {
  rest,
  handover,
  "focus during the read": focusDuringRead,
  "a failed read, then the next rest": retry,
  "a file the tree gains": staleFile,
  "an image inside a link": imageInLink,
  "a link to another site": outside,
};

/** Every session, or those named on the command line, each one's failure said as it ends. */
async function main() {
  const named = process.argv.slice(2);
  const transcript = {};
  const failed = [];
  for (const [name, session] of Object.entries(SESSIONS)) {
    if (named.length > 0 && !named.includes(name)) {
      continue;
    }
    try {
      transcript[name] = await session();
    } catch (error) {
      failed.push(`${name}: ${error.message}`);
    }
  }
  if (failed.length > 0) {
    throw new Error(`failed:\n${failed.join("\n")}`);
  }
  process.stdout.write(`${JSON.stringify(transcript, null, 1)}\n`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
