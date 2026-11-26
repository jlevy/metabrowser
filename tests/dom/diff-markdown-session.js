// Browserless session: a pull request's rendered Markdown views, driven through the
// production browser code.
//
// builtin_plugins/diff/diff-markdown.js and static/inert-html.js load whole. The answers
// are the server's projections, recorded in tests/fixtures/diff-markdown-responses.json by
// tests/test_diff_markdown_session.py, which fails when the server answers differently;
// so is Python's HTML parse of every block, from which this builds the template a page
// parses a block into, so the page's own sanitizer runs on what the server sends. The
// shared chip family, the stylesheet loader and the diff's layout are stand-ins, the page
// is a small element tree that records what the production code builds, and time is a
// clock this advances by hand, so the loading delay and a refused request's wait are
// steps of the story rather than races.
//
// Which addresses a block keeps is the plugin's rule, not this session's:
// builtin_plugins/diff/index.js loads whole, as the shell loads it, and mounts a pull
// request's comparison on pages the shell rendered (pinned at the head, pinned at the
// merge base, and beside a checkout, which has no pin), handing the diff, here the stand-in
// for diff-view.js, the `markdownTargets` this session draws with. The pin guard's
// `metabrowser:pin-changed` is played on the window as static/source-pin-guard.js sends it.
// The comparison mounted is the conformance corpus's added Markdown file, which the plugin
// validates; only the routes the session's own recording names decide anything here.
//
// Each step prints the requests the page made, each a file and what it asked of the
// route, and for each file whose state the step changed: its chooser (`*` marks the chosen
// format, and a rendered view that cannot be chosen says `unavailable` and why, as its
// tooltip and its accessible name do), what its body shows (`rendered`, `source`, or
// `nothing` while it waits for its rendered view), whether its progress mark is
// counting down to visible, and the rendered rows: each block's kind and text, a fold's bar
// as `[N unchanged blocks]`, open with its rows under it or closed, and the place a chunk
// not drawn yet keeps as `[blocks I-J not drawn: N px]`. A long file's rows are shortened
// to their first and last few.

const fs = require("node:fs");
const { registerHooks } = require("node:module");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

// The diff's layout is a stand-in: the plugin mounts it with the options it records.
registerHooks({
  load(url, context, nextLoad) {
    if (url.endsWith("/builtin_plugins/diff/diff-view.js")) {
      return {
        format: "module",
        shortCircuit: true,
        source:
          "export const setChangeLoader = () => {}; export const setGapLoader = () => {}; export const mountDiffView = (_host, _document, _api, options) => ({ options, dispose() {} }); export const mountDiffSummary = () => ({ dispose() {} }); export const fileDisclosure = () => {}; export const presentationControlHtml = () => ''; export const mountFilePatch = () => ({ dispose() {} });",
      };
    }
    return nextLoad(url, context);
  },
});

const repoRoot = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/diff-markdown-responses.json"), "utf8"),
);
const ORIGIN = "http://127.0.0.1:8123";

// The part of the transcript to print, which the golden prints a block at a time:
// tryscript matches a block through one regular expression, which V8 refuses past about
// 32,700 characters, and the whole transcript passed that on 2026-11-24. With no part
// named it prints the links and the steps before the long document's, `long` the rest,
// and `all` the whole, which tests/test_diff_markdown_session.py reads. The session runs
// every step whichever it prints.
const PART = process.argv[2] ?? "mount";
const LONG_FIRST_STEP =
  "Rendered Diff folds a short run with its blocks and withholds the long runs' blocks";
/** @param {string | null} part @param {unknown} links @param {{step: string}[]} all */
function printed(part, links, all) {
  const split = all.findIndex((each) => each.step === LONG_FIRST_STEP);
  assert(split > 0, "the long document's steps are found");
  assert(["mount", "long", "all"].includes(part), `no part of the transcript is ${part}`);
  return part === "mount"
    ? { links, steps: all.slice(0, split) }
    : part === "long"
      ? { steps: all.slice(split) }
      : { links, steps: all };
}

let finished = false;
process.on("exit", (code) => {
  if (!finished && code === 0) {
    process.stderr.write("Markdown session: ended before its last step\n");
    process.exitCode = 1;
  }
});

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

// ── The page: elements that record what the production code builds ─────────

class ClassList {
  constructor(owner) {
    this.owner = owner;
  }

  get names() {
    return this.owner.className.split(" ").filter(Boolean);
  }

  add(...names) {
    this.owner.className = [...new Set([...this.names, ...names])].join(" ");
  }

  remove(name) {
    this.owner.className = this.names.filter((each) => each !== name).join(" ");
  }

  toggle(name, force) {
    const on = force ?? !this.names.includes(name);
    if (on) {
      this.add(name);
    } else {
      this.remove(name);
    }
    return on;
  }

  contains(name) {
    return this.names.includes(name);
  }
}

class PageElement {
  constructor(tag) {
    this.nodeType = tag === "#text" ? 3 : 1;
    this.tagName = tag.toUpperCase();
    this.className = "";
    this.classList = new ClassList(this);
    this.childNodes = [];
    this.parentElement = null;
    this.attributes = new Map();
    this.listeners = new Map();
    this.dataset = {};
    this.style = {};
    this.hidden = false;
    this.open = false;
    this.text = "";
    this.id = "";
  }

  get children() {
    return this.childNodes.filter((node) => node.nodeType === 1);
  }

  get textContent() {
    return this.nodeType === 3
      ? this.text
      : this.childNodes.map((node) => node.textContent).join("");
  }

