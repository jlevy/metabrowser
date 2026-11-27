// Browserless session for the link card (static/link-previews.js).
//
// The exact production module runs whole, beside the scripts its bundle and page give it:
// the shell's formatters (static/formatters.js, a startup script), and the GitPath codec
// and the resolver (static/git-path.js, static/repository-links.js) that the
// `repository-links` bundle loads ahead of it. The page's one tooltip is app.js's own,
// lifted verbatim from its section comment through the block that publishes it, as
// tests/dom/tooltip-anchor-session.js lifts it, so `show` and `hide` behave as they do on
// the page. Timers run on this file's clock, so each step says how much time has passed.
// The DOM is stand-ins that know their parent, their text, and whether they are in the
// document; the SDK's glyph owners are stand-ins whose glyphs name themselves
// (`data-glyph`), since what the card owes them is which glyph it asks for.
//
// It prints what `subject` reads from the resolver's answers, what `card` draws for each
// kind with and without a provider's data, and pointer rests: the card's timing, one read
// and one prefetch at a time and none aborted, focus and touch showing nothing, a state
// shown only with data, a late answer kept for the next rest, providers that fail, and
// `dispose` putting away only its own root's card. tests/test_link_previews_js.py holds
// its invariants; this file exits 1 on a failed one.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticRoot = path.join(repoRoot, "src/metabrowser/static");
const appSource = fs.readFileSync(path.join(staticRoot, "app.js"), "utf8");
const TOOLTIP_BLOCK =
  /\n\/\/ ── Custom tooltip[\s\S]*?\n {2}window\.MetabrowserTooltip = \{[\s\S]*?\n {2}\};\n\}\n/;
const tooltipBlock = appSource.match(TOOLTIP_BLOCK);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

assert(tooltipBlock, "the tooltip block was not found in app.js");

const SERVED = "a".repeat(40);
const PINNED = "c".repeat(40);
const COMMIT = "0123456789abcdef0123456789abcdef01234567";
const STATE_MARK = /data-state="/;

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