  set textContent(value) {
    if (this.nodeType === 3) {
      this.text = String(value);
      return;
    }
    this.childNodes = [];
    if (value) {
      this.append(text(String(value)));
    }
  }

  get firstElementChild() {
    return this.children[0];
  }

  get previousElementSibling() {
    const siblings = this.parentElement?.children ?? [];
    return siblings[siblings.indexOf(this) - 1] ?? null;
  }

  get nextElementSibling() {
    const siblings = this.parentElement?.children ?? [];
    return siblings[siblings.indexOf(this) + 1] ?? null;
  }

  remove() {
    if (this.parentElement !== null) {
      const siblings = this.parentElement.childNodes;
      siblings.splice(siblings.indexOf(this), 1);
      this.parentElement = null;
    }
  }

  append(...nodes) {
    for (const node of nodes) {
      if (node.tagName === "#FRAGMENT") {
        this.append(...node.childNodes);
        continue;
      }
      node.parentElement = this;
      this.childNodes.push(node);
    }
  }

  prepend(...nodes) {
    for (const node of nodes) {
      node.parentElement = this;
    }
    this.childNodes.unshift(...nodes);
  }

  replaceChildren(...nodes) {
    this.childNodes = [];
    this.append(...nodes);
  }

  #insert(offset, nodes) {
    const siblings = this.parentElement.childNodes;
    const at = siblings.indexOf(this) + offset;
    for (const node of nodes) {
      node.parentElement = this.parentElement;
    }
    siblings.splice(at, 0, ...nodes);
  }

  after(...nodes) {
    this.#insert(1, nodes);
  }

  replaceWith(...nodes) {
    const parent = this.parentElement;
    const siblings = parent.childNodes;
    const at = siblings.indexOf(this);
    const placed = nodes.flatMap((node) =>
      node.tagName === "#FRAGMENT" ? node.childNodes : [node],
    );
    for (const node of placed) {
      node.parentElement = parent;
    }
    siblings.splice(at, 1, ...placed);
    this.parentElement = null;
  }

  closest(selector) {
    assert(selector === "a[href]", `the session finds only links, not ${selector}`);
    for (let node = this; node !== null; node = node.parentElement) {
      if (node.tagName === "A" && node.getAttribute("href") !== null) {
        return node;
      }
    }
    return null;
  }

  scrollIntoView(options) {
    scrolled.push({ id: this.getAttribute("id"), ...options });
  }

  before(...nodes) {
    this.#insert(0, nodes);
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  addEventListener(name, listener) {
    this.listeners.set(name, listener);
  }

  contains(node) {
    return this === node || this.childNodes.some((child) => child.contains?.(node));
  }

  focus() {
    page.activeElement = this;
  }

  // The chip family's markup, as the shared stand-in below spells it.
  set innerHTML(spec) {
    if (typeof spec !== "object") {
      throw new Error("only a chooser is written as markup here");
    }
    this.childNodes = [];
    for (const option of spec.options) {
      const chip = element("button");
      chip.dataset.chipValue = option.value;
      if (option.tip !== undefined) {
        chip.dataset.tipText = option.tip;
      }
      chip.textContent = option.label;
      chip.setAttribute("aria-checked", String(spec.value === option.value));
      this.append(chip);
    }
  }

  querySelectorAll(selector) {
    const found = [];
    const walk = (parent) => {
      for (const child of parent.children) {
        const tag = child.tagName;
        const wanted =
          selector === "button[data-chip-value]"
            ? tag === "BUTTON" && child.dataset.chipValue !== undefined
            : selector === "a[href], img[src]"
              ? (tag === "A" && child.getAttribute("href") !== null) ||
                (tag === "IMG" && child.getAttribute("src") !== null)
              : selector === 'a[href^="/view/"]'
                ? tag === "A" && (child.getAttribute("href") ?? "").startsWith("/view/")
                : tag === selector.toUpperCase();
        if (wanted) {
          found.push(child);
        }
        walk(child);
      }
    };
    walk(this);
    return found;
  }
}

const element = (tag) => new PageElement(tag);
const text = (value) => {
  const node = new PageElement("#text");
  node.text = value;
  return node;
};

// The template a page parses a block into, built from the recorded parse of that block.
function parsed(nodes) {
  return nodes.map((node) => {
    if (typeof node === "string") {
      const built = text(node);
      built.nodeValue = node;
      return built;
    }
    const built = element(node.tag);
    for (const [name, value] of node.attrs) {
      built.setAttribute(name, value);
    }
    built.append(...parsed(node.children));
    return built;
  });
}

function template() {
  const made = element("template");
  Object.defineProperty(made, "innerHTML", {
    set(html) {
      assert(html in recorded.trees, `no recorded parse for ${html}`);
      const content = element("#fragment");
      content.append(...parsed(recorded.trees[html]));
      made.content = content;
    },
  });
  return made;
}

const page = {
  activeElement: null,
  createElement: (tag) => (tag === "template" ? template() : element(tag)),
  createTextNode: (value) => text(String(value)),
  createDocumentFragment: () => element("#fragment"),
  implementation: {
    createHTMLDocument: () => ({
      createElement: (tag) => element(tag),
      createTextNode: (value) => text(String(value)),
    }),
  },
};
globalThis.document = page;

// What the page's window holds for the plugin: the SDK functions it calls here, the block
// the shell writes for a pin (`METABROWSER_SOURCE_PIN`), and its listeners.
const windowListeners = new Map();
/** The plugin's registered view, once index.js has loaded. */
let plugin = null;
/** The served repository's identity, as a page of the fixture's mirror or checkout has it. */
function repositoryAt(revision) {
  return {
    branch: null,
    host: "github.com",
    name: "demo",
    owner: "octo",
    revision,
    served_prefix: "",
  };
}
/** What the page knows of its source: a pin's page is a Git revision, a checkout's a folder. */
const pageSource = { kind: "git_revision", repository: null };
globalThis.window = {
  location: { origin: ORIGIN },
  addEventListener(type, handler) {
    windowListeners.set(type, [...(windowListeners.get(type) ?? []), handler]);
  },
  removeEventListener(type, handler) {
    windowListeners.set(
      type,
      (windowListeners.get(type) ?? []).filter((candidate) => candidate !== handler),
    );
  },
  metabrowser: {
    registerView(kind, view, spec) {
      assert(kind === "diff" && view === "diff", "the plugin registers its one view");
      plugin = spec;
    },
    loadChangedFilesTree: async () => null,
    sourceKind: () => pageSource.kind,
    get repository() {
      return pageSource.repository;
    },
    // As static/plugin-sdk-views.js answers it: the links on a repository's page.
    loadRepositoryLinks: async () =>
      pageSource.repository ? globalThis.window.MetabrowserRepositoryLinks : null,
  },
};

// What the page has loaded when a rendered file arrives on a repository's page (diff-view.js
// `ensureInert`): what a link into the repository opens, and the GitPath codec that reads a
// link to a file of the head back.
for (const name of ["git-path.js", "repository-links.js"]) {
  const file = path.join(repoRoot, "src/metabrowser/static", name);
  require("node:vm").runInThisContext(fs.readFileSync(file, "utf8"), { filename: file });
}

/** What the pin guard announces when a data request finds the server serves another pin. */
function pinChanged(served) {
  for (const handler of windowListeners.get("metabrowser:pin-changed") ?? []) {
    handler({ detail: { pin: served } });
  }
}

// The page's observers, in the order it makes them: the files' lookahead, then the chunks'.
const observers = [];
globalThis.IntersectionObserver = class {
  constructor(notify, options) {
    observers.push(this);
    this.notify = notify;
    this.options = options;
    this.observed = [];
  }

  observe(target) {
    this.observed.push(target);
  }

  unobserve(target) {
    this.observed = this.observed.filter((each) => each !== target);
  }

  disconnect() {
    this.observed = [];
  }
};
/** What the page scrolled into view, in order. */
const scrolled = [];

// ── The clock and the server ────────────────────────────────────────────────

const clock = {
  time: 0,
  timers: new Map(),
  next: 1,
  now: () => clock.time,
  later(callback, ms) {
    const handle = clock.next++;
    clock.timers.set(handle, { at: clock.time + ms, callback });
    return handle;
  },
  cancel(handle) {
    clock.timers.delete(handle);
  },
  advance(ms) {
    clock.time += ms;
    for (const [handle, timer] of [...clock.timers].sort((a, b) => a[1].at - b[1].at)) {
      if (timer.at <= clock.time && clock.timers.has(handle)) {
        clock.timers.delete(handle);
        timer.callback();
      }
    }
  },
};

/** Requests the page made since the last step, and the ones still waiting for an answer. */
let requests = [];
const waiting = [];

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/** A request as a step prints it: the file, and what it asks of the route. */
function asked(fileId, ask) {
  const query = new URLSearchParams(ask ?? {}).toString();
  return query === "" ? fileId : `${fileId} ${query}`;
}

function answer(key, how = "recorded") {
  const index = waiting.findIndex((request) => request.key === key);
  assert(index >= 0, `no request waits for ${key}`);
  const [request] = waiting.splice(index, 1);
  if (how === "recorded") {
    // A refusal answers every view alike; a ready file answers each as the route does.
    const kept = recorded.answers[request.fileId];
    const query = request.key.slice(request.fileId.length + 1);
    const found = kept.status !== undefined ? kept : kept[query];
    assert(found !== undefined, `the recording has no answer for ${key}`);
    request.resolve(structuredClone(found));
  } else if (how === "busy") {
    request.reject(Object.assign(new Error("rendered_diff_busy"), { status: 429 }));
  } else {
    request.reject(new TypeError("Failed to fetch"));
  }
}

// ── What a step prints ──────────────────────────────────────────────────────

function rows(article, depth = "") {
  const shown = [];
  for (const node of article.childNodes) {
    if (node.classList.contains("fold-expander")) {
      // The diff's fold bar (diff-fold.js), which names the group it opens.
      assert(
        node.getAttribute("aria-controls") ===
          node.parentElement.childNodes[node.parentElement.childNodes.indexOf(node) + 1].id,
        "a fold's bar controls the group after it",
      );
      const open = node.getAttribute("aria-expanded") === "true";
      const busy = node.getAttribute("aria-busy") === "true" ? ", loading" : "";
      shown.push(`${depth}[${node.textContent}${open ? ", open" : ""}${busy}]`);
    } else if (node.classList.contains("diff-fold-group")) {
      // A closed fold holds no rows, and an open one shows its rows once it has them.
      const control =
        node.parentElement.childNodes[node.parentElement.childNodes.indexOf(node) - 1];
      const waiting = control.getAttribute("aria-busy") === "true";
      assert(
        node.classList.contains("diff-fold-collapsed")
          ? node.childNodes.length === 0
          : (node.childNodes.length === 0) === waiting,
        "a closed fold holds no rows, and an open one shows its rows",
      );
      shown.push(...rows(node, `${depth}  `));
    } else if (node.classList.contains("diff-markdown-spacer")) {
      shown.push(`${depth}[blocks ${node.dataset.span} not drawn: ${node.style.height}]`);
    } else if (node.classList.contains("diff-markdown-change")) {
      for (const row of changeRows(node)) {
        shown.push(...rowLines(row, depth));
      }
    } else {
      assert(
        !node.classList.contains("diff-markdown-added") &&
          !node.classList.contains("diff-markdown-removed"),
        "a changed row is drawn only in a run of its kind (changeRuns)",
      );
      shown.push(...rowLines(node, depth));
    }
  }
  return shown;
}