class FakeElement {
  constructor(tag, name = tag) {
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.name = name;
    this.parentNode = null;
    this.childNodes = [];
    this.listeners = new Map();
    this.attributes = new Map();
    this.innerHTML = "";
    this.isDocument = false;
  }
  append(...nodes) {
    for (const item of nodes) {
      const node = typeof item === "string" ? new FakeText(item) : item;
      node.parentNode = this;
      this.childNodes.push(node);
    }
    return this;
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
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  hasAttribute(name) {
    return this.attributes.has(name);
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  /** Descendants by one class and one attribute, `.name[attribute]`, the module's one query. */
  querySelectorAll(selector) {
    const match = /^\.([\w-]+)\[([\w-]+)\]$/.exec(selector);
    assert(match, `the stand-in does not read ${selector}`);
    const found = [];
    const walk = (node) => {
      for (const child of node.childNodes ?? []) {
        const classes = String(child.attributes?.get("class") ?? "").split(/\s+/);
        if (classes.includes(match[1]) && child.attributes.has(match[2])) {
          found.push(child);
        }
        walk(child);
      }
    };
    walk(this);
    return found;
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
  closest() {
    return null;
  }
  addEventListener(type, listener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }
  removeEventListener(type, listener) {
    this.listeners.set(
      type,
      (this.listeners.get(type) ?? []).filter((each) => each !== listener),
    );
  }
  getBoundingClientRect() {
    return { left: 100, top: 100, bottom: 120, width: 80 };
  }
}

/** Dispatch *type* at *target*, bubbling through its parents, as the browser does. */
function dispatch(target, type, init = {}) {
  const event = { type, target, relatedTarget: null, pointerType: "mouse", ...init };
  for (let at = target; at; at = at.parentNode) {
    for (const listener of at.listeners?.get(type) ?? []) {
      listener(event);
    }
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

/** A card's lines as text, a line's mark named first: what a reader sees, compactly. */
function lines(html) {
  return html
    .split("</div>")
    .filter(Boolean)
    .map((line) => {
      const glyph = /data-glyph="([^"]+)"/.exec(line)?.[1];
      const text = line
        .replace(/<[^>]+>/g, "")
        .replaceAll("&lt;", "<")
        .replaceAll("&gt;", ">")
        .replaceAll("&quot;", '"')
        .replaceAll("&#39;", "'")
        .replaceAll("&amp;", "&");
      return glyph ? `[${glyph}] ${text}` : text;
    })
    .join(" | ");
}

function createPage(options = {}) {
  const clock = createClock();
  const log = [];
  const warnings = [];
  const document = new FakeElement("body");
  document.isDocument = true;
  document.createElement = (tag) => new FakeElement(tag);

  // The page's one tooltip: app.js's own code.
  const classes = new Set();
  const tooltipElement = {
    innerHTML: "",
    style: {},
    classList: { add: (name) => classes.add(name), remove: (name) => classes.delete(name) },
    getBoundingClientRect: () => ({ width: 100, height: 20 }),
  };
  const shell = {
    clearTimeout: clock.clearTimeout,
    setTimeout: clock.setTimeout,
    requestAnimationFrame: (callback) => clock.setTimeout(callback, 16),
    document: { body: { appendChild() {} }, createElement: () => tooltipElement },
    Element: FakeElement,
    innerHeight: 800,
    innerWidth: 1200,
  };
  shell.window = shell;
  vm.createContext(shell);
  vm.runInContext(`${tooltipBlock[0]}\ninitTooltip();`, shell, { filename: "app.js (lifted)" });
  const shown = () =>
    tooltipElement.style.display === "block" && classes.has("visible")
      ? lines(tooltipElement.innerHTML)
      : null;

  // The github plugin's export, its glyph naming the state it draws.
  const github = {
    pullStateIcon: (state, { named }) => ({
      outerHTML: `<span class="github-pull-state-icon" data-state="${state}"${named === false ? ' aria-hidden="true"' : ""}><svg data-glyph="${state}"></svg></span>`,
    }),
  };
  const mb = {
    repository: {
      host: "github.com",
      owner: "example",
      name: "docs",
      branch: "main",
      revision: SERVED,
      served_prefix: "",
    },
    sourceKind: () => options.sourceKind ?? "filesystem",
    fileTypeIcon: (file) => {
      const extension = file.includes(".") ? file.split(".").pop() : "";
      return {
        svg: `<svg data-glyph="${extension || "file"}"></svg>`,
        className: extension ? `ft-${extension}` : "",
      };
    },
    // decorateExternalLink's mark on a pull request's address: the supplied icon, or the
    // neutral pull request glyph.
    decorateExternalLink(anchor, decoration = {}) {
      const node = new FakeElement("span");
      node.innerHTML = decoration.icon
        ? decoration.icon.outerHTML
        : '<svg data-glyph="pull"></svg>';
      anchor.append(node);
      return anchor;
    },
    plugins: {
      load: (name) => {
        log.push({ at: clock.now, load: name });
        return new Promise((resolve) => clock.setTimeout(() => resolve(github), 5));
      },
    },
    tooltip: {
      show(html, anchor) {
        log.push({ at: clock.now, show: anchor?.name ?? null, card: lines(html) });
        shell.MetabrowserTooltip.show(html, anchor);
      },
      hide(within) {
        log.push({ at: clock.now, hide: within?.name ?? null });
        shell.MetabrowserTooltip.hide(within);
      },
    },
  };

  const sandbox = {
    AbortController,
    URL,
    TextEncoder,
    TextDecoder,
    btoa,
    atob,
    clearTimeout: clock.clearTimeout,
    setTimeout: clock.setTimeout,
    console: {
      warn: (message, error) => warnings.push(`${message}: ${error?.message ?? error}`),
    },
    // The page's document, which the module listens on for the reader's presses and focus.
    document,
    metabrowser: mb,
    MetabrowserIcons: { layers: '<svg data-glyph="layers"></svg>' },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  for (const name of ["formatters.js", "git-path.js", "repository-links.js", "link-previews.js"]) {
    const file = path.join(staticRoot, name);
    vm.runInContext(fs.readFileSync(file, "utf8"), sandbox, { filename: file });
  }
  const previews = sandbox.MetabrowserLinkPreviews;
  // app.js's own focus listener, lifted with the tooltip, on the same document: focus moving
  // puts the pointer's tooltip away. It listens in the bubbling phase, after the module's.
  document.addEventListener("focusin", (event) => shell.hideTooltipOnFocus(event));

  /** A root of rendered text holding one link per `[name, words, target, options]`. */
  function text(rootName, ...entries) {
    const root = new FakeElement("div", rootName);
    document.append(root);
    const anchors = {};
    for (const [name, words, target, registration] of entries) {
      const anchor = new FakeElement("a", name);
      anchor.append(new FakeElement("span", `${name}'s words`).append(words));
      root.append(anchor);
      previews.register(root, anchor, target, mb, registration);
      anchors[name] = anchor;
    }
    return { root, anchors };
  }

  // The pointer, which leaves what it was on before it arrives, in the browser's order.
  let under = document;
  async function point(time, element, init = {}) {
    await clock.to(time);
    if (under !== element) {
      dispatch(under, "pointerout", { relatedTarget: element, ...init });
      dispatch(element, "pointerover", { relatedTarget: under, ...init });
      under = element;
    }
  }
  async function look(time) {
    await clock.to(time);
    log.push({ at: clock.now, tooltip: shown() });
  }
  /** The reader acts at *time* on *element*: `focus` (a Tab), or `press` (a click). */
  async function act(time, element, what) {
    await clock.to(time);
    log.push({ at: clock.now, [what]: element.name });
    if (what === "press") {
      dispatch(element, "pointerdown");
    }
    dispatch(element, "focusin");
  }

  return { clock, log, warnings, document, mb, previews, sandbox, text, point, look, act };
}

/**
 * A provider whose reads and prefetches take *delays* ms, recording what it is asked. It
 * keeps what it read, as a provider does since the registry keeps nothing, and answers that
 * at once: from `summary`, logged as `kept`, and from `known`, which the pointer's arrival
 * asks. `signals` counts the calls given anything that could abort a read.
 */
function stub(page, answer, delays = { summary: 1, prefetch: 1 }) {
  const counts = { reads: 0, prefetches: 0, maxReads: 0, maxPrefetches: 0, signals: 0 };
  const kept = new Map();
  const provider = {
    summary(subject, how) {
      assert(how.mb === page.mb, "a provider was not given the surface's SDK");
      counts.signals += "signal" in how ? 1 : 0;
      const key = label(subject);
      if (kept.has(key)) {
        page.log.push({ at: page.clock.now, summary: key, kept: true });
        return Promise.resolve(kept.get(key));
      }
      counts.reads += 1;
      counts.maxReads = Math.max(counts.maxReads, counts.reads);
      page.log.push({ at: page.clock.now, summary: key });
      return new Promise((resolve) =>
        page.clock.setTimeout(() => {
          counts.reads -= 1;
          const value = typeof answer === "function" ? answer(subject) : answer;
          kept.set(key, value);
          resolve(value);
        }, delays.summary),
      );
    },
    known(subject) {
      return kept.get(label(subject)) ?? null;
    },
    prefetch(subject) {
      counts.prefetches += 1;
      counts.maxPrefetches = Math.max(counts.maxPrefetches, counts.prefetches);
      page.log.push({ at: page.clock.now, prefetch: label(subject) });
      return new Promise((resolve) =>
        page.clock.setTimeout(() => {
          counts.prefetches -= 1;
          resolve();
        }, delays.prefetch),
      );
    },
  };
  return { provider, counts };
}

/** @param {Record<string, unknown>} subject */
function label(subject) {
  return Object.values(subject)
    .filter((value) => value !== "")
    .join(" ");
}

/** A pull request's route, as the resolver answers one. */
function pullRoute(number, tab = "", file = "") {
  return {
    kind: "route",
    href: `/pull/${number}${tab ? `/${tab}` : ""}`,
    localization: "pull",
    pull: { number, tab, file, stack: false },
  };
}

// ── What a target names ────────────────────────────────────────────

function subjects() {
  const page = createPage();
  const links = page.sandbox.MetabrowserRepositoryLinks;
  const previews = page.previews;
  const checkout = page.mb.repository;
  const pin = { ...checkout, revision: PINNED };
  const base = "https://github.com/example/docs";
  const rows = [];
  const read = (name, target, sourceKind) => {
    rows.push({ label: name, subject: previews.subject(target, sourceKind) });
  };
  const local = (url, context, options) => links.localize(`${base}${url}`, context, options);
  const folder = { sourceKind: "filesystem" };
  read("a pull request", local("/pull/12", checkout, folder), "filesystem");
  read("its Changes", local("/pull/12/changes", checkout, folder), "filesystem");
  read("its Checks", local("/pull/12/checks", checkout, folder), "filesystem");
  for (const stack of [false, true]) {
    const text = {
      head: PINNED,
      changes: { number: stack ? 3 : 7, stack, files: new Set(["src/app.py"]) },
    };
    read(
      stack ? "a changed file in a stack's note" : "a changed file in a pull request's text",
      local("/pull/src/app.py", checkout, { sourceKind: "filesystem", text, pathRelative: true }),
      "filesystem",
    );
  }
  read("a commit", local(`/commit/${COMMIT}`, checkout, folder), "filesystem");
  read("the pull request list", local("/pulls", checkout, folder), "filesystem");
  read("a file on the served branch", local("/blob/main/docs/guide.md", checkout, folder));
  read("a file at the served commit", local(`/blob/${SERVED}/docs/guide.md`, checkout, folder));
  read("a folder on the served branch", local("/tree/main/docs", checkout, folder));
  read("the repository", local("", checkout, folder));
  read("a name holding %", local("/blob/main/docs/100%25.md", checkout, folder), "filesystem");
  read(
    "a file with a query and an anchor",
    local("/blob/main/docs/guide.md?plain=1#install", checkout, folder),
    "filesystem",
  );
  const pinned = local(`/blob/${PINNED}/docs/guide.md`, pin, { sourceKind: "git_revision" });
  rows.push({ label: "a pin's address for it", path: pinned.target.path });
  read("the same file on the pin", pinned, "git_revision");
  // A link to the served branch on a pin opens the path at the pinned revision, which is
  // what the pin serves: not a working tree.
  read(
    "a file on the served branch, on a pin",
    local("/blob/main/docs/guide.md", pin, { sourceKind: "git_revision" }),
    "git_revision",
  );
  const pinFolder = local(`/tree/${PINNED}/docs`, pin, { sourceKind: "git_revision" });
  read("a pin's folder", pinFolder, "git_revision");
  // Read as a folder's inventory spells a path, a pin's address is its wire, never a name:
  // what the page's source kind is for.
  read("a pin's folder read as a folder's", pinFolder, "filesystem");
  const wire = page.sandbox.MetabrowserGitPath.wire("docs/guide.md");
  read("a rendered diff's head link", { kind: "view-head", href: `/view/${wire}#install` });
  read("a head link with an escaped anchor", {
    kind: "view-head",
    href: `/view/${wire}#%C3%BCber-uns`,
  });
  read("a head link whose anchor does not decode", {
    kind: "view-head",
    href: `/view/${wire}#%E0%A4%A`,
  });
  read("a head link whose name is not text", { kind: "view-head", href: "/view/g1-_w" });
  read("a head link that is not a file's", { kind: "view-head", href: "/pull/12" });
  read("a link to another site", { kind: "external", url: `${base}/issues/1` });
  read("a link whose user name names one site and whose host another", {
    kind: "external",
    url: "https://github.com@elsewhere.example/docs",
  });
  read("a mail link", { kind: "external", url: "mailto:someone@example.com" });
  read("a link with no scheme of its own", { kind: "external", url: "//example.com/docs" });
  read("an address that does not parse", { kind: "external", url: "https://" });
  read("a pull request numbered 0", pullRoute(0));
  read("a commit by a short ID", {
    kind: "route",
    href: "/commit/abc1234",
    localization: "commit",
    pull: null,
  });
  read("nothing", null);
  // The pin's own page, which `subject` reads when no source kind is given.
  const pinPage = createPage({ sourceKind: "git_revision" });
  rows.push({
    label: "the same file on the pin, as the page's source kind reads it",
    subject: pinPage.previews.subject(pinned),
  });
  return rows;
}

// ── The card ───────────────────────────────────────────────────────

/** Every line's text, folded as the card folds it. */
function foldedLines(html) {
  return lines(html)
    .split(" | ")
    .map((line) =>
      line
        .replace(/^\[[^\]]+\] /, "")
        .replace(/\s+/g, " ")
        .trim()
        .toLowerCase(),
    );
}

/** The card's own invariants, for any card this file draws. */
function checkCard(html, linkText, preview) {
  const folded = foldedLines(html);
  const link = String(linkText ?? "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
  assert(!folded.includes(link) || link === "", `a card repeats its link's text: ${html}`);
  assert(new Set(folded).size === folded.length, `a card says one thing twice: ${html}`);
  const last = folded.at(-1);
  const expected = preview?.missing?.toLowerCase() ?? null;
  assert(
    expected === null ? last.startsWith("opens ") : last === expected,
    `a card does not end with where it opens: ${html}`,
  );
  assert(
    STATE_MARK.test(html) === ["open", "closed", "merged", "draft"].includes(preview?.state),
    `a card claims a state its data does not give: ${html}`,
  );
  assert(!/<(?!\/?(div|span|svg)\b)/.test(html), `a card holds markup it did not write: ${html}`);
}

function cards(page) {
  const { previews } = page;
  const pull = previews.subject(pullRoute(12));
  const changes = previews.subject(pullRoute(12, "files", "docs/guide.md"));
  const checks = previews.subject(pullRoute(12, "checks"));
  const stack = Object.freeze({ kind: "stack", number: 3, file: "src/app.py" });
  const commit = Object.freeze({ kind: "commit", revision: COMMIT });
  /** A file's or folder's subject as the resolver's view target names it. */
  const view = (path, localization) =>
    previews.subject({ kind: "view", target: { path }, localization }, "filesystem");
  const file = view("docs/guide.md", "revision");
  const branchFile = view("docs/guide.md", "working-tree");
  const docs = view("docs/", "revision");
  const root = view("", "working-tree");
  const pulls = Object.freeze({ kind: "pulls" });
  const title = "fix(parser): keep a heading's trailing text";
  const rows = [
    ["a pull request, no data", pull, null, "#12"],
    ["a pull request, its title and state", pull, { title, state: "merged" }, "#12"],
    ["its Changes at a file", changes, { title, state: "open" }, "the guide"],
    ["its Checks", checks, null, "the checks"],
    ["a stack's changed file, no data", stack, null, "app.py"],
    ["a stack's changed file, its top's title", stack, { title: "Stack the parser" }, "app.py"],
    ["a commit, no data", commit, null, "this commit"],
    ["a commit, its subject and author", commit, { title, detail: "Ada · 3 days ago" }, "it"],
    ["a commit the repository lacks", commit, { missing: "Not in this repository" }, "it"],
    ["a file, no data", file, null, "the guide"],
    ["a file, its title", file, { title: "The Guide" }, "read this"],
    ["a file on the served branch", branchFile, null, "the guide"],
    ["a folder", docs, { detail: "12 files · 3.4 KB" }, "the docs"],
    ["the root, from a branch's link", root, null, "the repository"],
    ["the pull request list", pulls, null, "open pull requests"],
    [
      "a file on the served branch, on a pin",
      previews.subject(
        {
          kind: "view",
          target: { path: page.sandbox.MetabrowserGitPath.wire("docs/guide.md") },
          localization: "working-tree",
        },
        "git_revision",
      ),
      null,
      "the guide",
    ],
    ["a title with markup", pull, { title: `<img src=x onerror="go()"> & 'q'` }, "#12"],
    ["an answer that is not data", pull, "<b>bold</b>", "#12"],
  ].map(([name, subject, preview, linkText]) => {
    const html = previews.card(subject, preview, { linkText });
    checkCard(html, linkText, preview);
    return { label: name, linkText, preview, html };
  });
  // The root is named by the served folder's name, the last of the served prefix, or else
  // by the repository's, and is `/` only on a page with no repository identity.
  const { repository } = page.mb;
  for (const [name, context] of [
    ["the root of a served folder", { ...repository, served_prefix: "guides/notes" }],
    ["the root, on a page with no repository identity", null],
  ]) {
    page.mb.repository = context;
    const html = previews.card(root, null, { linkText: "the start" });
    checkCard(html, "the start", null);
    rows.push({ label: name, linkText: "the start", preview: null, html });
  }
  page.mb.repository = repository;
  // An author's title: in place of an object's, beside it, and never twice.
  for (const [name, preview, authorTitle] of [
    ["an author's title, no object title", null, "Read this first"],
    ["an author's title beside the object's", { title }, "Read this first"],
    ["an author's title that is the object's", { title }, title.toUpperCase()],
  ]) {
    const html = previews.card(pull, preview, { linkText: "#12", authorTitle });
    checkCard(html, "#12", preview);
    rows.push({ label: name, linkText: "#12", preview, authorTitle, text: lines(html) });
  }
  // An author's title is the author's, never the app's: set apart in quotation marks, and
  // never in place of what the link opens, even where the link's text is that identity and
  // the title says what the app would.
  for (const [name, subject, linkText, authorTitle] of [
    ["an author's title in the app's words", file, "docs/guide.md", "Not in the served files"],
    ["an author's title where the link's text is its identity", pull, "Pull request #12", "Go"],
  ]) {
    const html = previews.card(subject, null, { linkText, authorTitle });
    const said = lines(html).split(" | ");
    const named = said[0].replace(/^\[[^\]]+\] /, "");
    assert(
      named === (subject.kind === "pull" ? "Pull request #12" : subject.path),
      `an author's title took the place of the link's identity: ${html}`,
    );
    assert(
      said[1] === `\u201c${authorTitle}\u201d`,
      `an author's title was not set apart as the author's: ${html}`,
    );
    rows.push({ label: name, linkText, authorTitle, text: lines(html) });
  }
  // The link's own text is never said again, in any case and spacing.
  for (const [name, subject, preview, linkText] of [
    [
      "the link's text is the title",
      pull,
      { title },
      `  FIX(parser): keep a heading's\ntrailing text `,
    ],
    ["the link's text is the path", file, { title: "The Guide" }, "docs/guide.md"],
    ["the link's text is the identity", pull, { title, state: "draft" }, "Pull request #12"],
    ["the link's text is the subject", commit, { title }, title],
  ]) {
    const html = previews.card(subject, preview, { linkText });
    checkCard(html, linkText, preview);
    rows.push({ label: name, linkText, text: lines(html) });
  }
  // A page on another site: one line saying where it goes, and that it opens a new tab only
  // where the link does, and after it the author's title.
  const outside = previews.subject({ kind: "external", url: "https://example.com/elsewhere" });
  for (const [name, options] of [
    ["another site, in a new tab", { linkText: "elsewhere", newTab: true }],
    ["another site, in the same tab", { linkText: "elsewhere", newTab: false }],
    [
      "another site, with its author's title",
      { linkText: "elsewhere", newTab: true, authorTitle: "The other guide" },
    ],
    [
      "another site, whose link's text is its address",
      { linkText: "https://example.com/elsewhere", newTab: true },
    ],
  ]) {
    const html = previews.card(outside, null, options);
    const said = lines(html).split(" | ");
    assert(
      said[0] === `Opens example.com${options.newTab ? " in a new tab" : ""}`,
      `an outside link's card did not say first where it goes: ${html}`,
    );
    assert(!STATE_MARK.test(html) && !html.includes("link-card-mark"), `a mark: ${html}`);
    rows.push({ label: name, ...options, text: lines(html) });
  }
  const invalid = previews.card({ kind: "issue", number: 1 }, null, {});
  assert(invalid === "", "a card was drawn for something that is not a subject");
  rows.push({ label: "not a subject", html: invalid });
  return rows;
}

// ── Rests ──────────────────────────────────────────────────────────

/** A state is drawn only where a summary gives one, and with the github plugin's glyph. */
async function states() {
  const page = createPage();
  const { previews } = page;
  const pull = previews.subject(pullRoute(12));
  const before = previews.card(pull, { state: "open" }, { linkText: "#12" });
  assert(!STATE_MARK.test(before), "a state was drawn before its glyphs loaded");
  const { provider } = stub(page, (subject) =>
    subject.number === 12 ? { title: "Keep the tail", state: "merged" } : { title: "Untold" },
  );
  previews.provide("pull", provider);
  const { anchors } = page.text("description", ["twelve", "#12", pullRoute(12)]);
  await page.point(0, anchors.twelve);
  await page.look(600);
  const after = Object.fromEntries(
    [
      ["no data", null],
      ["a title alone", { title: "Untold" }],
      ["a draft", { state: "draft" }],
      ["a state the card does not know", { state: "reopened" }],
    ].map(([name, preview]) => {
      const html = previews.card(pull, preview, { linkText: "#12" });
      checkCard(html, "#12", preview);
      return [name, lines(html)];
    }),
  );
  assert(
    page.log.filter((entry) => entry.load).length === 1,
    "the state glyphs were not loaded once",
  );
  return { beforeTheGlyphsLoad: lines(before), rest: page.log, after };
}

/** The card's timing on the page's tooltip, with and without a provider. */
async function timing() {
  const sessions = {};
  {
    const page = createPage();
    const { anchors } = page.text("description", ["twelve", "#12", pullRoute(12)]);
    await page.point(0, anchors.twelve);
    await page.look(299);
    await page.look(320);
    await page.point(400, page.document);
    sessions["no provider: the card at the tooltip's own delay"] = page.log;
  }
  {
    const page = createPage();
    page.previews.provide("pull", stub(page, { title: "Keep the tail" }).provider);
    const { anchors } = page.text("description", ["twelve", "#12", pullRoute(12)]);
    await page.point(0, anchors.twelve);
    await page.look(320);
    await page.look(570);
    await page.point(700, page.document);
    sessions["an answer during the delay: the card shows it on time"] = page.log;
  }
  {
    const page = createPage();
    const late = stub(page, { title: "Keep the tail" }, { summary: 100, prefetch: 100 });
    page.previews.provide("pull", late.provider);
    const { anchors } = page.text("description", ["twelve", "#12", pullRoute(12)]);
    await page.point(0, anchors.twelve);
    await page.look(320);
    await page.look(400);
    await page.point(450, page.document);
    await page.point(600, anchors.twelve);
    await page.look(920);
    await page.point(1000, page.document);
    const reads = page.log.filter((entry) => entry.summary && !entry.kept).length;
    assert(reads === 1, "a kept answer was read again");
    sessions["a late answer: kept for the next rest"] = page.log;
  }
  {
    const page = createPage();
    const crossed = stub(page, { title: "Keep the tail" });
    page.previews.provide("pull", crossed.provider);
    const { anchors } = page.text("description", ["twelve", "#12", pullRoute(12)]);
    await page.point(0, anchors.twelve);
    await page.point(100, page.document);
    await page.look(500);
    assert(!page.log.some((entry) => entry.summary || entry.prefetch), "a pass read a link");
    sessions["a pass across the link: nothing is read"] = page.log;
  }
  {
    const page = createPage();
    page.previews.provide("pull", stub(page, { title: "Keep the tail" }).provider);
    const { anchors } = page.text("description", ["twelve", "#12", pullRoute(12)]);
    const words = anchors.twelve.childNodes[0];
    await page.point(0, anchors.twelve);
    await page.point(100, words);
    await page.point(200, anchors.twelve);
    await page.look(570);
    const shows = page.log.filter((entry) => "show" in entry).length;
    assert(shows === 2, "moving within a link asked for its card again");
    sessions["moving within the link: nothing changes"] = page.log;
  }
  return sessions;
}

/** One read and one prefetch in flight, a newer rest waiting for them, none aborted. */
async function requests() {
  const page = createPage();
  const readMs = 400;
  const slow = stub(page, (subject) => ({ title: `Title ${subject.number}` }), {
    summary: readMs,
    prefetch: readMs,
  });
  page.previews.provide("pull", slow.provider);
  const { anchors } = page.text(
    "description",
    ["one", "#1", pullRoute(1)],
    ["two", "#2", pullRoute(2)],
    ["three", "#3", pullRoute(3)],
  );
  await page.point(0, anchors.one);
  await page.point(300, anchors.two);
  await page.look(980);
  await page.point(1000, anchors.three);
  await page.point(1100, page.document);
  await page.look(2000);
  const { counts } = slow;
  assert(counts.maxReads === 1 && counts.maxPrefetches === 1, "two requests were in flight");
  assert(counts.signals === 0, "a read was given something that could abort it");
  assert(!page.log.some((entry) => entry.summary === "pull 3"), "a pass read a link");
  // The second rest's intent delay ended at 550, during the first read, which it waited for.
  assert(
    page.log.find((entry) => entry.summary === "pull 2")?.at === page.previews.INTENT_MS + readMs,
    "a newer rest did not wait for the read in flight",
  );
  return { readMs, log: page.log, counts };
}

/**
 * An image the page did not load, inside a link with a card: its chip's own tooltip comes
 * off as the link is registered, so one tooltip shows, and the card says its address; a link
 * that loses its card gives the chip its tooltip back.
 */
function images() {
  const page = createPage();
  const { previews } = page;
  const root = new FakeElement("div", "description");
  page.document.append(root);
  const rows = {};
  for (const [name, target] of [
    ["in a link that opens here", pullRoute(12)],
    ["in a link to another site", { kind: "external", url: "https://example.com/build" }],
  ]) {
    const anchor = new FakeElement("a", name);
    const chip = new FakeElement("span", "chip");
    chip.setAttribute("class", "mb-image-fallback");
    chip.setAttribute("data-tip-text", "https://img.example/badge.svg");
    chip.append("build passing");
    anchor.append("the badge: ", chip);
    root.append(anchor);
    previews.register(root, anchor, target, page.mb);
    const taken = chip.getAttribute("data-tip-text");
    // A later pass over the same link, as the resolver makes, keeps what the first took.
    previews.register(root, anchor, target, page.mb);
    const html = previews.card(previews.subject(target), null, {
      linkText: anchor.textContent,
      images: ["https://img.example/badge.svg"],
    });
    previews.forget(anchor);
    rows[name] = {
      "the chip's tooltip once registered": taken,
      card: lines(html),
      "the chip's tooltip once forgotten": chip.getAttribute("data-tip-text"),
    };
    assert(taken === null, "a chip inside a link with a card kept its own tooltip");
    assert(
      lines(html).includes("Image from https://img.example/badge.svg"),
      `the card did not say the image's address: ${html}`,
    );
    assert(
      chip.getAttribute("data-tip-text") === "https://img.example/badge.svg",
      "a forgotten link's chip did not get its tooltip back",
    );
  }
  return rows;
}

/** A link to another site: its card on the tooltip's own delay, and nothing read. */
async function outside() {
  const page = createPage();
  const { anchors } = page.text("comment", [
    "elsewhere",
    "the other guide",
    { kind: "external", url: "https://example.com/elsewhere" },
  ]);
  anchors.elsewhere.setAttribute("target", "_blank");
  await page.point(0, anchors.elsewhere);
  await page.look(299);
  await page.look(320);
  await page.point(700, page.document);
  assert(
    page.log.at(-2).tooltip === "Opens example.com in a new tab",
    "an outside link's card did not come up saying where it goes",
  );
  assert(
    !page.log.some((entry) => entry.summary || entry.prefetch),
    "a rest on an outside link asked something of a provider",
  );
  return page.log;
}

/** Focus and touch show nothing; the pointer does. */
async function modality() {
  const page = createPage();
  page.previews.provide("pull", stub(page, { title: "Keep the tail" }).provider);
  const { anchors } = page.text("description", ["twelve", "#12", pullRoute(12)]);
  dispatch(anchors.twelve, "focusin");
  dispatch(anchors.twelve, "focus");
  dispatch(anchors.twelve, "keydown");
  await page.point(0, anchors.twelve, { pointerType: "touch" });
  await page.look(600);
  assert(!page.log.some((entry) => "show" in entry), "focus or touch asked for a card");
  const quiet = [...page.log];
  await page.point(700, page.document);
  await page.point(800, anchors.twelve, { pointerType: "pen" });
  await page.look(1400);
  assert(
    page.log.some((entry) => "show" in entry),
    "a pen's rest asked for no card",
  );
  const sessions = {
    "focus, keys, and a touch": quiet,
    "then a pen": page.log.slice(quiet.length),
  };
  // Focus moving onto the link during a rest, by a Tab or by a click, before the card's read
  // has answered: its tooltip goes, and neither the read's answer nor the state glyphs it
  // loads bring the card back, though the pointer is still on the link and moves within it.
  for (const what of ["focus", "press"]) {
    const rested = createPage();
    rested.previews.provide(
      "pull",
      stub(rested, { title: "Keep the tail", state: "merged" }, { summary: 40, prefetch: 1 })
        .provider,
    );
    const link = rested.text("description", ["twelve", "#12", pullRoute(12)]).anchors.twelve;
    await rested.point(0, link);
    await rested.act(260, link, what);
    await rested.look(280);
    await rested.point(400, link.childNodes[0]);
    await rested.look(1000);
    const after = rested.log.slice(rested.log.findIndex((entry) => entry[what]));
    assert(
      !after.some((entry) => "show" in entry || entry.tooltip),
      `a card came back after ${what === "focus" ? "focus" : "a press"} moved onto its link`,
    );
    sessions[what === "focus" ? "focus during the read" : "a press during the read"] = rested.log;
  }
  return sessions;
}

/** A provider that fails still leaves the card with what the link opens. */
async function failures() {
  const sessions = {};
  for (const [name, summary] of [
    [
      "a provider that throws",
      () => {
        throw new Error("no record");
      },
    ],
    ["a provider that rejects", () => Promise.reject(new Error("offline"))],
    ["a provider that answers null", () => null],
    // The registry keeps no answer, so a provider that knew nothing at the first rest, as a
    // catalog still filling does, is asked again, and the next rest says what it knows then.
    [
      "a provider that answers null, then a subject",
      (_subject, _how, asked) => (asked === 1 ? null : { title: "Found at the second rest" }),
    ],
  ]) {
    const page = createPage();
    let asked = 0;
    page.previews.provide("commit", {
      summary: (subject, how) => {
        asked += 1;
        return summary(subject, how, asked);
      },
    });
    const commit = { kind: "route", href: `/commit/${COMMIT}`, localization: "commit", pull: null };
    const { anchors } = page.text("message", ["commit", "this commit", commit]);
    await page.point(0, anchors.commit);
    await page.look(600);
    await page.point(700, page.document);
    // Back once the first card's fade has ended, so the second is a card of its own.
    await page.point(900, anchors.commit);
    await page.look(1500);
    const cardsShown = page.log.filter((entry) => entry.tooltip).map((entry) => entry.tooltip);
    assert(
      cardsShown.length === 2 &&
        cardsShown.every((card) => card.endsWith("Opens here in Metabrowser")),
      `${name}: the card was lost`,
    );
    assert(asked === 2, `${name}: the second rest did not ask its provider again`);
    sessions[name] = { asked, cards: cardsShown, warnings: page.warnings };
  }
  return sessions;
}

/** Each surface puts away its own card: `dispose`, `forget`, and a later `register`. */
async function disposal() {
  const page = createPage();
  const { previews } = page;
  const readme = page.text("readme", [
    "guide",
    "the guide",
    { kind: "view", target: { path: "docs/guide.md" }, localization: "revision" },
  ]);
  const comment = page.text("comment", ["twelve", "#12", pullRoute(12)]);
  await page.point(0, readme.anchors.guide);
  await page.look(320);
  previews.dispose(comment.root);
  await page.look(340);
  assert(page.log.at(-1).tooltip !== null, "another root's dispose took the card");
  previews.dispose(readme.root);
  await page.look(600);
  assert(page.log.at(-1).tooltip === null, "a root's dispose left its card");
  await page.point(700, page.document);
  await page.point(800, readme.anchors.guide);
  await page.look(1200);
  assert(!page.log.slice(-3).some((entry) => "show" in entry), "a disposed root showed a card");
  const disposed = [...page.log];

  const again = page.text("again", ["twelve", "#12", pullRoute(12)]);
  await page.point(1300, again.anchors.twelve);
  await page.look(1620);
  previews.register(again.root, again.anchors.twelve, pullRoute(12, "checks"), page.mb);
  await page.look(1640);
  previews.forget(again.anchors.twelve);
  await page.look(1900);
  assert(page.log.at(-1).tooltip === null, "a forgotten link kept its card");
  return { dispose: disposed, "register again, then forget": page.log.slice(disposed.length) };
}

async function main() {
  const glyphsPage = createPage();
  // The github plugin's glyphs, loaded as a state's first summary loads them.
  glyphsPage.previews.provide("pull", stub(glyphsPage, { state: "open" }).provider);
  const { anchors } = glyphsPage.text("warm", ["twelve", "#12", pullRoute(12)]);
  await glyphsPage.point(0, anchors.twelve);
  await glyphsPage.look(600);
  const transcript = {
    // The module's own intent delay, and its words for where a link opens, by `opens`.
    intentMs: glyphsPage.previews.INTENT_MS,
    opens: glyphsPage.previews.OPENS,
    subjects: subjects(),
    cards: cards(glyphsPage),
    states: await states(),
    timing: await timing(),
    requests: await requests(),
    outside: await outside(),
    images: images(),
    modality: await modality(),
    failures: await failures(),
    disposal: await disposal(),
  };
  process.stdout.write(`${JSON.stringify(transcript, null, 1)}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