/** A row as a step prints it: front matter's disclosure, or a block's kind and content. */
function rowLines(row, depth) {
  return row.className.includes("diff-markdown-frontmatter")
    ? frontmatter(row)
    : [`${depth}${row_(row)}`];
}

// A change's band is drawn only by its runs (`changeRuns` in diff-markdown.js), each one box
// across its rows, so the band of a run of one kind can have no gap in it: a run holds rows
// of its own kind, two runs side by side in a change are of two kinds, and two changes are
// never side by side, which would put a run's end beside the next run of its kind. The
// rows, in order.
function changeRows(change) {
  const siblings = change.parentElement.childNodes;
  const before = siblings[siblings.indexOf(change) - 1];
  assert(
    before === undefined || !before.classList.contains("diff-markdown-change"),
    "two changes side by side are one",
  );
  const rows = [];
  let previous = null;
  for (const run of change.childNodes) {
    const kind = ["added", "removed"].find(
      (each) => run.className === `diff-markdown-run diff-markdown-run-${each}`,
    );
    assert(kind !== undefined, `a change holds only runs, not ${run.className}`);
    assert(kind !== previous, `two ${kind} runs side by side in a change are one`);
    previous = kind;
    assert(run.childNodes.length > 0, "a run holds a row");
    for (const row of run.childNodes) {
      assert(
        row.classList.contains("diff-markdown-block") &&
          row.classList.contains(`diff-markdown-${kind}`),
        `a ${kind} run holds only ${kind} rows`,
      );
      rows.push(row);
    }
  }
  return rows;
}

// The production `markJoins`, which `main` loads with the module.
let markJoins = null;

// Each row's joins (`markJoins` in diff-markdown.js) are the ones the rows shown around it
// make now, whatever was drawn, hidden, or opened since: marking the article again whole, and
// each open fold, changes none of them. A step that draws or hides rows without marking the
// rows it moved fails here.
function joinsAreFresh(file, container = file.rendered) {
  const all = [];
  const collect = (node) => {
    for (const child of node.children) {
      if (child.hidden) {
        continue;
      }
      if (child.classList.contains("diff-markdown-block")) {
        assert(child.dataset.join !== undefined, "a row shown is marked (markJoins)");
        all.push(child);
      } else {
        collect(child);
      }
    }
  };
  collect(container);
  const marks = () => all.map((row) => row.dataset.join);
  const before = JSON.stringify(marks());
  markJoins(container.children);
  for (const group of container.children) {
    if (group.classList.contains("diff-fold-group")) {
      markJoins(group.children);
    }
  }
  assert(JSON.stringify(marks()) === before, `${file.name}: a row's joins are stale`);
}

/** A long file's rows, shortened to their first and last few. */
function shortened(all) {
  return all.length <= 48
    ? all
    : [...all.slice(0, 4), `... ${all.length - 8} rows ...`, ...all.slice(-4)];
}

// Front matter is the Document view's Frontmatter disclosure: its summary, whether it is
// open, whether it was added or removed whole, and each key with its value and, when it
// changed, its change.
function frontmatter(row) {
  const [details] = row.childNodes.filter((node) => node.className !== "sr-only");
  assert(details.tagName === "DETAILS" && details.className === "kpress-frontmatter");
  const whole = ["added", "removed"].find((change) =>
    row.classList.contains(`diff-markdown-${change}`),
  );
  const [summary, list] = details.childNodes;
  const shown = [
    `[${summary.textContent}${details.open ? ", open" : ""}${whole ? `, ${whole}` : ""}]`,
  ];
  for (let index = 0; index < list.childNodes.length; index += 2) {
    const [term, value] = list.childNodes.slice(index, index + 2);
    const change = term.className.replace("diff-frontmatter-", "");
    const key = term.childNodes.filter((node) => node.className !== "sr-only")[0].textContent;
    shown.push(`  ${change || whole || "context"}: ${key} = ${value.textContent}`);
  }
  return shown;
}

// The Rendered body holds blocks and folds and nothing that talks about them: a row is its
// screen-reader label and its content, and no note says that Source shows more.
function row_(row) {
  assert(
    row.className.startsWith("diff-markdown-block diff-markdown-"),
    `a Rendered body holds only blocks and folds, not ${row.tagName} ${row.className}`,
  );
  const kind = row.className.replace("diff-markdown-block diff-markdown-", "").split(" ")[0];
  const parts = row.childNodes.filter((node) => node.className !== "sr-only");
  assert(
    parts.length === 1 && parts[0].className === "kpress-prose",
    `a ${kind} row draws a note beside its content`,
  );
  return `${kind}: ${serialize(parts[0].childNodes)}`;
}

function serialize(nodes) {
  return nodes
    .map((node) => {
      if (node.nodeType === 3) {
        return node.textContent.replace(/\s+/g, " ");
      }
      const tag = node.tagName.toLowerCase();
      const attributes = [...node.attributes]
        .map(([name, value]) => ` ${name}="${value}"`)
        .join("");
      return ["img", "br", "hr"].includes(tag)
        ? `<${tag}${attributes}>`
        : `<${tag}${attributes}>${serialize(node.childNodes)}</${tag}>`;
    })
    .join("");
}

function describe(file) {
  const views = ["Rendered"];
  const chips = file.control.children.map((chip) => {
    const chosen = chip.getAttribute("aria-checked") === "true" ? "*" : "";
    // A chip is never `disabled`, which would take the pointer and focus from it: one that
    // cannot be chosen is `aria-disabled`, and says why as its tooltip and in its name.
    assert(!chip.disabled, `${file.name}: a chip is disabled, so it cannot say why`);
    const why = chip.dataset.tipText;
    if (chip.getAttribute("aria-disabled") !== "true") {
      assert(why === undefined, `${file.name}: a chip that can be chosen explains itself`);
      return `${chosen}${chip.textContent}`;
    }
    assert(
      views.includes(chip.textContent) && chosen === "",
      `${file.name}: only a rendered view goes`,
    );
    assert(typeof why === "string" && why !== "", `${file.name}: nothing says why`);
    assert(
      chip.getAttribute("aria-label") === `${chip.textContent}, unavailable. ${why}`,
      `${file.name}: the chip's name does not say what its tooltip says`,
    );
    return `${chip.textContent} (unavailable: ${why})`;
  });
  const shows = !file.rendered.hidden ? "rendered" : !file.source.hidden ? "source" : "nothing";
  // Every file of a rendered format keeps its chooser, its progress mark's place, and the
  // bar layout that makes room for them, whatever the server answered.
  assert(
    chips.length === views.length + 1 &&
      !file.control.hidden &&
      !file.progress.hidden &&
      file.bar.classList.contains("diff-file-bar-markdown"),
    `${file.name}: the chooser is gone`,
  );
  assert(file.section.childNodes.length === 4, `${file.name}: unexpected file content`);
  // A file whose body shows nothing yet says so on its section, which keeps what follows it
  // in the diff out of sight (styles.css), so its body arriving moves nothing a reader sees.
  assert(
    file.section.classList.contains(waitingClass) === (shows === "nothing"),
    `${file.name}: a file waits exactly while its body shows nothing`,
  );
  if (file.rendered.childNodes.length > 0) {
    joinsAreFresh(file);
  }
  return {
    chooser: chips.join(" | "),
    shows,
    ...(file.progress.classList.contains("mb-delayed-loading") ? { progress: "counting" } : {}),
    ...(file.rendered.childNodes.length > 0 ? { rows: shortened(rows(file.rendered)) } : {}),
  };
}

/** The class a waiting file's section has (`WAITING_CLASS` in diff-markdown.js). */
let waitingClass;
const steps = [];
/** What each file showed when last printed: a step prints only the files it changed. */
const shown = new Map();
function step(name, files) {
  const changed = [];
  for (const file of files) {
    const now = describe(file);
    const text = JSON.stringify(now);
    if (shown.get(file.name) !== text) {
      shown.set(file.name, text);
      changed.push([file.name, now]);
    }
  }
  steps.push({ step: name, requests, files: Object.fromEntries(changed) });
  requests = [];
}

// ── The story ───────────────────────────────────────────────────────────────

async function main() {
  const inertPath = path.join(repoRoot, "src/metabrowser/static/inert-html.js");
  const context = { window: {}, URL };
  vm.runInNewContext(fs.readFileSync(inertPath, "utf8"), context, { filename: inertPath });
  const inert = context.window.MetabrowserInertHtml;
  const markdown = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-markdown.js")).href
  );
  waitingClass = markdown.WAITING_CLASS;
  markJoins = markdown.markJoins;

  // Every file of a rendered format is drawn with the chooser; a projection is asked only
  // for one whose changes loaded.
  const formatted = recorded.manifest.filter((entry) => markdown.renderedFormat(entry) !== null);
  const ahead = markdown.firstScreenRendered(recorded.manifest);

  // The plugin mounts the pull request's comparison, as its Changes does, on each page, and
  // hands the diff the rule for which addresses open there.
  await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/index.js")).href
  );
  assert(plugin !== null, "the diff plugin registered its view");
  const routes = new URL(recorded.rendered_route, ORIGIN).searchParams;
  const base = routes.get("left");
  const head = routes.get("right");
  const corpus = JSON.parse(
    fs.readFileSync(
      path.join(repoRoot, "src/metabrowser/data/file-diff-format/file-diff-conformance.json"),
      "utf8",
    ),
  );
  const added = corpus.cases.find((entry) => entry.name === "added-text-file").document;
  const comparison = {
    left: base,
    right: head,
    base_policy: "merge_base",
    rendered_route: recorded.rendered_route,
    image_route: recorded.image_route,
    branch: { ref: "refs/pull/7/head" },
  };
  /** The rule the plugin mounts the diff with on a page pinned at *pin*, or with no pin. */
  async function targetsOn(pin) {
    if (pin === null) {
      delete globalThis.window.METABROWSER_SOURCE_PIN;
      Object.assign(pageSource, { kind: "filesystem", repository: repositoryAt(head) });
    } else {
      globalThis.window.METABROWSER_SOURCE_PIN = { pin, ref: null };
      Object.assign(pageSource, { kind: "git_revision", repository: repositoryAt(pin) });
    }
    const mounted = await plugin.render({}, { comparison, raw: structuredClone(added) });
    assert(typeof mounted?.options?.markdownTargets === "function", "the diff has a rule");
    const target = mounted.options.markdownTargets;
    return (href, image, links = globalThis.window.MetabrowserRepositoryLinks) =>
      target(href, image, links);
  }
  const isTarget = await targetsOn(head);
  const atBase = await targetsOn(base);
  const beside = await targetsOn(null);
  const headLink = "/view/g1-ZG9jcw/g1-c2V0dXAubWQ";
  const route = recorded.image_route;
  const links = {
    route,
    // A link to a file of the head opens here only where its address names that file: on a
    // page that shows the head. On the other pages it opens that file at the head on
    // github.com.
    pages: {
      "pinned at the comparison's head": isTarget(headLink, false),
      "pinned at the merge base before the resolver arrives": atBase(headLink, false, null),
      "pinned at the merge base after the resolver arrives": atBase(headLink, false),
      "beside a checkout at the head, which has no pin": beside(headLink, false),
    },
    // On the page that shows the head.
    opens: Object.fromEntries(
      [
        ["/view/g1-ZG9jcw/g1-c2V0dXAubWQ", false],
        ["/view/g1-ZG9jcw/g1-c2V0dXAubWQ#user-content-setup", false],
        [`${route}&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc`, true],
        [`${route}&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc`, false],
        [`${route}&side=head&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc`, true],
        [route.replace("left=a", "left=0"), true],
        ["/api/tree?path=docs", false],
      ].map(([href, image]) => [`${image ? "image" : "link"} ${href}`, isTarget(href, image)]),
    ),
  };

  const root = element("div");
  // Each file's chooser is bound by itself, never the diff around them, whose toolbar holds
  // another control's dropdown (mb-yn7w).
  const bound = new Map();
  const makeViews = () =>
    markdown.createMarkdownViews({
      controls: {
        groupHtml: (spec) => spec,
        bind(container, handlers) {
          assert(container.className === "diff-markdown-control", "a chooser is bound by itself");
          bound.set(container, handlers.onChange);
          return () => bound.delete(container);
        },
      },
      load(fileId, signal, ask) {
        const key = asked(fileId, ask);
        requests.push(key);
        return new Promise((resolve, reject) => {
          const request = { fileId, key, resolve, reject };
          waiting.push(request);
          signal.addEventListener("abort", () => {
            requests.push(`abort ${key}`);
            reject(new DOMException("aborted", "AbortError"));
          });
        });
      },
      ensureInert: async () => inert,
      loadStyles: async () => {},
      mutate: (change) => change(),
      isTarget,
      now: clock.now,
      later: clock.later,
      cancel: clock.cancel,
    });
  const views = makeViews();

  /** Add one changed file to *views*, its section in *root*, as diff-view.js adds one. */
  const addTo = (views, root) => (entry) => {
    const section = element("section");
    const bar = element("div");
    const toggle = element("button");
    const end = element("div");
    bar.append(toggle, end);
    const source = element("div");
    source.id = `diff-file-${entry.id}`;
    section.append(bar, source);
    root.append(section);
    // As diff-view.js adds a file: one whose changes did not load says, in its Source
    // body and on its Rendered chip, what the diff's own table says for its availability
    // (`AVAILABILITY_COPY`; tests/dom/diff-view-behavior.js holds that the diff passes it).
    assert(
      markdown.supportsRenderedChange(entry) || entry.availability === "too_large",
      `${entry.id}: the session knows no sentence for ${entry.availability}`,
    );
    const state = views.add({
      section,
      bar,
      end,
      source,
      id: entry.id,
      format: markdown.renderedFormat(entry),
      ...(markdown.supportsRenderedChange(entry)
        ? {}
        : { unavailable: "This change is too large to show inline." }),
    });
    const [progress, control] = end.childNodes;
    const [, fallback, rendered] = section.childNodes;
    const [, expand] = fallback.childNodes;
    return {
      name: `${entry.id} ${(entry.new ?? entry.old).path}`,
      id: entry.id,
      format: markdown.renderedFormat(entry),
      section,
      bar,
      source,
      control,
      expand,
      progress,
      rendered,
      state,
    };
  };
  const files = formatted.map(addTo(views, root));
  const byId = Object.fromEntries(files.map((file) => [file.id, file]));
  const choose = async (file, value) => {
    bound.get(file.control)(file.source.id, value, "one");
    await settle();
  };
  const near = (...ids) =>
    observers[0].notify(ids.map((id) => ({ target: byId[id].section, isIntersecting: true })));
  // The reader comes near the first chunk not drawn yet, or the one of blocks *span*.
  const nearChunk = (file, span = undefined) => {
    const spacer = observers[1].observed.find(
      (each) => file.rendered.contains(each) && (span === undefined || each.dataset.span === span),
    );
    assert(spacer !== undefined, `${file.name}: no chunk waits to be drawn`);
    observers[1].notify([{ target: spacer, isIntersecting: true }]);
  };
  /** A fold's bar in *file*, by the start of its label. */
  const bar = (file, label) => {
    const find = (parent) => {
      for (const node of parent.children) {
        if (node.classList.contains("fold-expander") && node.textContent.startsWith(label)) {
          return node;
        }
        const inner = find(node);
        if (inner !== null) {
          return inner;
        }
      }
      return null;
    };
    const found = find(file.rendered);
    assert(found !== null, `${file.name}: no fold reads ${label}`);
    return found;
  };
  /** Every fold's bar in *file*, in order. */
  const bars = (file) => {
    const found = [];
    const find = (parent) => {
      for (const node of parent.children) {
        if (node.classList.contains("fold-expander")) {
          found.push(node);
        }
        find(node);
      }
    };
    find(file.rendered);
    return found;
  };
  /** A fold's bar as a step prints it: its label, and whether it is open or waiting. */
  const barOf = (node) =>
    `${node.textContent}${node.getAttribute("aria-expanded") === "true" ? ", open" : ""}${
      node.getAttribute("aria-busy") === "true" ? ", loading" : ""
    }`;
  /**
   * A step about one file's chooser, progress mark, and fold bars alone, its rows left to
   * the steps around it, which print them when they change.
   */
  const brief = (name, file) => {
    const { rows: _rows, ...now } = describe(file);
    steps.push({
      step: name,
      requests,
      files: { [file.name]: { ...now, folds: bars(file).map(barOf) } },
    });
    requests = [];
  };
  /** What the views log while *run* runs, which a page shows no one. */
  const logged = async (run) => {
    const warn = console.warn;
    const lines = [];
    console.warn = (message) => lines.push(message);
    try {
      await run();
    } finally {
      console.warn = warn;
    }
    return lines;
  };
  const click = async (node) => {
    let prevented = false;
    node.listeners.get("click")({
      target: node,
      stopPropagation() {},
      preventDefault() {
        prevented = true;
      },
    });
    await settle();
    return prevented;
  };
  /** Follow a link in *file*'s rendered body whose text is *text*. */
  const follow = async (file, text) => {
    const find = (parent) => {
      for (const node of parent.children) {
        if (node.tagName === "A" && node.textContent === text) {
          return node;
        }
        const inner = find(node);
        if (inner !== null) {
          return inner;
        }
      }
      return null;
    };
    const link = find(file.rendered);
    assert(link !== null, `${file.name}: no link reads ${text}`);
    let prevented = false;
    file.rendered.listeners.get("click")({
      target: link,
      preventDefault() {
        prevented = true;
      },
    });
    await settle();
    return prevented;
  };

  views.observe(null);
  steps.push({
    step: "the page asks for the first screen's projections ahead of Changes",
    asks: ahead,
    lookahead: observers[0].options.rootMargin,
    chunks: observers[1].options.rootMargin,
  });
  step(
    "mount: a Markdown file waits for Rendered with Source hidden; " +
      "one whose changes did not load shows Source",
    files,
  );

  observers[0].notify(
    files.map((file) => ({
      target: file.section,
      isIntersecting: ["f1", "f2"].includes(file.id),
    })),
  );
  await settle();
  step("the first screen asks for its first file; a file away from it shows Source", files);

  answer("f1 view=concise");
  await settle();
  step("an answer within the loading delay paints Rendered first", files);

  clock.advance(50);
  await settle();
  step("past the loading delay a waiting file still waits, Source hidden", files);

  answer("f2 view=concise");
  await settle();
  step("a file Rendered cannot show stays in Source, and its chooser says why", files);

  await choose(byId.f2, "rendered");
  step("choosing an unavailable view changes nothing and asks for nothing", files);

  near("f3");
  await settle();
  answer("f3 view=concise", "busy");
  await settle();
  step("a busy server keeps Rendered and asks again after a wait", files);

  clock.advance(100);
  await settle();
  step("the wait is over", files);

  answer("f3 view=concise");
  await settle();
  near("f4");
  await settle();
  await choose(byId.f4, "source");
  step(
    "a file nested too deeply shows Source and says why; Source chosen while a request runs",
    files,
  );

  answer("f4 view=concise");
  await settle();
  step("the answer is kept, not shown", files);

  await choose(byId.f4, "rendered");
  step("choosing Rendered again shows the kept answer without asking", files);

  await click(bar(byId.f1, "5 unchanged blocks"));
  step("opening a fold draws its blocks, which the answer holds", [byId.f1]);

  await choose(byId.f1, "source");
  await choose(byId.f1, "rendered");
  near("f1");
  step("switching formats asks for nothing, and an open fold stays open", [byId.f1]);

  await click(byId.f1.expand);
  step("expanding unchanged sections draws every block already held", [byId.f1]);

  near("f6", "f7");
  await settle();
  answer("f6 view=concise");
  await settle();
  answer("f7 view=concise");
  await settle();
  step(
    "front matter that did not change is closed above the body's change, " +
      "and front matter removed is one removed row",
    [byId.f6, byId.f7],
  );

  near("f8", "f9");
  await settle();
  answer("f8 view=concise");
  await settle();
  step(
    "a file past the route's read bound says it is too large; " +
      "no projection is asked for a file whose changes did not load",
    [byId.f8, byId.f9],
  );

  near("f10");
  await settle();
  answer("f10 view=concise");
  await settle();
  step("Rendered Diff folds a short run with its blocks and withholds the long runs' blocks", [
    byId.f10,
  ]);

  await click(bar(byId.f10, "2 unchanged blocks"));
  step("opening the short run's fold asks for nothing", [byId.f10]);

  // The appendix's run is withheld too, and its blocks do not load: the bar closes again
  // and says so, and a press asks again.
  const appendix = () => bars(byId.f10).at(-1);
  await click(appendix());
  brief("a withheld fold asks for its blocks, the file's progress mark counting", byId.f10);
  const foldLog = await logged(async () => {
    answer("f10 blocks=21-23", "failed");
    await settle();
  });
  brief("blocks that did not load close the fold again, and its bar says so", byId.f10);
  steps.push({ step: "the failure is logged, not shown", logged: foldLog });
  await click(appendix());
  brief("a press on it asks again", byId.f10);
  await logged(async () => {
    answer("f10 blocks=21-23", "failed");
    await settle();
  });

  const followed = await follow(byId.f10, "the deep part");
  steps.push({
    step: "a link to a heading a withheld fold holds waits for it",
    prevented: followed,
  });
  step("its fold opens and asks for its blocks", [byId.f10]);

  answer("f10 blocks=13-15");
  await settle();
  step("its blocks are drawn, and the page goes to the heading", [byId.f10]);
  steps.push({ step: "scrolled into view", scrolled: scrolled.splice(0) });

  await click(byId.f10.expand);
  step("expanding unchanged sections asks for the blocks still withheld", [byId.f10]);

  // Source chosen while Full is asked for, and Full fails: the reader's choice stands.
  await choose(byId.f10, "source");
  const fullLog = await logged(async () => {
    answer("f10 view=full", "failed");
    await settle();
  });
  brief("Full failing after Source was chosen leaves Source chosen", byId.f10);
  steps.push({ step: "the failure is logged all the same", logged: fullLog });
  await choose(byId.f10, "rendered");
  await click(byId.f10.expand);
  brief("expanding unchanged sections again retries the request", byId.f10);

  answer("f10 view=full");
  await settle();
  step("Full draws every block once they arrive", [byId.f10]);

  await click(byId.f10.expand);
  step("collapsing unchanged sections keeps the folds the reader opened", [byId.f10]);

  near("f11");
  await settle();
  answer("f11 view=concise");
  await settle();
  step("a long document draws its first chunk and keeps the place of the rest", [byId.f11]);

  nearChunk(byId.f11);
  await settle();
  step("coming near a place draws the chunk there", [byId.f11]);

  // A chunk drawn before the one above it: that one, drawn later, joins the change on either
  // side of it, so the book's one run of added blocks stays one box (`joinChanges`).
  nearChunk(byId.f11, "400-500");
  await settle();
  step("coming near a later place first draws that chunk alone", [byId.f11]);

  steps.push({
    step: "a link into a chunk not drawn yet",
    prevented: await follow(byId.f11, "the last part"),
  });
  step("draws every chunk through it, and the link goes there", [byId.f11]);

  // Another tab switched the server's pin: a link to a file of the head would open that
  // path at the other pin, so every one drawn opens that file at the head on github.com
  // instead, and so does any drawn later; images stay on the comparison's own route. The pin
  // guard says so once, and the page that showed the head keeps no `/view/` link from then on. The diff's own call when it
  // hears this is diff-view.js's (tests/dom/diff-view-behavior.js); here the session makes
  // it, as the diff's stand-in.
  pinChanged(base);
  links.pages["pinned at the comparison's head, after another tab changed the pin"] = isTarget(
    headLink,
    false,
  );
  views.closeHeadLinks();
  step("a page that learns another pin is served links a file to the head on github.com", [
    byId.f1,
  ]);

  views.dispose();
  step("disposal unbinds every chooser and stops every timer", files);
  steps.push({ step: "after disposal", bound: bound.size, timers: clock.timers.size });

  // The ceiling on a file's wait (`RENDERED_WAIT_MS`), each in a comparison of its own with
  // one first-screen file: a server that is busy, asked again and again, and one that is
  // slow, whose answer comes after the ceiling.
  /** Mount *id* alone on the first screen; the views, the file, and when it was mounted. */
  const mountAlone = async (id) => {
    shown.clear();
    const alone = makeViews();
    const file = addTo(alone, element("div"))(formatted.find((entry) => entry.id === id));
    const at = clock.time;
    alone.observe(null);
    observers.at(-2).notify([{ target: file.section, isIntersecting: true }]);
    await settle();
    return { alone, file, at };
  };
  const ceiling = markdown.RENDERED_WAIT_MS;
  const busy = await mountAlone("f1");
  let refusals = 0;
  for (;;) {
    while (waiting.some((request) => request.fileId === "f1")) {
      answer("f1 view=concise", "busy");
      refusals += 1;
      await settle();
    }
    if (clock.time - busy.at >= ceiling - 100) {
      break;
    }
    clock.advance(100);
    await settle();
  }
  assert(refusals > 3, "the busy file was asked again and again");
  requests = [];
  step("a busy server, asked again and again to just short of the wait's ceiling: it waits", [
    busy.file,
  ]);
  clock.advance(ceiling - (clock.time - busy.at));
  await settle();
  step("at the ceiling it shows Source and keeps Rendered to choose", [busy.file]);
  clock.advance(10 * ceiling);
  await settle();
  step("and is asked for no more by itself", [busy.file]);
  busy.alone.dispose();

  const slow = await mountAlone("f1");
  clock.advance(ceiling - 1);
  await settle();
  step("a slow server, to just short of the ceiling: the file waits", [slow.file]);
  clock.advance(1);
  await settle();
  step("at the ceiling it shows Source", [slow.file]);
  answer("f1 view=concise");
  await settle();
  step("its answer comes late and replaces nothing", [slow.file]);
  // No file waits past the ceiling, and nothing replaces Source by itself afterwards.
  assert(
    [busy.file, slow.file].every((file) => !file.source.hidden && file.rendered.hidden),
    "a file past the ceiling shows Source",
  );
  bound.get(slow.file.control)(slow.file.source.id, "rendered", "one");
  await settle();
  step("choosing Rendered shows the answer that was kept, asking for nothing", [slow.file]);
  slow.alone.dispose();
  steps.push({ step: "after their disposal", bound: bound.size, timers: clock.timers.size });

  finished = true;
  process.stdout.write(`${JSON.stringify(printed(PART, links, steps), null, 2)}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
